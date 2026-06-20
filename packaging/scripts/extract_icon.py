#!/usr/bin/env python3
"""Извлекает PNG-иконку из embedded_assets для .desktop / .deb / AppImage."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def extract_icon(output: Path, *, fmt: str = "PNG") -> None:
    from PyQt6.QtGui import QImage, QPixmap
    from PyQt6.QtCore import QByteArray

    from src.shared.ui.assets.embedded_assets import ICON_BASE64
    import base64

    if not ICON_BASE64:
        raise RuntimeError("ICON_BASE64 is empty in embedded_assets.py")

    data = base64.b64decode(ICON_BASE64)
    ba = QByteArray(data)
    image = QImage()
    if not image.loadFromData(ba):
        pix = QPixmap()
        if not pix.loadFromData(ba):
            raise RuntimeError("Failed to decode embedded icon")
        image = pix.toImage()

    output.parent.mkdir(parents=True, exist_ok=True)
    if not image.save(str(output), fmt.upper()):
        raise RuntimeError(f"Failed to write {output}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=PROJECT_ROOT / "packaging" / "assets" / "zapretdesktop.png",
        help="Output image path",
    )
    parser.add_argument(
        "--format",
        default="PNG",
        choices=("PNG", "ICO"),
        help="Output format (default: PNG)",
    )
    args = parser.parse_args()

    from PyQt6.QtWidgets import QApplication

    app = QApplication([])
    try:
        extract_icon(args.output, fmt=args.format)
    finally:
        app.quit()
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
