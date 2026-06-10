"""YAIL wire protocol: packet construction and shared constants.

The byte-level format here is frozen; existing client binaries in the wild
parse it exactly as produced by the legacy server. See PROTOCOL.md.
"""
import struct

import numpy as np

# Graphics mode identifiers exchanged with the client via the `gfx` command
# and echoed back in every packet header.
GRAPHICS_8 = 2
GRAPHICS_9 = 4
GRAPHICS_15 = 6
GRAPHICS_11 = 8
VBXE = 16

# Target raster geometry for ANTIC modes (320x220, 40 bytes per line).
YAIL_W = 320
YAIL_H = 220
# VBXE palette mode geometry.
VBXE_W = 320
VBXE_H = 240

# Memory block type tokens.
LEGACY_BLOCK = 0x03  # v1.1 single-block image payload
DL_BLOCK = 0x04
XDL_BLOCK = 0x05
PALETTE_BLOCK = 0x06
IMAGE_BLOCK = 0x07
ERROR_BLOCK = 0xFF

VERSION_V11 = bytes([1, 1, 0])
VERSION_V14 = bytes([1, 4, 0])


def build_yai_packet(image_data: np.ndarray, gfx_mode: int) -> bytearray:
    """Build a v1.1 single-block packet for Graphics 8/9 framebuffer data."""
    total_bytes = image_data.shape[0] * image_data.shape[1]

    packet = bytearray()
    packet += VERSION_V11
    packet += bytes([gfx_mode])
    packet += bytes([LEGACY_BLOCK])
    packet += struct.pack("<H", total_bytes)
    packet += bytearray(image_data)
    return packet


def build_vbxe_packet(image_data: bytes, palette_data: bytes, gfx_mode: int) -> bytearray:
    """Build a v1.4 multi-block packet carrying a palette and image data."""
    packet = bytearray()
    packet += VERSION_V14
    packet += bytes([gfx_mode])
    packet += struct.pack("<B", 2)  # number of memory blocks
    packet += bytes([PALETTE_BLOCK])
    packet += struct.pack("<I", len(palette_data))
    packet += bytearray(palette_data)
    packet += bytes([IMAGE_BLOCK])
    packet += struct.pack("<I", len(image_data))
    packet += bytearray(image_data)
    return packet


def build_error_packet(error_message: bytes, gfx_mode: int) -> bytearray:
    """Build a v1.4 packet with a single ERROR_BLOCK carrying a message."""
    packet = bytearray()
    packet += VERSION_V14
    packet += bytes([gfx_mode])
    packet += struct.pack("<B", 1)  # number of memory blocks
    packet += bytes([ERROR_BLOCK])
    packet += struct.pack("<I", len(error_message))
    packet += bytearray(error_message)
    return packet
