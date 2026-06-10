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
    VBXE_H,
    VBXE_W,
    YAIL_H,
    YAIL_W,
    build_vbxe_packet,
    build_yai_packet,
)

logger = logging.getLogger(__name__)


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
            background = Image.new("L", (w, new_height))
            background.paste(image, (0, int((new_height - h) / 2)))
            image = background
        else:                    # taller than YAIL aspect
            new_width = int(h * aspect)
            background = Image.new("L", (new_width, h))
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

    # VBXE: 320x240 with a 256-color adaptive palette.
    resized = prep_image_for_vbxe(image, target_width=VBXE_W, target_height=VBXE_H)
    resized = resized.convert("P", palette=Image.ADAPTIVE, colors=256)
    palette = resized.getpalette()
    pixel_bytes = resized.tobytes()

    # Shift palette and pixel indices by one: VBXE entry 0 stays black.
    offset_palette = [0] * 3 + palette[:-3]
    offset_pixels = bytes((byte + 1) % 256 for byte in pixel_bytes)

    return build_vbxe_packet(offset_pixels, offset_palette, gfx_mode)
