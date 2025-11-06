#!/usr/bin/env python3
"""
YAIL Client Handler Module

Handles individual client connections and command processing.
Manages the protocol between YAIL server and Atari clients.
"""

import socket
import logging
import traceback
from typing import Optional

from yail_command_parser import CommandParser, CommandContext
from yail_image_streamer import (
    stream_random_image_from_urls,
    stream_random_image_from_files,
    stream_generated_image,
    stream_generated_image_gemini,
    stream_camera_frame,
    search_images,
    send_client_response
)
from yail_image_converter import convertImageToYAIL, GRAPHICS_8
from yail_camera import capture_camera_image
from yail_server_state import server_state
from yail_gen import gen_config

logger = logging.getLogger(__name__)

# Constants
SOCKET_WAIT_TIME = 1
GRAPHICS_8 = 2
GRAPHICS_9 = 4
GRAPHICS_11 = 8
VBXE = 16
YAIL_W = 320
YAIL_H = 220


class ClientHandler:
    """Handles a single client connection."""
    
    def __init__(self, client_socket: socket.socket, thread_id: int):
        """
        Initialize client handler.
        
        Args:
            client_socket: Socket connected to client
            thread_id: Thread ID for logging
        """
        self.client_socket = client_socket
        self.thread_id = thread_id
        self.parser = CommandParser()
        self.context = CommandContext()
        self.done = False
    
    def handle(self) -> None:
        """Handle the client connection."""
        logger.info(f"Starting Connection: {self.thread_id}")
        
        # Use thread-safe state management
        connection_count = server_state.increment_connections()
        logger.info(f'Starting Connection: {connection_count}')
        
        try:
            self.client_socket.settimeout(300)  # 5 minutes timeout
            
            while not self.done:
                self._process_request()
        
        except socket.timeout:
            logger.warning(f"Client connection {self.thread_id} timed out")
        except ConnectionResetError:
            logger.warning(f"Client connection {self.thread_id} was reset by the client")
        except BrokenPipeError:
            logger.warning(f"Client connection {self.thread_id} has a broken pipe")
        except Exception as e:
            logger.error(f"Error handling client connection {self.thread_id}: {e}")
            logger.error(traceback.format_exc())
        finally:
            self._cleanup()
    
    def _process_request(self) -> None:
        """Process a single client request."""
        if len(self.context.tokens) == 0:
            request = self.client_socket.recv(1024)
            logger.info(f'{self.thread_id} Client request {request}')
            
            # Check if this looks like an HTTP request
            if request.startswith(b'GET') or request.startswith(b'POST') or \
               request.startswith(b'PUT') or request.startswith(b'DELETE') or \
               request.startswith(b'HEAD'):
                logger.warning("HTTP request detected - sending 'Not Allowed' response")
                http_response = "HTTP/1.1 403 Forbidden\r\nContent-Type: text/plain\r\nContent-Length: 11\r\n\r\nNot Allowed"
                self.client_socket.sendall(http_response.encode('utf-8'))
                self.done = True
                return
            
            # Parse command
            is_valid, tokens, error = self.parser.parse_command(request)
            
            if not is_valid:
                send_client_response(self.client_socket, error or "Invalid command", is_error=True)
                return
            
            self.context.tokens = tokens
        
        logger.info(f'{self.thread_id} Tokens {self.context.tokens}')
        
        # Dispatch command
        self._dispatch_command()
    
    def _dispatch_command(self) -> None:
        """Dispatch command to appropriate handler."""
        if not self.context.tokens:
            return
        
        command = self.context.tokens[0].lower()
        
        if command == 'video' or command == 'camera':
            self._handle_video()
        elif command == 'search':
            self._handle_search()
        elif command.startswith('gen'):
            self._handle_gen()
        elif command == 'files':
            self._handle_files()
        elif command == 'next':
            self._handle_next()
        elif command == 'gfx':
            self._handle_gfx()
        elif command == 'openai-config':
            self._handle_config()
        elif command == 'quit':
            self._handle_quit()
        else:
            self.context.tokens = []
            send_client_response(self.client_socket, "ACK!")
    
    def _handle_video(self) -> None:
        """Handle video/camera command."""
        self.context.set_mode('video')
        stream_camera_frame(self.client_socket, self.context.gfx_mode)
        self.context.tokens.pop(0)
    
    def _handle_search(self) -> None:
        """Handle search command."""
        self.context.set_mode('search')
        prompt = self.parser.extract_prompt(self.context.tokens)
        logger.info(f"Received search {prompt}")
        urls = search_images(prompt)
        self.context.set_search_urls(urls)
        stream_random_image_from_urls(self.client_socket, urls, self.context.gfx_mode)
        self.context.reset_tokens()
    
    def _handle_gen(self) -> None:
        """Handle gen/gen-gemini command."""
        self.context.set_mode('generate')
        command = self.context.tokens[0]
        
        if command.startswith('gen') and len(self.context.tokens) > 1 and command != 'gen-gemini':
            # Format: gen <model> <prompt...>
            ai_model_name = self.context.tokens[1]
            prompt = self.parser.extract_prompt(self.context.tokens, 2)
            logger.info(f"{self.thread_id} Received {command} model={ai_model_name} prompt={prompt}")
        else:
            # Format: gen <prompt...> or gen-gemini <prompt...>
            prompt = self.parser.extract_prompt(self.context.tokens)
            logger.info(f"{self.thread_id} Received {command} {prompt}")
        
        server_state.set_last_prompt(prompt)
        
        if command == 'gen-gemini':
            stream_generated_image_gemini(self.client_socket, prompt, self.context.gfx_mode)
        else:
            stream_generated_image(self.client_socket, prompt, self.context.gfx_mode)
        
        self.context.reset_tokens()
    
    def _handle_files(self) -> None:
        """Handle files command."""
        self.context.set_mode('files')
        stream_random_image_from_files(self.client_socket, self.context.gfx_mode)
        self.context.tokens.pop(0)
    
    def _handle_next(self) -> None:
        """Handle next command."""
        if self.context.client_mode == 'search':
            stream_random_image_from_urls(self.client_socket, self.context.urls, self.context.gfx_mode)
        elif self.context.client_mode == 'video':
            stream_camera_frame(self.client_socket, self.context.gfx_mode)
        elif self.context.client_mode == 'generate':
            prompt = server_state.get_last_prompt()
            if prompt:
                logger.info(f"{self.thread_id} Regenerating image with prompt: '{prompt}'")
                stream_generated_image(self.client_socket, prompt, self.context.gfx_mode)
            else:
                send_client_response(self.client_socket, "No previous prompt to regenerate", is_error=True)
        elif self.context.client_mode == 'files':
            stream_random_image_from_files(self.client_socket, self.context.gfx_mode)
        else:
            send_client_response(self.client_socket, "No previous command to repeat", is_error=True)
        
        self.context.tokens.pop(0)
    
    def _handle_gfx(self) -> None:
        """Handle gfx command."""
        self.context.tokens.pop(0)
        mode = self.parser.extract_graphics_mode(self.context.tokens)
        if mode is not None:
            self.context.set_graphics_mode(mode)
            logger.info(f"Graphics mode set to {mode}")
        else:
            send_client_response(self.client_socket, "Invalid graphics mode", is_error=True)
        self.context.tokens.pop(0)
    
    def _handle_config(self) -> None:
        """Handle openai-config command."""
        self.context.tokens.pop(0)
        
        if len(self.context.tokens) == 0:
            send_client_response(self.client_socket, f"Current OpenAI config: {gen_config}")
            return
        
        param, value = self.parser.extract_config_param(self.context.tokens)
        
        if param is None:
            send_client_response(self.client_socket, f"Current OpenAI config: {gen_config}")
            return
        
        if value is None:
            send_client_response(self.client_socket, f"Current OpenAI config: {gen_config}")
            return
        
        # Process configuration
        if param == "model":
            if gen_config.set_model(value):
                send_client_response(self.client_socket, f"OpenAI model set to {value}")
            else:
                send_client_response(self.client_socket, "Invalid model", is_error=True)
        
        elif param == "size":
            if gen_config.set_size(value):
                send_client_response(self.client_socket, f"Image size set to {value}")
            else:
                send_client_response(self.client_socket, "Invalid size", is_error=True)
        
        elif param == "quality":
            if gen_config.set_quality(value):
                send_client_response(self.client_socket, f"Image quality set to {value}")
            else:
                send_client_response(self.client_socket, "Invalid quality", is_error=True)
        
        elif param == "style":
            if gen_config.set_style(value):
                send_client_response(self.client_socket, f"Image style set to {value}")
            else:
                send_client_response(self.client_socket, "Invalid style", is_error=True)
        
        elif param == "system_prompt":
            gen_config.set_system_prompt(value)
            send_client_response(self.client_socket, f"System prompt set to {value}")
        
        else:
            send_client_response(self.client_socket, f"Unknown parameter '{param}'", is_error=True)
        
        # Consume tokens
        self.context.tokens.pop(0)
        if len(self.context.tokens) > 0:
            self.context.tokens.pop(0)
    
    def _handle_quit(self) -> None:
        """Handle quit command."""
        self.done = True
        self.context.tokens.pop(0)
    
    def _cleanup(self) -> None:
        """Clean up resources."""
        try:
            self.client_socket.close()
            logger.info(f"Closing Connection: {self.thread_id}")
            
            # Update connection counter using thread-safe state
            remaining_connections = server_state.decrement_connections()
            logger.info(f"Active connections: {remaining_connections}")
        
        except Exception as e:
            logger.error(f"Error closing client socket for connection {self.thread_id}: {e}")
        
        logger.debug(f"handle_client_connection thread exiting: {self.thread_id}")


def handle_client_connection(client_socket: socket.socket, thread_id: int) -> None:
    """
    Handle a client connection in a separate thread.
    
    Args:
        client_socket: The client socket to handle
        thread_id: The ID of this client thread for tracking
    """
    handler = ClientHandler(client_socket, thread_id)
    handler.handle()
