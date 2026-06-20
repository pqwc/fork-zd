#!/usr/bin/env bash
# Собирает .deb из dist/ZapretDesktop (PyInstaller onedir).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

read_version() {
    python3 - <<'PY'
import re
from pathlib import Path
text = Path("src/entities/config/config_manager.py").read_text(encoding="utf-8")
m = re.search(r'^VERSION\s*=\s*["\']([^"\']+)["\']', text, re.M)
print(m.group(1) if m else "0.0.0")
PY
}

VERSION="$(read_version)"
PKG_NAME="zapretdesktop"
ARCH="amd64"
DEB_FILE="dist/${PKG_NAME}_${VERSION}_${ARCH}.deb"
STAGING="dist/deb-root"

if [[ ! -x dist/ZapretDesktop/ZapretDesktop ]]; then
    echo "[ERROR] Run ./build.sh --target portable first" >&2
    exit 1
fi

if [[ ! -f packaging/assets/zapretdesktop.png ]]; then
    python3 packaging/scripts/extract_icon.py -o packaging/assets/zapretdesktop.png
fi

echo "[deb] Staging package in $STAGING ..."
rm -rf "$STAGING"
mkdir -p "$STAGING/DEBIAN"
mkdir -p "$STAGING/opt/zapretdesktop"
mkdir -p "$STAGING/usr/bin"
mkdir -p "$STAGING/usr/share/applications"
mkdir -p "$STAGING/usr/share/icons/hicolor/256x256/apps"
mkdir -p "$STAGING/usr/share/icons/hicolor/scalable/apps"
mkdir -p "$STAGING/usr/share/metainfo"
mkdir -p "$STAGING/usr/share/doc/${PKG_NAME}"

cp -a dist/ZapretDesktop/. "$STAGING/opt/zapretdesktop/"
cp packaging/debian/zapretdesktop.desktop "$STAGING/usr/share/applications/"
cp packaging/debian/zapretdesktop.metainfo.xml "$STAGING/usr/share/metainfo/"
cp packaging/assets/zapretdesktop.png "$STAGING/usr/share/icons/hicolor/256x256/apps/zapretdesktop.png"
cp packaging/assets/zapretdesktop.png "$STAGING/usr/share/icons/hicolor/scalable/apps/zapretdesktop.png"
cp packaging/linux-runtime/README.md "$STAGING/usr/share/doc/${PKG_NAME}/linux-runtime-README.md"
cp docs/LINUX_INSTALL.md "$STAGING/usr/share/doc/${PKG_NAME}/LINUX_INSTALL.md" 2>/dev/null || true

cat >"$STAGING/usr/bin/zapretdesktop" <<'LAUNCHER'
#!/bin/sh
exec /opt/zapretdesktop/ZapretDesktop "$@"
LAUNCHER
chmod 755 "$STAGING/usr/bin/zapretdesktop"

INSTALLED_SIZE="$(du -sk "$STAGING/opt/zapretdesktop" | awk '{print $1}')"

cat >"$STAGING/DEBIAN/control" <<EOF
Package: ${PKG_NAME}
Version: ${VERSION}
Section: net
Priority: optional
Architecture: ${ARCH}
Maintainer: pqwc <https://github.com/pqwc/fork-zd>
Installed-Size: ${INSTALLED_SIZE}
Depends: nftables, curl, iproute2, iputils-ping, sudo, bash
Recommends: polkit, systemd
Description: GUI for zapret DPI bypass on Linux
 ZapretDesktop provides a PyQt6 interface to manage zapret strategies
 via the zapret-discord-youtube-linux adapter (service.sh, nfqws).
 .
 The nfqws binary is not included; install the Linux adapter separately.
EOF

cp packaging/debian/postinst "$STAGING/DEBIAN/postinst"
cp packaging/debian/prerm "$STAGING/DEBIAN/prerm"
chmod 755 "$STAGING/DEBIAN/postinst" "$STAGING/DEBIAN/prerm"

mkdir -p dist
dpkg-deb --build --root-owner-group "$STAGING" "$DEB_FILE"

echo "[deb] Created: $DEB_FILE"
echo "      Install: sudo apt install ./${DEB_FILE}"
