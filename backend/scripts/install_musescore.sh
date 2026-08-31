#!/usr/bin/env bash
set -euo pipefail

readonly MUSESCORE_VERSION="4.7.4"
readonly MUSESCORE_BUILD="260706075"

install_dir="${1:?usage: install_musescore.sh INSTALL_DIR}"

case "$(uname -m)" in
  x86_64|amd64)
    asset_arch="x86_64"
    expected_sha="9233ed1b87d3e6b45722278f3c286dcd41e83da778bd0f80a1dd04949696ad93"
    ;;
  aarch64|arm64)
    asset_arch="aarch64"
    expected_sha="162ae55b317660f196b2e73d566bdb45c1e990ed4cc140709d25d97b9ef366b0"
    ;;
  *)
    echo "Unsupported MuseScore architecture: $(uname -m)" >&2
    exit 1
    ;;
esac

asset="MuseScore-Studio-${MUSESCORE_VERSION}.${MUSESCORE_BUILD}-${asset_arch}.AppImage"
url="https://github.com/musescore/MuseScore/releases/download/v${MUSESCORE_VERSION}/${asset}"
tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT
appimage="${tmp_dir}/${asset}"

curl --fail --location --retry 3 --output "$appimage" "$url"
echo "${expected_sha}  ${appimage}" | sha256sum --check -
chmod +x "$appimage"
(
  cd "$tmp_dir"
  "$appimage" --appimage-extract >/dev/null
)

rm -rf "$install_dir"
mkdir -p "$(dirname "$install_dir")"
mv "${tmp_dir}/squashfs-root" "$install_dir"

printf '%s\n' \
  "MuseScore Studio ${MUSESCORE_VERSION}.${MUSESCORE_BUILD}" \
  "License: GPL-3.0" \
  "Source: https://github.com/musescore/MuseScore/releases/tag/v${MUSESCORE_VERSION}" \
  > "${install_dir}/LISTENCLOSER_PROVENANCE.txt"
