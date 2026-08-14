"""Bounded extraction of individual files from a remote ZIP archive.

Downloads only the byte ranges needed to inflate specific members of a ZIP that
is far too large to fetch whole (e.g. the 101 GB MAESTRO v3.0.0 archive), using
HTTP ``Range`` requests. The central directory is fetched once (it sits at the
end of the file) and individual members are streamed on demand.

The implementation supports ordinary and ZIP64 archives (MAESTRO v3.0.0 uses
ZIP64). ``download()`` is idempotent: members are cached on disk keyed by their
archive path, so repeated calls only fetch bytes once.
"""

from __future__ import annotations

import os
import struct
import zlib
from dataclasses import dataclass, field
from pathlib import Path
from urllib import request

_CHUNK = 1 << 16
_HEADER_TAIL_BYTES = 70_000


@dataclass
class _Member:
    comp_method: int
    comp_size: int
    uncomp_size: int
    local_offset: int


def _apply_zip64(
    comp_method: int,
    comp_size: int,
    uncomp_size: int,
    local_offset: int,
    extra: bytes,
) -> tuple[int, int, int, int]:
    """Replace 0xFFFFFFFF sentinels using the ZIP64 extra field (0x0001).

    The ZIP64 extra record contains, in order, only the 8-byte fields whose
    32-bit placeholders overflowed: uncompressed size, compressed size, then
    local header offset.
    """
    needs_uncomp = uncomp_size == 0xFFFFFFFF
    needs_comp = comp_size == 0xFFFFFFFF
    needs_off = local_offset == 0xFFFFFFFF
    if not (needs_uncomp or needs_comp or needs_off):
        return comp_method, comp_size, uncomp_size, local_offset
    p = 0
    while p + 4 <= len(extra):
        hdr = struct.unpack("<H", extra[p : p + 2])[0]
        size = struct.unpack("<H", extra[p + 2 : p + 4])[0]
        body = extra[p + 4 : p + 4 + size]
        if hdr == 0x0001:
            q = 0
            if needs_uncomp:
                uncomp_size = struct.unpack("<Q", body[q : q + 8])[0]
                q += 8
            if needs_comp:
                comp_size = struct.unpack("<Q", body[q : q + 8])[0]
                q += 8
            if needs_off:
                local_offset = struct.unpack("<Q", body[q : q + 8])[0]
            return comp_method, comp_size, uncomp_size, local_offset
        p += 4 + size
    return comp_method, comp_size, uncomp_size, local_offset


class RemoteZip:
    """Random access to members of a remote ZIP archive."""

    def __init__(self, url: str, total_size: int | None = None) -> None:
        self.url = url
        self._total = total_size
        self.members: dict[str, _Member] = {}
        self._locate_central_directory()

    # ── central directory discovery ──────────────────────────────────────────

    def _range(self, start: int, end: int) -> bytes:
        """Fetch the inclusive byte range [start, end]."""
        req = request.Request(self.url, headers={"Range": f"bytes={start}-{end}"})
        with request.urlopen(req, timeout=120) as resp:
            return resp.read()

    def _locate_central_directory(self) -> None:
        if self._total is None:
            self._total = self._probe_size()
        tail = self._range(self._total - _HEADER_TAIL_BYTES, self._total - 1)
        eocd_idx = tail.rfind(b"PK\x05\x06")
        if eocd_idx == -1:
            raise RuntimeError("no End Of Central Directory record found")
        loc = tail[eocd_idx - 20 : eocd_idx]
        if loc[:4] != b"PK\x06\x07":
            raise RuntimeError("ZIP64 EOCD locator not found (non-ZIP64 archive)")
        zip64_eocd_off = struct.unpack("<Q", loc[8:16])[0]
        z64 = self._range(zip64_eocd_off, zip64_eocd_off + 55)
        if z64[:4] != b"PK\x06\x06":
            raise RuntimeError("ZIP64 EOCD record not found")
        cd_off = struct.unpack("<Q", z64[48:56])[0]
        cd_size = struct.unpack("<Q", z64[40:48])[0]
        self._parse_central_directory(cd_off, cd_size)

    def _probe_size(self) -> int:
        req = request.Request(self.url, method="HEAD")
        with request.urlopen(req, timeout=120) as resp:
            length = resp.headers.get("Content-Length")
            if length is None:
                raise RuntimeError("remote archive reports no Content-Length")
            return int(length)

    def _parse_central_directory(self, cd_off: int, cd_size: int) -> None:
        cd = self._range(cd_off, cd_off + cd_size - 1)
        pos = 0
        while pos + 46 <= len(cd):
            if cd[pos : pos + 4] != b"PK\x01\x02":
                break
            comp_method = struct.unpack("<H", cd[pos + 10 : pos + 12])[0]
            comp_size = struct.unpack("<I", cd[pos + 20 : pos + 24])[0]
            uncomp_size = struct.unpack("<I", cd[pos + 24 : pos + 28])[0]
            local_off = struct.unpack("<I", cd[pos + 42 : pos + 46])[0]
            name_len = struct.unpack("<H", cd[pos + 28 : pos + 30])[0]
            extra_len = struct.unpack("<H", cd[pos + 30 : pos + 32])[0]
            comment_len = struct.unpack("<H", cd[pos + 32 : pos + 34])[0]
            name = cd[pos + 46 : pos + 46 + name_len].decode("utf-8", "replace")
            extra = cd[pos + 46 + name_len : pos + 46 + name_len + extra_len]
            comp_method, comp_size, uncomp_size, local_off = _apply_zip64(
                comp_method, comp_size, uncomp_size, local_off, extra
            )
            self.members[name] = _Member(
                comp_method=comp_method,
                comp_size=comp_size,
                uncomp_size=uncomp_size,
                local_offset=local_off,
            )
            pos += 46 + name_len + extra_len + comment_len

    # ── member access ────────────────────────────────────────────────────────

    def has(self, name: str) -> bool:
        return name in self.members

    def read(self, name: str) -> bytes:
        """Return the inflated bytes of a single archive member."""
        if name not in self.members:
            raise KeyError(f"{name} not in archive")
        member = self.members[name]
        lh = self._range(member.local_offset, member.local_offset + 29)
        if lh[:4] != b"PK\x03\x04":
            raise RuntimeError(f"bad local header for {name}")
        nlen = struct.unpack("<H", lh[26:28])[0]
        elen = struct.unpack("<H", lh[28:30])[0]
        data_start = member.local_offset + 30 + nlen + elen
        raw = self._range(data_start, data_start + member.comp_size - 1)
        if member.comp_method == 0:
            return raw
        if member.comp_method == 8:
            return zlib.decompress(raw, -zlib.MAX_WBITS)
        raise RuntimeError(f"unsupported compression method {member.comp_method}")


def download_member(
    url: str,
    member: str,
    dest: Path,
    total_size: int | None = None,
    _zip: RemoteZip | None = None,
) -> Path:
    """Extract ``member`` from the remote archive ``url`` into ``dest``.

    Idempotent: returns immediately when ``dest`` already exists and is
    non-empty. ``_zip`` is an optional shared RemoteZip to avoid re-fetching the
    central directory across many members.
    """
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    if _zip is None:
        _zip = RemoteZip(url, total_size=total_size)
    data = _zip.read(member)
    tmp = dest.with_suffix(dest.suffix + ".part")
    try:
        tmp.write_bytes(data)
        os.replace(tmp, dest)
    finally:
        if tmp.exists():
            tmp.unlink(missing_ok=True)
    return dest
