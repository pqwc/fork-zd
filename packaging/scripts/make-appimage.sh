#!/usr/bin/env bash
# Собирает AppImage из dist/ZapretDesktop.
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
APPDIR="dist/ZapretDesktop-${VERSION}-x86_64.AppDir"
APPIMAGE="dist/ZapretDesktop-${VERSION}-x86_64.AppImage"

if [[ ! -x dist/ZapretDesktop/ZapretDesktop ]]; then
    echo "[ERROR] Run ./build.sh --target portable first" >&2
    exit 1
fi

if [[ ! -f packaging/assets/zapretdesktop.png ]]; then
    python3 packaging/scripts/extract_icon.py -o packaging/assets/zapretdesktop.png
fi

APPIMAGETOOL=""
if command -v appimagetool >/dev/null 2>&1; then
    APPIMAGETOOL="appimagetool"
elif [[ -x packaging/tools/appimagetool-x86_64.AppImage ]]; then
    APPIMAGETOOL="packaging/tools/appimagetool-x86_64.AppImage"
else
    echo "[ERROR] appimagetool not found." >&2
    echo "  Install: https://github.com/AppImage/AppImageKit/releases" >&2
    echo "  Or place appimagetool-x86_64.AppImage in packaging/tools/" >&2
    exit 1
fi

echo "[appimage] Preparing AppDir: $APPDIR"
rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr/bin" "$APPDIR/usr/share/applications" \
    "$APPDIR/usr/share/icons/hicolor/256x256/apps" \
    "$APPDIR/usr/share/linux-runtime"

cp -a dist/ZapretDesktop "$APPDIR/usr/bin/"
cp -a dist/linux-runtime/. "$APPDIR/usr/share/linux-runtime/"
cp packaging/debian/zapretdesktop.desktop "$APPDIR/"
cp packaging/assets/zapretdesktop.png "$APPDIR/zapretdesktop.png"
cp packaging/assets/zapretdesktop.png "$APPDIR/usr/share/icons/hicolor/256x256/apps/zapretdesktop.png"

sed 's|^Exec=.*|Exec=ZapretDesktop %U|' "$APPDIR/zapretdesktop.desktop" >"$APPDIR/zapretdesktop.desktop.tmp"
mv "$APPDIR/zapretdesktop.desktop.tmp" "$APPDIR/zapretdesktop.desktop"

cat >"$APPDIR/AppRun" <<'EOF'
#!/bin/sh
HERE="$(dirname "$(readlink -f "$0" 2>/dev/null || echo "$0")")"
export PATH="$HERE/usr/bin/ZapretDesktop:$PATH"
cd "$HERE/usr/bin/ZapretDesktop"
exec ./ZapretDesktop "$@"
EOF
chmod 755 "$APPDIR/AppRun"

ARCH="$(uname -m)"
export ARCH
"$APPIMAGETOOL" "$APPDIR" "$APPIMAGE"

echo "[appimage] Created: $APPIMAGE"
chmod +x "$APPIMAGE"
