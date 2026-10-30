#!/bin/sh
# Fetch the signed WinDivert driver used by the Windows split-tunneling helper.
#
# pvpn-split.exe needs WinDivert.dll and WinDivert64.sys next to it. Both ship
# from upstream already signed by Basil, so no driver has to be built or signed
# here. The files are not vendored in git because of their size and licence, so
# this script downloads and verifies them into engine/.
#
# Usage: scripts/fetch-windivert.sh [destination-directory]
set -eu

VERSION="2.2.2"
ARCHIVE="WinDivert-${VERSION}-A.zip"
URL="https://reqrypt.org/download/${ARCHIVE}"
SHA256="63cb41763bb4b20f600b6de04e991a9c2be73279e317d4d82f237b150c5f3f15"

DEST="${1:-engine}"
mkdir -p "$DEST"

if [ -f "$DEST/WinDivert.dll" ] && [ -f "$DEST/WinDivert64.sys" ]; then
    echo "-> WinDivert is already present in $DEST"
    exit 0
fi

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

echo "-> Downloading $URL"
if command -v curl >/dev/null 2>&1; then
    curl -fsSL "$URL" -o "$TMP/$ARCHIVE"
elif command -v wget >/dev/null 2>&1; then
    wget -qO "$TMP/$ARCHIVE" "$URL"
else
    echo "[ERROR] curl or wget is required" >&2
    exit 1
fi

# The checksum is advisory: upstream re-publishes archives, and a mismatch must
# be loud but must not silently install something unexpected.
if command -v sha256sum >/dev/null 2>&1; then
    ACTUAL="$(sha256sum "$TMP/$ARCHIVE" | cut -d' ' -f1)"
    if [ "$ACTUAL" != "$SHA256" ]; then
        echo "[WARNING] Unexpected checksum for $ARCHIVE" >&2
        echo "          expected $SHA256" >&2
        echo "          actual   $ACTUAL" >&2
        if [ "${WINDIVERT_ALLOW_CHECKSUM_MISMATCH:-0}" != "1" ]; then
            echo "[ERROR] Refusing to install. Re-run with" >&2
            echo "        WINDIVERT_ALLOW_CHECKSUM_MISMATCH=1 after verifying the file," >&2
            echo "        and update SHA256 in this script." >&2
            exit 1
        fi
    fi
fi

if ! command -v unzip >/dev/null 2>&1; then
    echo "[ERROR] unzip is required" >&2
    exit 1
fi

unzip -qo "$TMP/$ARCHIVE" -d "$TMP/extracted"

# Only the 64-bit build is needed: the packaged application is amd64 only.
found=0
for candidate in "$TMP/extracted"/*/x64 "$TMP/extracted"/x64; do
    if [ -f "$candidate/WinDivert.dll" ]; then
        cp "$candidate/WinDivert.dll" "$DEST/WinDivert.dll"
        cp "$candidate/WinDivert64.sys" "$DEST/WinDivert64.sys"
        found=1
        break
    fi
done

if [ "$found" -ne 1 ]; then
    echo "[ERROR] Could not find the x64 payload inside $ARCHIVE" >&2
    exit 1
fi

echo "-> Installed WinDivert.dll and WinDivert64.sys into $DEST"
