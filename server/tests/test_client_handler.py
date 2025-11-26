import unittest
from unittest.mock import MagicMock, patch
import sys
import os
import socket

# Add parent directory to path to import modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from yail_client_handler import ClientHandler

class TestClientHandler(unittest.TestCase):
    def setUp(self):
        self.mock_socket = MagicMock(spec=socket.socket)
        self.handler = ClientHandler(self.mock_socket, 1)

    @patch('yail_client_handler.server_state')
    def test_initialization(self, mock_server_state):
        self.assertEqual(self.handler.thread_id, 1)
        self.assertFalse(self.handler.done)
        self.assertIsNotNone(self.handler.parser)
        self.assertIsNotNone(self.handler.context)

    @patch('yail_client_handler.server_state')
    def test_handle_http_request(self, mock_server_state):
        # Mock receiving an HTTP GET request
        self.mock_socket.recv.return_value = b"GET / HTTP/1.1\r\nHost: localhost\r\n\r\n"
        
        self.handler._process_request()
        
        # Should have sent 403 response
        self.mock_socket.sendall.assert_called_once()
        args = self.mock_socket.sendall.call_args[0][0]
        self.assertIn(b"HTTP/1.1 403 Forbidden", args)
        self.assertTrue(self.handler.done)

    @patch('yail_client_handler.send_client_response')
    def test_invalid_command(self, mock_send_response):
        # Mock receiving invalid command
        self.mock_socket.recv.return_value = b"invalidcommand\r\n"
        
        self.handler._process_request()
        
        # Should have sent error response
        mock_send_response.assert_called()
        call_args = mock_send_response.call_args
        self.assertTrue(call_args[1]['is_error']) # Check is_error=True

    @patch('yail_client_handler.yail_gen')
    @patch('yail_client_handler.stream_generated_image')
    @patch('yail_client_handler.server_state')
    def test_handle_gen_command(self, mock_server_state, mock_stream_gen, mock_yail_gen):
        # Mock gen_config
        mock_config = MagicMock()
        mock_config.is_valid_model.return_value = False # "a" is not a model
        mock_yail_gen.gen_config = mock_config
        
        # Mock receiving gen command
        self.mock_socket.recv.return_value = b"gen a cat\r\n"
        
        self.handler._process_request()
        
        # Should set mode
        self.assertEqual(self.handler.context.client_mode, 'generate')
        
        # Should update server state last prompt
        mock_server_state.set_last_prompt.assert_called_with("a cat")
        
        # Should call stream_generated_image
        mock_stream_gen.assert_called_once_with(self.mock_socket, "a cat", 2, model=None)

    @patch('yail_client_handler.yail_gen')
    @patch('yail_client_handler.stream_generated_image')
    @patch('yail_client_handler.server_state')
    def test_handle_gen_command_with_model(self, mock_server_state, mock_stream_gen, mock_yail_gen):
        # Mock gen_config
        mock_config = MagicMock()
        mock_config.is_valid_model.side_effect = lambda m: m == "dall-e-3"
        mock_yail_gen.gen_config = mock_config
        
        # Mock receiving gen command
        self.mock_socket.recv.return_value = b"gen dall-e-3 a cat\r\n"
        
        self.handler._process_request()
        
        # Should update server state last prompt
        mock_server_state.set_last_prompt.assert_called_with("a cat")
        
        # Should call stream_generated_image
        mock_stream_gen.assert_called_once_with(self.mock_socket, "a cat", 2, model="dall-e-3")
        
    @patch('yail_client_handler.stream_random_image_from_urls')
    @patch('yail_client_handler.search_images')
    def test_handle_search_command(self, mock_search, mock_stream_urls):
        # Mock receiving search command
        self.mock_socket.recv.return_value = b"search dogs\r\n"
        mock_search.return_value = ["http://test.com/dog.jpg"]
        
        self.handler._process_request()
        
        # Should set mode
        self.assertEqual(self.handler.context.client_mode, 'search')
        
        # Should call search
        mock_search.assert_called_with("dogs")
        
        # Should stream
        mock_stream_urls.assert_called_once()

    def test_handle_quit(self):
        self.handler.context.tokens = ["quit"]
        self.handler._dispatch_command()
        self.assertTrue(self.handler.done)

    @patch('yail_client_handler.server_state')
    def test_cleanup(self, mock_server_state):
        self.handler._cleanup()
        self.mock_socket.close.assert_called_once()
        mock_server_state.decrement_connections.assert_called_once()

if __name__ == '__main__':
    unittest.main()
