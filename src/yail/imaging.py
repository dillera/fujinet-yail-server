"""Image conversion pipeline: PIL image -> Atari-native YAI byte stream.

The numeric behavior (resampling filters, dithering, bit packing) is frozen
to remain byte-identical with the legacy server output.
"""
import logging
from pathlib import Path

import numpy as np
from PIL import Image, ImageEnhance, ImageOps

from yail.protocol import (
    GRAPHICS_8,
    GRAPHICS_9,
    GRAPHICS_10,
    GRAPHICS_11,
    GRAPHICS_15,
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


# Graphics 15 (ANTIC E) gray levels for pixel values %00-%11.  The client
# programs COLBK=0x00, PF0=0x06, PF1=0x0E, PF2=0x03 (PF1 white / PF2 dark
# so the mode 0 console stays readable); RGB sampled from atari800's
# default NTSC palette gray ramp at those luminances.
GR15_GRAYS = [0, 171, 255, 89]

# Full 256-entry GTIA palette (16 hues x 16 luminances) from atari800's
# default NTSC palette; the byte index is the Atari color value the client
# pokes into a color register (hue<<4 | luminance).
ATARI_NTSC_PALETTE = np.frombuffer(
    (Path(__file__).parent / "atari_ntsc.act").read_bytes(), dtype=np.uint8
).reshape(256, 3).astype(np.int32)


def _to_ycc(rgb: np.ndarray) -> np.ndarray:
    """BT.601 RGB -> (Y, Cb, Cr), float."""
    rgb = np.asarray(rgb, dtype=np.float64)
    y = rgb @ np.array([0.299, 0.587, 0.114])
    cb = (rgb[..., 2] - y) * 0.564
    cr = (rgb[..., 0] - y) * 0.713
    return np.stack([y, cb, cr], axis=-1)


# Chroma errors weigh more than luma when snapping to the GTIA palette:
# the final dither pass can recover brightness but never hue/saturation,
# and plain RGB distance drifts toward the palette's washed-out entries.
GR10_CHROMA_WEIGHT = 4.0

_PALETTE_YCC = _to_ycc(ATARI_NTSC_PALETTE)


def nearest_atari_color(rgb) -> int:
    """Return the Atari color byte perceptually closest to rgb."""
    diff = _PALETTE_YCC - _to_ycc(rgb)
    dist = diff[:, 0] ** 2 + GR10_CHROMA_WEIGHT * (diff[:, 1] ** 2 + diff[:, 2] ** 2)
    return int(np.argmin(dist))


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


def pack_quads(image: Image.Image) -> np.ndarray:
    """Pack a grayscale image into Graphics 15 bytes (four 2-bit pixels/byte).

    ANTIC E is 160 pixels wide; each byte holds four pixels, leftmost in
    the top bits.  Pixel values index the client's COLBK/PF0/PF1/PF2 gray
    ramp (GR15_GRAYS), which is not monotonically bright, so quantization
    targets the actual displayed grays.
    """
    yail = image.resize((int(YAIL_W / 2), YAIL_H), Image.LANCZOS)
    # Per-image tone stretch: with only four grays, dynamic range matters
    # more than fidelity to the source's absolute levels.
    yail = ImageOps.autocontrast(yail, cutoff=1)

    palette_image = Image.new("P", (1, 1))
    palette_image.putpalette([g for gray in GR15_GRAYS for g in (gray,) * 3])
    indexed = yail.convert("RGB").quantize(
        palette=palette_image, dither=Image.FLOYDSTEINBERG
    )

    im_values = np.array(indexed).astype("uint8")
    combined = (
        (im_values[:, ::4] << 6)
        | (im_values[:, 1::4] << 4)
        | (im_values[:, 2::4] << 2)
        | im_values[:, 3::4]
    )
    return combined.astype("uint8")


# Graphics 10 tuning knobs.
GR10_AUTOCONTRAST_CUTOFF = 1     # % of histogram clipped per end before quantizing
GR10_SATURATION = 1.5            # chroma boost: median-cut centroids average away
                                 # saturation and GTIA hues need strong signals
GR10_CANDIDATE_COLORS = (9, 12, 16, 24, 32)


def pack_9color(image: Image.Image) -> tuple[bytes, bytes]:
    """Quantize an RGB image for Graphics 10: adaptive 9-color palette.

    Returns (packed_pixels, palette).  Pixel values 0-8 select the GTIA
    mode 10 color sources in register order P0-P3, PF0-PF3, BAK; the
    9-byte palette holds the Atari color values (hue<<4|lum) the client
    pokes into those registers.  The palette is sorted darkest-first
    because GTIA renders borders (and forced-blank pixels) in P0's color.

    Palette selection works in displayed-color space: median-cut
    centroids are snapped to the GTIA palette and deduplicated (several
    centroids often snap to one GTIA color), widening the candidate set
    until nine distinct GTIA colors are found.  The final dither then
    runs against the snapped colors the Atari actually shows, so the
    error diffusion corrects toward real output instead of ideal
    centroids that don't exist on screen.
    """
    yail = image.resize((int(YAIL_W / 4), YAIL_H), Image.LANCZOS)
    yail = ImageOps.autocontrast(yail, cutoff=GR10_AUTOCONTRAST_CUTOFF)
    yail = ImageEnhance.Color(yail).enhance(GR10_SATURATION)

    chosen: list[int] = []
    for candidates in GR10_CANDIDATE_COLORS:
        quantized = yail.quantize(colors=candidates, dither=Image.NONE)
        pal = np.array(
            quantized.getpalette()[: candidates * 3], dtype=np.int32
        ).reshape(candidates, 3)
        counts = np.bincount(
            np.asarray(quantized, dtype=np.int64).ravel(), minlength=candidates
        )
        chosen = []
        for i in np.argsort(-counts):            # most-used colors first
            if counts[i] == 0:
                break
            color = nearest_atari_color(pal[i])
            if color not in chosen:
                chosen.append(color)
            if len(chosen) == 9:
                break
        if len(chosen) == 9:
            break
    while len(chosen) < 9:                       # low-color sources: pad black
        chosen.append(0)

    displayed = ATARI_NTSC_PALETTE[chosen]
    luma = displayed @ np.array([299, 587, 114])
    order = np.argsort(luma, kind="stable")      # darkest palette entry first
    chosen = [chosen[i] for i in order]
    displayed = ATARI_NTSC_PALETTE[chosen]

    palette_image = Image.new("P", (1, 1))
    palette_image.putpalette([int(v) for rgb in displayed for v in rgb])
    indexed = yail.quantize(palette=palette_image, dither=Image.FLOYDSTEINBERG)
    indices = np.array(indexed, dtype=np.uint8)

    evens = indices[:, ::2]
    odds = indices[:, 1::2]
    packed = ((evens << 4) | odds).astype("uint8")
    return packed.tobytes(), bytes(chosen)


def convert_image_to_yail(image: Image.Image, gfx_mode: int) -> bytearray:
    """Convert a PIL image to a complete YAI packet for the given mode."""
    logger.debug(f"Source image size={image.size} mode={image.mode} format={image.format}")

    if gfx_mode in (GRAPHICS_8, GRAPHICS_9, GRAPHICS_15):
        gray = image.convert(mode="L")
        gray = fix_aspect(gray)
        gray = gray.resize((YAIL_W, YAIL_H), Image.LANCZOS)

        if gfx_mode == GRAPHICS_8:
            image_data = pack_bits(dither_image(gray))
        elif gfx_mode == GRAPHICS_15:
            image_data = pack_quads(gray)
        else:
            image_data = pack_shades(gray)

        return build_yai_packet(image_data, gfx_mode)

    if gfx_mode == GRAPHICS_11:
        rgb = image.convert(mode="RGB")
        rgb = fix_aspect(rgb)
        rgb = rgb.resize((YAIL_W, YAIL_H), Image.LANCZOS)
        return build_yai_packet(pack_hues(rgb), gfx_mode)

    if gfx_mode == GRAPHICS_10:
        rgb = image.convert(mode="RGB")
        rgb = fix_aspect(rgb)
        rgb = rgb.resize((YAIL_W, YAIL_H), Image.LANCZOS)
        pixels, palette = pack_9color(rgb)
        # v1.4 two-block packet: palette block then image block, like VBXE
        # but with 9 Atari color bytes instead of a 768-byte RGB palette.
        return build_vbxe_packet(pixels, palette, gfx_mode)

    # VBXE: 320x240 with a 256-color adaptive palette.
    resized = prep_image_for_vbxe(image, target_width=VBXE_W, target_height=VBXE_H)
    resized = resized.convert("P", palette=Image.ADAPTIVE, colors=256)
    palette = resized.getpalette()
    pixel_bytes = resized.tobytes()

    # Shift palette and pixel indices by one: VBXE entry 0 stays black.
    offset_palette = [0] * 3 + palette[:-3]
    offset_pixels = bytes((byte + 1) % 256 for byte in pixel_bytes)

    return build_vbxe_packet(offset_pixels, offset_palette, gfx_mode)
