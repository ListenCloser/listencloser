"""Tests for the bounded remote-ZIP extractor (no network)."""

from __future__ import annotations

import struct
import zlib

import pytest

from evaluation.datasets._remote_zip import RemoteZip, _apply_zip64, download_member


def _make_zip64_extra(uncomp: int, comp: int, offset: int) -> bytes:
    body = struct.pack("<QQQ", uncomp, comp, offset)
    return struct.pack("<HH", 0x0001, len(body)) + body


def _local_header(name: bytes, comp_size: int, uncomp_size: int, method: int) -> bytes:
    fixed = struct.pack("<IHHHHHIIHH", 0x04034B50, 20, 0, 0, method, 0, 0, 0, 0, 0)
    return fixed + name


class TestApplyZip64:
    def test_no_sentinels_returns_unchanged(self):
        assert _apply_zip64(8, 10, 20, 30, b"") == (8, 10, 20, 30)

    def test_fills_uncompressed_from_extra(self):
        extra = _make_zip64_extra(0x123456789, 0xFFFFFFFF, 0xFFFFFFFF)
        method, comp, uncomp, off = _apply_zip64(8, 0xFFFFFFFF, 0xFFFFFFFF, 0xFFFFFFFF, extra)
        assert (method, comp, uncomp, off) == (8, 0xFFFFFFFF, 0x123456789, 0xFFFFFFFF)

    def test_fills_all_three_from_extra(self):
        extra = _make_zip64_extra(0x111111111, 0x222222222, 0x333333333)
        method, comp, uncomp, off = _apply_zip64(8, 0xFFFFFFFF, 0xFFFFFFFF, 0xFFFFFFFF, extra)
        assert (method, comp, uncomp, off) == (8, 0x222222222, 0x111111111, 0x333333333)

    def test_ignores_unrelated_extra_entries(self):
        other = struct.pack("<HHH", 0x0000, 2, 0xFFFF)
        extra = other + _make_zip64_extra(5, 6, 7)
        assert _apply_zip64(8, 0xFFFFFFFF, 0xFFFFFFFF, 0xFFFFFFFF, extra)[1:] == (6, 5, 7)

    def test_missing_zip64_returns_sentinels(self):
        assert _apply_zip64(8, 0xFFFFFFFF, 0xFFFFFFFF, 0xFFFFFFFF, b"\x00\x00")[1:] == (
            0xFFFFFFFF,
            0xFFFFFFFF,
            0xFFFFFFFF,
        )


class TestRemoteZipParsing:
    def _make_archive_bytes(self, entries: list[tuple[str, bytes]]) -> bytes:
        """Build a real (small) ZIP with deflated members and return its bytes."""
        import io
        import zipfile

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for name, data in entries:
                zf.writestr(name, data)
        return buf.getvalue()

    def test_members_from_real_zip(self):
        data = self._make_archive_bytes([("a/one.wav", b"hello" * 100), ("a/two.wav", b"x" * 500)])
        z = RemoteZip.__new__(RemoteZip)
        z.members = {}
        z._range = lambda start, end: data[start : end + 1]
        import io

        with io.BytesIO(data) as fh:
            fh.seek(0, 2)
            total = fh.tell()
            tail = data[total - 200 :]
            eocd = tail.rfind(b"PK\x05\x06")
            cd_off = struct.unpack("<I", tail[eocd + 16 : eocd + 20])[0]
            cd_size = struct.unpack("<I", tail[eocd + 12 : eocd + 16])[0]
        z._parse_central_directory(cd_off, cd_size)
        assert set(z.members) == {"a/one.wav", "a/two.wav"}
        assert z.members["a/one.wav"].comp_method == 8

    def test_read_deflates_member(self, tmp_path):
        payload = b"piano bytes " * 500
        import io
        import zipfile

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("dir/track.wav", payload)
        data = buf.getvalue()

        z = RemoteZip.__new__(RemoteZip)
        z.url = "http://unused"
        z.members = {}
        with io.BytesIO(data):
            total = len(data)
            tail = data[total - 200 :]
            eocd = tail.rfind(b"PK\x05\x06")
            cd_off = struct.unpack("<I", tail[eocd + 16 : eocd + 20])[0]
            cd_size = struct.unpack("<I", tail[eocd + 12 : eocd + 16])[0]
        z._range = lambda start, end: data[start : end + 1]
        z._parse_central_directory(cd_off, cd_size)
        m = z.members["dir/track.wav"]
        # simulate the local-header range read
        lh = data[m.local_offset : m.local_offset + 30]
        nlen = struct.unpack("<H", lh[26:28])[0]
        elen = struct.unpack("<H", lh[28:30])[0]
        data_start = m.local_offset + 30 + nlen + elen
        raw = data[data_start : data_start + m.comp_size]
        assert zlib.decompress(raw, -zlib.MAX_WBITS) == payload


class TestDownloadMember:
    def test_idempotent_when_dest_exists(self, tmp_path, monkeypatch):
        dest = tmp_path / "x.wav"
        dest.write_bytes(b"exists")
        monkeypatch.setattr(
            "evaluation.datasets._remote_zip.RemoteZip",
            lambda *a, **k: pytest.fail("should not touch network"),
        )
        result = download_member("http://unused", "x.wav", dest)
        assert result == dest
        assert dest.read_bytes() == b"exists"
