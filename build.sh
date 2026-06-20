#!/usr/bin/env bash
# ZapretDesktop — сборка Linux (PyInstaller onedir, .deb, AppImage, tarball).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

TARGET="all"
SKIP_VENV=0
PYTHON_BIN="${PYTHON_BIN:-python3}"

usage() {
    cat <<'EOF'
Usage: ./build.sh [options] [target]

Targets:
  portable   PyInstaller onedir + linux-runtime stub + tarball (default step)
  deb        .deb package (requires portable)
  appimage   AppImage (requires portable, needs appimagetool)
  all        portable + deb + appimage

Options:
  --target TARGET   One of: portable, deb, appimage, all
  --skip-venv       Use system Python instead of .venv-build
  --python PATH     Python interpreter (default: python3)
  -h, --help        Show this help
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --target)
            TARGET="${2:?}"
            shift 2
            ;;
        --skip-venv)
            SKIP_VENV=1
            shift
            ;;
        --python)
            PYTHON_BIN="${2:?}"
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        portable|deb|appimage|all)
            TARGET="$1"
            shift
            ;;
        *)
            echo "Unknown argument: $1" >&2
            usage >&2
            exit 1
            ;;
    esac
done

read_version() {
    "$PYTHON_BIN" - <<'PY'
import re
from pathlib import Path
text = Path("src/entities/config/config_manager.py").read_text(encoding="utf-8")
m = re.search(r'^VERSION\s*=\s*["\']([^"\']+)["\']', text, re.M)
print(m.group(1) if m else "0.0.0")
PY
}

VERSION="$(read_version)"
echo "========================================"
echo "  ZapretDesktop Linux build  v${VERSION}"
echo "========================================"

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
    echo "[ERROR] Python not found: $PYTHON_BIN" >&2
    exit 1
fi

if [[ "$SKIP_VENV" -eq 0 ]]; then
    VENV_DIR="$ROOT/.venv-build"
    if [[ ! -d "$VENV_DIR" ]]; then
        echo "[1/6] Creating venv: $VENV_DIR"
        "$PYTHON_BIN" -m venv "$VENV_DIR"
    fi
    # shellcheck disable=SC1091
    source "$VENV_DIR/bin/activate"
    PYTHON_BIN="python"
fi

echo "[deps] Installing build dependencies..."
"$PYTHON_BIN" -m pip install --upgrade pip -q
"$PYTHON_BIN" -m pip install -r requirements.txt -q
"$PYTHON_BIN" -m pip install -r requirements-build.txt -q

if [[ -n "${PYARMOR_REGFILE:-}" ]]; then
    echo "[deps] Registering PyArmor license..."
    "$PYTHON_BIN" -m pyarmor.cli reg "$PYARMOR_REGFILE"
fi

build_portable() {
    echo "[portable] Cleaning previous dist..."
    rm -rf build dist/ZapretDesktop "dist/ZapretDesktop-${VERSION}-linux-x86_64.tar.gz" .pyarmor
    rm -f *.patched.spec

    echo "[portable] Extracting icon..."
    "$PYTHON_BIN" packaging/scripts/extract_icon.py \
        -o packaging/assets/zapretdesktop.png

    echo "[portable] Running PyArmor + PyInstaller (onedir)..."
    "$PYTHON_BIN" packaging/scripts/pyarmor_pack.py --spec ZapretDesktop-linux.spec

    if [[ ! -x dist/ZapretDesktop/ZapretDesktop ]]; then
        echo "[ERROR] dist/ZapretDesktop/ZapretDesktop not found" >&2
        exit 1
    fi

    echo "[portable] Bundling linux-runtime stub..."
    rm -rf dist/linux-runtime
    cp -a packaging/linux-runtime dist/linux-runtime

    echo "[portable] Copying desktop launcher template..."
    mkdir -p dist/ZapretDesktop
    cp packaging/debian/zapretdesktop.desktop dist/ZapretDesktop/zapretdesktop.desktop.example
    cp packaging/assets/zapretdesktop.png dist/ZapretDesktop/icon.png

    TARBALL="dist/ZapretDesktop-${VERSION}-linux-x86_64.tar.gz"
    echo "[portable] Creating tarball: $TARBALL"
    tar -C dist -czf "$TARBALL" ZapretDesktop linux-runtime

    echo "[portable] Done."
    echo "  Binary:  dist/ZapretDesktop/ZapretDesktop"
    echo "  Bundle:  $TARBALL"
}

build_deb() {
    if [[ ! -x dist/ZapretDesktop/ZapretDesktop ]]; then
        echo "[deb] Portable build missing — building portable first..."
        build_portable
    fi
    bash packaging/scripts/make-deb.sh
}

build_appimage() {
    if [[ ! -x dist/ZapretDesktop/ZapretDesktop ]]; then
        echo "[appimage] Portable build missing — building portable first..."
        build_portable
    fi
    bash packaging/scripts/make-appimage.sh
}

case "$TARGET" in
    portable)
        build_portable
        ;;
    deb)
        build_deb
        ;;
    appimage)
        build_appimage
        ;;
    all)
        build_portable
        build_deb
        build_appimage
        ;;
    *)
        echo "Unknown target: $TARGET" >&2
        exit 1
        ;;
esac

echo "========================================"
echo "  Build finished (target: $TARGET)"
echo "========================================"
