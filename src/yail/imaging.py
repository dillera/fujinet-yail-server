"""Image conversion pipeline: PIL image -> Atari-native YAI byte stream.

The numeric behavior (resampling filters, dithering, bit packing) is frozen
to remain byte-identical with the legacy server output.
"""
import logging

import numpy as np
from PIL import Image

from yail.protocol import (
    GRAPHICS_8,
    GRAPHICS_9,
    GRAPHICS_11,
    VBXE_H,
    VBXE_W,
    YAIL_H,
    YAIL_W,
    build_vbxe_packet,
    build_yai_packet,
)

logger = logging.getLogger(__name__)

# GTIA mode 11 palette: hues 1-15 at luminance 8, sampled from atari800's
# default NTSC palette (act/default.act, entries hue*16+8).  Index 0 is
# black, not hue 0: GTIA forces pixel value %0000 to luminance 0 regardless
# of COLBK (Altirra Hardware Reference Manual p.154).  The client sets
# COLBK to hue 0 / luminance 8 to match.
GTIA_HUES_LUM8 = [
    (0, 0, 0),
    (255, 197, 29), (255, 152, 44), (255, 112, 110), (234, 81, 235),
    (224, 94, 255), (190, 96, 255), (113, 131, 255), (138, 132, 255),
    (85, 182, 255), (97, 208, 112), (33, 217, 27), (134, 217, 34),
    (161, 176, 52), (213, 181, 67), (225, 147, 68),
]


def prep_image_for_vbxe(image: Image.Image, target_width: int = VBXE_W,
                        target_height: int = VBXE_H) -> Image.Image:
    """Fit the image inside the target size, centered on a black background."""
    image_ratio = image.width / image.height
    target_ratio = target_width / target_height

    if image_ratio > target_ratio:
        new_width = target_width
        new_height = int(target_width / image_ratio)
    else:
        new_width = int(target_height * image_ratio)
        new_height = target_height

    image = image.resize((new_width, new_height), Image.BILINEAR)
    logger.debug(f"VBXE resized image to {image.size}")

    background = Image.new("RGB", (target_width, target_height), (0, 0, 0))
    paste_x = (target_width - image.width) // 2
    paste_y = (target_height - image.height) // 2
    background.paste(image, (paste_x, paste_y))
    return background


def fix_aspect(image: Image.Image, crop: bool = False) -> Image.Image:
    """Pad (or crop) a grayscale image to the YAIL 320:220 aspect ratio."""
    aspect = YAIL_W / YAIL_H
    aspect_i = 1 / aspect
    w, h = image.size
    img_aspect = w / h

    if crop:
        if img_aspect > aspect:  # wider than YAIL aspect
            new_width = int(h * aspect)
            diff_half = int((w - new_width) / 2)
            image = image.crop((diff_half, 0, w - diff_half, h))
        else:                    # taller than YAIL aspect
            new_height = int(w * aspect_i)
            diff_half = int((h - new_height) / 2)
            image = image.crop((0, diff_half, w, h - diff_half))
    else:
        if img_aspect > aspect:  # wider than YAIL aspect
            new_height = int(w * aspect_i)
            background = Image.new(image.mode, (w, new_height))
            background.paste(image, (0, int((new_height - h) / 2)))
            image = background
        else:                    # taller than YAIL aspect
            new_width = int(h * aspect)
            background = Image.new(image.mode, (new_width, h))
            background.paste(image, (int((new_width - w) / 2), 0))
            image = background

    return image


def dither_image(image: Image.Image) -> Image.Image:
    return image.convert("1")


def pack_bits(image: Image.Image) -> np.ndarray:
    """Pack a 1-bit image into Graphics 8 framebuffer bytes (8 pixels/byte)."""
    bits = np.array(image)
    return np.packbits(bits, axis=1)


def pack_shades(image: Image.Image) -> np.ndarray:
    """Pack a grayscale image into Graphics 9 bytes (two 4-bit pixels/byte)."""
    yail = image.resize((int(YAIL_W / 4), YAIL_H), Image.LANCZOS)
    yail = yail.convert(dither=Image.FLOYDSTEINBERG, colors=16)

    im_values = np.array(yail)[:, :]
    evens = im_values[:, ::2]
    odds = im_values[:, 1::2]

    # Upper four bits hold the left pixel, lower four bits the right pixel.
    combined = ((evens >> 4) << 4) + (odds >> 4)
    return combined.astype("int8")


# Pixels darker than this (HSV value, 0-255) become GTIA pixel 0 (black).
GR11_BLACK_THRESHOLD = 40
# Brightness the hues are normalized to before matching; roughly the luma of
# the GTIA_HUES_LUM8 entries, so quantization compares hue rather than light.
GR11_FLAT_VALUE = 205


def pack_hues(image: Image.Image) -> np.ndarray:
    """Pack an RGB image into Graphics 11 bytes (two 4-bit hue pixels/byte).

    GTIA mode 11 renders every nonzero pixel at one fixed luminance, so
    brightness cannot be represented.  Quantizing raw RGB against the hue
    palette makes the ditherer simulate brightness with black speckle and
    mutes the hues.  Instead: flatten HSV value so only hue/saturation
    drive the palette match against the 15 hues, then force originally
    dark pixels to black (pixel value 0, which GTIA renders at lum 0).
    """
    yail = image.resize((int(YAIL_W / 4), YAIL_H), Image.LANCZOS)

    hue, sat, val = yail.convert("HSV").split()
    dark = np.array(val) < GR11_BLACK_THRESHOLD
    flattened = Image.merge(
        "HSV", (hue, sat, Image.new("L", yail.size, GR11_FLAT_VALUE))
    ).convert("RGB")

    palette_image = Image.new("P", (1, 1))
    palette_image.putpalette([c for rgb in GTIA_HUES_LUM8[1:] for c in rgb])
    indexed = flattened.quantize(palette=palette_image, dither=Image.FLOYDSTEINBERG)

    im_values = np.array(indexed).astype("uint8") + 1  # palette holds hues 1-15
    im_values[dark] = 0

    evens = im_values[:, ::2]
    odds = im_values[:, 1::2]

    combined = (evens << 4) + odds
    return combined.astype("uint8")


def convert_image_to_yail(image: Image.Image, gfx_mode: int) -> bytearray:
    """Convert a PIL image to a complete YAI packet for the given mode."""
    logger.debug(f"Source image size={image.size} mode={image.mode} format={image.format}")

    if gfx_mode in (GRAPHICS_8, GRAPHICS_9):
        gray = image.convert(mode="L")
        gray = fix_aspect(gray)
        gray = gray.resize((YAIL_W, YAIL_H), Image.LANCZOS)

        if gfx_mode == GRAPHICS_8:
            image_data = pack_bits(dither_image(gray))
        else:
            image_data = pack_shades(gray)

        return build_yai_packet(image_data, gfx_mode)

    if gfx_mode == GRAPHICS_11:
        rgb = image.convert(mode="RGB")
        rgb = fix_aspect(rgb)
        rgb = rgb.resize((YAIL_W, YAIL_H), Image.LANCZOS)
        return build_yai_packet(pack_hues(rgb), gfx_mode)

    # VBXE: 320x240 with a 256-color adaptive palette.
    resized = prep_image_for_vbxe(image, target_width=VBXE_W, target_height=VBXE_H)
    resized = resized.convert("P", palette=Image.ADAPTIVE, colors=256)
    palette = resized.getpalette()
    pixel_bytes = resized.tobytes()

    # Shift palette and pixel indices by one: VBXE entry 0 stays black.
    offset_palette = [0] * 3 + palette[:-3]
    offset_pixels = bytes((byte + 1) % 256 for byte in pixel_bytes)

    return build_vbxe_packet(offset_pixels, offset_palette, gfx_mode)
