import unittest
from unittest.mock import MagicMock, patch, mock_open
import sys
import os
import socket

# Add parent directory to path to import modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from yail_image_streamer import (
    stream_YAI, 
    search_images, 
    stream_generated_image
)

class TestImageStreamer(unittest.TestCase):
    def setUp(self):
        self.mock_socket = MagicMock(spec=socket.socket)

    @patch('yail_image_streamer.requests.get')
    @patch('yail_image_streamer.Image.open')
    @patch('yail_image_streamer.convertImageToYAIL')
    @patch('yail_image_streamer.image_cache')
    def test_stream_YAI_url(self, mock_cache, mock_convert, mock_open_img, mock_get):
        # Setup mocks
        mock_response = MagicMock()
        mock_response.iter_content.return_value = [b'image_data']
        mock_get.return_value = mock_response
        
        mock_img = MagicMock()
        mock_open_img.return_value = mock_img
        
        mock_convert.return_value = b'converted_data'
        
        mock_cache.get.return_value = None # Cache miss
        
        # Run
        success = stream_YAI(self.mock_socket, 2, url="http://test.com/img.jpg")
        
        # Verify
        self.assertTrue(success)
        mock_get.assert_called_with("http://test.com/img.jpg", stream=True, timeout=5)
        mock_convert.assert_called_with(mock_img, 2)
        mock_cache.put.assert_called()
        self.mock_socket.sendall.assert_called_with(b'converted_data')

    @patch('yail_image_streamer.image_cache')
    def test_stream_YAI_cache_hit(self, mock_cache):
        # Setup cache hit
        mock_cache.get.return_value = b'cached_data'
        
        # Run
        success = stream_YAI(self.mock_socket, 2, url="http://test.com/img.jpg")
        
        # Verify
        self.assertTrue(success)
        self.mock_socket.sendall.assert_called_with(b'cached_data')
        # Should not have called requests/convert (implied by no mocks for them failing)

    @patch('yail_image_streamer.DDGS')
    def test_search_images(self, mock_ddgs_cls):
        mock_ddgs = mock_ddgs_cls.return_value
        mock_ddgs.images.return_value = [
            {'image': 'http://img1.jpg'},
            {'image': 'http://img2.jpg'}
        ]
        
        urls = search_images("cat")
        
        self.assertEqual(urls, ['http://img1.jpg', 'http://img2.jpg'])
        mock_ddgs.images.assert_called()

    @patch('yail_image_streamer.generate_image')
    @patch('yail_image_streamer.stream_YAI')
    def test_stream_generated_image(self, mock_stream_yai, mock_generate):
        mock_generate.return_value = "http://openai.com/img.png"
        mock_stream_yai.return_value = True
        
        stream_generated_image(self.mock_socket, "prompt", 2, model="dall-e-3")
        
        mock_generate.assert_called_with("prompt", model="dall-e-3")
        mock_stream_yai.assert_called_with(self.mock_socket, 2, url="http://openai.com/img.png")

if __name__ == '__main__':
    unittest.main()
