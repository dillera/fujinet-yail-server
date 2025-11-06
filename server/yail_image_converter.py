#!/usr/bin/env python3
"""
YAIL Image Converter Module

Handles all image format conversion for Atari graphics modes.
Converts images to YAIL binary format for streaming to Atari clients.
"""

import logging
import struct
import numpy as np
from PIL import Image
from typing import Optional

logger = logging.getLogger(__name__)

# Graphics mode constants
GRAPHICS_8 = 2    # Black & white dithered (320x220)
GRAPHICS_9 = 4    # 16-color grayscale (320x220)
GRAPHICS_11 = 8   # (reserved)
VBXE = 16         # 256-color palette (320x240)

# Memory block type constants
DL_BLOCK = 0x04
XDL_BLOCK = 0x05
PALETTE_BLOCK = 0x06
IMAGE_BLOCK = 0x07
ERROR_BLOCK = 0xFF

# Image dimensions
YAIL_W = 320
YAIL_H = 220
VBXE_W = 640
VBXE_H = 480


def prep_image_for_vbxe(image: Image.Image, target_width: int = YAIL_W, 
                        target_height: int = YAIL_H) -> Image.Image:
    """
    Prepare image for VBXE mode by resizing and centering.
    
    Preserves aspect ratio by fitting to width or height and centering
    on a black background.
    
    Args:
        image: PIL Image to process
        target_width: Target width (default: 320)
        target_height: Target height (default: 220)
    
    Returns:
        Resized and centered image
    """
    logger.info(f'Image size: {image.size}')

    # Calculate the new size preserving the aspect ratio
    image_ratio = image.width / image.height
    target_ratio = target_width / target_height

    if image_ratio > target_ratio:
        # Image is wider than target, fit to width
        new_width = target_width
        new_height = int(target_width / image_ratio)
    else:
        # Image is taller than target, fit to height
        new_width = int(target_height * image_ratio)
        new_height = target_height

    # Resize the image
    image = image.resize((new_width, new_height), Image.BILINEAR)
    logger.info(f'Image new size: {image.size}')

    # Create a new image with the target size and a black background
    new_image = Image.new('RGB', (target_width, target_height), (0, 0, 0))

    # Calculate the position to paste the resized image onto the black background
    paste_x = (target_width - image.width) // 2
    paste_y = (target_height - image.height) // 2

    # Paste the resized image onto the black background
    new_image.paste(image, (paste_x, paste_y))

    return new_image


def fix_aspect(image: Image.Image, crop: bool = False) -> Image.Image:
    """
    Fix image aspect ratio to match YAIL display.
    
    Args:
        image: PIL Image to process
        crop: If True, crop to aspect ratio. If False, pad with black.
    
    Returns:
        Image with corrected aspect ratio
    """
    aspect = YAIL_W / YAIL_H   # YAIL aspect ratio
    aspect_i = 1 / aspect
    w = image.size[0]
    h = image.size[1]
    img_aspect = w / h

    if crop:
        if img_aspect > aspect:  # wider than YAIL aspect
            new_width = int(h * aspect)
            new_width_diff = w - new_width
            new_width_diff_half = int(new_width_diff / 2)
            image = image.crop((new_width_diff_half, 0, w - new_width_diff_half, h))
        else:                    # taller than YAIL aspect
            new_height = int(w * aspect_i)
            new_height_diff = h - new_height
            new_height_diff_half = int(new_height_diff / 2)
            image = image.crop((0, new_height_diff_half, w, h - new_height_diff_half))
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
    """
    Convert image to 1-bit dithered (black & white).
    
    Args:
        image: PIL Image to dither
    
    Returns:
        Dithered 1-bit image
    """
    return image.convert('1')


def pack_bits(image: Image.Image) -> np.ndarray:
    """
    Pack dithered image bits into bytes.
    
    Converts 1-bit image to packed byte array where each byte
    contains 8 pixels.
    
    Args:
        image: 1-bit PIL Image
    
    Returns:
        Packed bit array
    """
    bits = np.array(image)
    return np.packbits(bits, axis=1)


def pack_shades(image: Image.Image) -> np.ndarray:
    """
    Convert image to 16-color grayscale packed format.
    
    Reduces image to 16 colors using Floyd-Steinberg dithering,
    then packs two 4-bit pixels per byte.
    
    Args:
        image: PIL Image to convert
    
    Returns:
        Packed 4-bit grayscale array
    """
    yail = image.resize((int(YAIL_W / 4), YAIL_H), Image.LANCZOS)
    yail = yail.convert(dither=Image.FLOYDSTEINBERG, colors=16)

    im_matrix = np.array(yail)
    im_values = im_matrix[:, :]

    evens = im_values[:, ::2]
    odds = im_values[:, 1::2]

    # Each byte holds 2 pixels. Upper four bits for left pixel, lower four bits for right pixel.
    evens_scaled = (evens >> 4) << 4  # left pixel
    odds_scaled = (odds >> 4)          # right pixel

    # Combine the two 4-bit values into a single byte
    combined = evens_scaled + odds_scaled

    return combined.astype('int8')


def convertToYai(image_data: bytearray, gfx_mode: int) -> bytearray:
    """
    Convert image data to YAIL format for graphics modes 8 and 9.
    
    Binary Format:
        [0:3]   Version (1, 1, 0)
        [3]     Graphics mode (8 or 9)
        [4]     Memory block type (3)
        [5:7]   Image size (little-endian uint16)
        [7:]    Image data
    
    Args:
        image_data: Packed image data (bits or nibbles)
        gfx_mode: Graphics mode (GRAPHICS_8 or GRAPHICS_9)
    
    Returns:
        YAIL format binary data
    """
    ttlbytes = image_data.shape[0] * image_data.shape[1]

    image_yai = bytearray()
    image_yai += bytes([1, 1, 0])            # version
    image_yai += bytes([gfx_mode])           # Gfx mode (8, 9)
    image_yai += bytes([3])                  # Memory block type
    image_yai += struct.pack("<H", ttlbytes) # num bytes height x width
    image_yai += bytearray(image_data)       # image

    logger.debug(f'YAI size: {len(image_yai)}')

    return image_yai


def convertToYaiVBXE(image_data: bytes, palette_data: bytes, gfx_mode: int) -> bytearray:
    """
    Convert image data to YAIL format for VBXE (graphics mode 16).
    
    VBXE uses 256-color palette mode with special requirements:
    - Palette entries are offset by 1 (entry 0 is reserved)
    - Image data byte values are offset by 1 (0 maps to palette entry 1)
    - This allows palette entry 0 to be used for transparency/background
    
    Binary Format:
        [0:3]   Version (1, 4, 0)
        [3]     Graphics mode (16 for VBXE)
        [4]     Number of memory blocks (2: palette + image)
        [5]     Block type (0x06 for palette)
        [6:10]  Palette size (little-endian uint32)
        [10:778]    Palette data (768 bytes)
        [778]   Block type (0x07 for image)
        [779:783]   Image size (little-endian uint32)
        [783:]  Image data
    
    Args:
        image_data: 8-bit indexed image data (320x240 = 76,800 bytes)
        palette_data: RGB palette data (256 colors * 3 bytes = 768 bytes)
        gfx_mode: Graphics mode identifier (16 for VBXE)
    
    Returns:
        YAIL format binary data with palette and image
    """
    logger.debug(f'Image data size: {len(image_data)}')
    logger.debug(f'Palette data size: {len(palette_data)}')

    image_yai = bytearray()
    image_yai += bytes([1, 4, 0])            # version
    image_yai += bytes([gfx_mode])           # gfx mode (16 for VBXE)
    image_yai += struct.pack("<B", 2)        # number of memory blocks (palette + image)
    
    # Palette block
    image_yai += bytes([PALETTE_BLOCK])             # Memory block type (0x06)
    image_yai += struct.pack("<I", len(palette_data)) # palette size
    image_yai += bytearray(palette_data)  # palette data
    
    # Image block
    image_yai += bytes([IMAGE_BLOCK])                  # Memory block type (0x07)
    image_yai += struct.pack("<I", len(image_data)) # image size
    image_yai += bytearray(image_data)       # image data

    logger.debug(f'YAI size: {len(image_yai)}')

    return image_yai


def createErrorPacket(error_message: str, gfx_mode: int) -> bytearray:
    """
    Create an error packet to send to client.
    
    Args:
        error_message: Error message text
        gfx_mode: Graphics mode
    
    Returns:
        Error packet in YAIL format
    """
    logger.debug(f'Error message length: {len(error_message)}')

    error_packets = bytearray()
    error_packets += bytes([1, 4, 0])                      # version
    error_packets += bytes([gfx_mode])                     # Gfx mode (8, 9)
    error_packets += struct.pack("<B", 1)                  # number of memory blocks
    error_packets += bytes([ERROR_BLOCK])                  # Memory block type
    error_packets += struct.pack("<I", len(error_message)) # error message size
    error_packets += bytearray(error_message)              # error

    return error_packets


def convertImageToYAIL(image: Image.Image, gfx_mode: int) -> bytearray:
    """
    Convert PIL Image to YAIL format for the specified graphics mode.
    
    Handles three graphics modes:
    - GRAPHICS_8 (2): Black & white dithered (320x220)
    - GRAPHICS_9 (4): 16-color grayscale (320x220)
    - VBXE (16): 256-color palette (320x240)
    
    Args:
        image: PIL Image to convert
        gfx_mode: Target graphics mode
    
    Returns:
        YAIL format binary data ready to stream to client
    """
    # Log information about the source image
    logger.debug(f'Source Image size: {image.size}')
    logger.debug(f'Source Image mode: {image.mode}')
    logger.debug(f'Source Image format: {image.format}')
    logger.debug(f'Source Image info: {image.info}')

    if gfx_mode == GRAPHICS_8 or gfx_mode == GRAPHICS_9:
        gray = image.convert(mode='L')
        gray = fix_aspect(gray)
        gray = gray.resize((YAIL_W, YAIL_H), Image.LANCZOS)

        logger.debug(f'Processed Image size: {image.size}')
        logger.debug(f'Processed Image mode: {image.mode}')
        logger.debug(f'Processed Image format: {image.format}')
        logger.debug(f'Processed Image info: {image.info}')

        if gfx_mode == GRAPHICS_8:
            gray_dithered = dither_image(gray)
            image_data = pack_bits(gray_dithered)
        elif gfx_mode == GRAPHICS_9:
            image_data = pack_shades(gray)

        image_yai = convertToYai(image_data, gfx_mode)

    else:  # gfx_mode == VBXE
        # Make the image fit our screen format but preserve its aspect ratio
        image_resized = prep_image_for_vbxe(image, target_width=320, target_height=240)
        # Convert the image to use a palette
        image_resized = image_resized.convert('P', palette=Image.ADAPTIVE, colors=256)
        logger.info(f'Image size: {image_resized.size}')
        
        # Get the palette
        palette = image_resized.getpalette()
        # Get the image data
        image_resized = image_resized.tobytes()
        logger.info(f'Image data size: {len(image_resized)}')
        
        # Offset the palette entries by one
        offset_palette = [0] * 3 + palette[:-3]
        # Offset the image data by one
        offset_image_data = bytes((byte + 1) % 256 for byte in image_resized)

        image_yai = convertToYaiVBXE(offset_image_data, offset_palette, gfx_mode)

    return image_yai
