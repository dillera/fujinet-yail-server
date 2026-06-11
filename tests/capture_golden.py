"""Capture golden YAI byte streams from the conversion pipeline.

The committed golden files were captured from the legacy pre-2.0
server/yail.py (now only in git history) to freeze the wire format.
Run with YAIL_IMPL=new to regenerate .new files from the current package
for comparison; YAIL_IMPL=legacy needs the old server/ tree checked out.
"""
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
GOLDEN_DIR = Path(__file__).resolve().parent / "golden"
TEST_IMAGE = REPO_ROOT / "test_images" / "yail_apple_splash1.jpg"

IMPL = os.environ.get("YAIL_IMPL", "legacy")
if IMPL == "legacy":
    sys.path.insert(0, str(REPO_ROOT / "server"))
    from yail import convertImageToYAIL, GRAPHICS_8, GRAPHICS_9, VBXE
else:
    sys.path.insert(0, str(REPO_ROOT / "src"))
    from yail.imaging import convert_image_to_yail as convertImageToYAIL
    from yail.protocol import GRAPHICS_8, GRAPHICS_9, VBXE

from PIL import Image


def main() -> None:
    GOLDEN_DIR.mkdir(exist_ok=True)
    suffix = "" if IMPL == "legacy" else ".new"
    image = Image.open(TEST_IMAGE)
    for name, mode in (("gfx8", GRAPHICS_8), ("gfx9", GRAPHICS_9), ("vbxe", VBXE)):
        data = bytes(convertImageToYAIL(image.copy(), mode))
        out = GOLDEN_DIR / f"splash_{name}.bin{suffix}"
        out.write_bytes(data)
        print(f"{out.name}: {len(data)} bytes, header={data[:9].hex(' ')}")


if __name__ == "__main__":
    main()
