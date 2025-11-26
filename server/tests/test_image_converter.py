import unittest
import sys
import os
import numpy as np
from PIL import Image
import struct

# Add parent directory to path to import modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from yail_image_converter import (
    fix_aspect, 
    dither_image, 
    pack_bits, 
    pack_shades, 
    convertToYai, 
    createErrorPacket,
    convertImageToYAIL,
    prep_image_for_vbxe,
    GRAPHICS_8,
    GRAPHICS_9,
    VBXE,
    YAIL_W,
    YAIL_H,
    ERROR_BLOCK
)

class TestImageConverter(unittest.TestCase):
    def setUp(self):
        # Create a simple test image (gradient)
        self.width = 100
        self.height = 100
        self.image = Image.new('RGB', (self.width, self.height), color='red')
        # Create a gradient
        for y in range(self.height):
            for x in range(self.width):
                self.image.putpixel((x, y), (x * 2, y * 2, 128))
                
    def test_fix_aspect(self):
        """Test aspect ratio fixing."""
        # Create wide image
        wide = Image.new('RGB', (200, 50))
        fixed = fix_aspect(wide, crop=False)
        
        # Should be padded to match aspect ratio
        # Target aspect is 320/220 = 1.45
        # Wide aspect is 4.0
        # Should fit to width, so height increases
        self.assertEqual(fixed.size[0], 200)
        self.assertGreater(fixed.size[1], 50)
        
        # Test cropping
        fixed_crop = fix_aspect(wide, crop=True)
        self.assertEqual(fixed_crop.size[1], 50)
        self.assertLess(fixed_crop.size[0], 200)

    def test_dither_image(self):
        """Test dithering to 1-bit."""
        img = self.image.convert('L')
        dithered = dither_image(img)
        self.assertEqual(dithered.mode, '1')
        self.assertEqual(dithered.size, img.size)

    def test_pack_bits(self):
        """Test bit packing."""
        # Create known 1-bit image 8x1 pixels
        # 1 0 1 0 1 0 1 0  -> 0xAA (170)
        data = [1, 0, 1, 0, 1, 0, 1, 0]
        img = Image.new('1', (8, 1))
        img.putdata(data)
        
        packed = pack_bits(img)
        self.assertEqual(packed.shape, (1, 1))
        self.assertEqual(packed[0][0], 170)

    def test_pack_shades(self):
        """Test 4-bit shade packing."""
        # Create grayscale image 8x1
        # We need to mock the resize/convert flow inside pack_shades essentially
        # But let's just test the function with a prepared image
        # pack_shades does resize and convert internally, so we pass a raw image
        
        # It resizes to YAIL_W/4 (80) x YAIL_H (220)
        # Let's just verify output shape and type
        # Note: pack_shades is typically called with a Grayscale ('L') image in the main flow
        gray_image = self.image.convert('L')
        packed = pack_shades(gray_image)
        
        expected_width = int(YAIL_W / 4 / 2) # 2 pixels per byte
        # Wait, logic is: resize to W/4, then pack.
        # Actually pack_shades implementation:
        # yail = image.resize((int(YAIL_W / 4), YAIL_H), Image.LANCZOS) -> 80x220
        # evens = im_values[:, ::2] -> 40 columns
        # odds = im_values[:, 1::2] -> 40 columns
        # combined -> 40x220
        
        self.assertEqual(packed.shape, (YAIL_H, 40))
        self.assertEqual(packed.dtype, 'int8')

    def test_convert_to_yai_graphics8(self):
        """Test full conversion for Graphics 8."""
        result = convertImageToYAIL(self.image, GRAPHICS_8)
        
        # Check header
        self.assertEqual(result[0:3], bytes([1, 1, 0])) # Version
        self.assertEqual(result[3], GRAPHICS_8)         # Mode
        self.assertEqual(result[4], 3)                  # Block type
        
        # Check size
        # GRAPHICS_8 is 320x220. 1 bit per pixel.
        # 320 * 220 / 8 = 8800 bytes
        size = struct.unpack("<H", result[5:7])[0]
        self.assertEqual(size, 8800)
        
        # Total size = 7 header bytes + 8800 data bytes
        self.assertEqual(len(result), 8807)

    def test_convert_to_yai_graphics9(self):
        """Test full conversion for Graphics 9."""
        result = convertImageToYAIL(self.image, GRAPHICS_9)
        
        # Check header
        self.assertEqual(result[0:3], bytes([1, 1, 0])) # Version
        self.assertEqual(result[3], GRAPHICS_9)         # Mode
        
        # Check size
        # GRAPHICS_9 packs into 4-bit pixels, but resized to 1/4 width?
        # pack_shades resizes to width 80. 
        # 80 * 220 pixels = 17600 pixels.
        # Each byte is 2 pixels -> 8800 bytes.
        size = struct.unpack("<H", result[5:7])[0]
        self.assertEqual(size, 8800)
        
        self.assertEqual(len(result), 8807)

    def test_convert_to_yai_vbxe(self):
        """Test full conversion for VBXE."""
        result = convertImageToYAIL(self.image, VBXE)
        
        # Check header
        self.assertEqual(result[0:3], bytes([1, 4, 0])) # Version
        self.assertEqual(result[3], VBXE)               # Mode
        
        # Block count
        block_count = struct.unpack("<B", result[4:5])[0]
        self.assertEqual(block_count, 2)
        
        # Check Palette Block
        self.assertEqual(result[5], 0x06) # PALETTE_BLOCK
        pal_size = struct.unpack("<I", result[6:10])[0]
        # Palette should be 256 * 3 = 768 bytes
        self.assertEqual(pal_size, 768)
        
        # Check Image Block
        # 5 (header) + 5 (pal header) + 768 (pal data) = 778
        self.assertEqual(result[778], 0x07) # IMAGE_BLOCK
        
        # VBXE Image size
        # prep_image_for_vbxe uses target_width=320, target_height=240
        # 8 bit per pixel = 320 * 240 = 76800 bytes
        img_size = struct.unpack("<I", result[779:783])[0]
        self.assertEqual(img_size, 76800)
        
        # Total expected length
        # 5 + 5 + 768 + 5 + 76800 = 77583
        self.assertEqual(len(result), 77583)

    def test_create_error_packet(self):
        """Test error packet creation."""
        msg = "Test Error"
        packet = createErrorPacket(msg, GRAPHICS_8)
        
        self.assertEqual(packet[3], GRAPHICS_8)
        self.assertEqual(packet[5], ERROR_BLOCK)
        
        msg_len = struct.unpack("<I", packet[6:10])[0]
        self.assertEqual(msg_len, len(msg))
        self.assertEqual(packet[10:], msg.encode('utf-8'))

if __name__ == '__main__':
    unittest.main()
