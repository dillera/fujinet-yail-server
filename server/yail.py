#!/usr/bin/env python3
"""
YAIL (Yet Another Image Loader) Server

Main server entry point. Handles server initialization, configuration,
and client connection management.

The server streams images to Atari 8-bit computers in native graphics formats.
Supports multiple image sources: AI generation, web search, local files, webcam.

Architecture:
  - yail.py: Main server and configuration (this file)
  - yail_image_converter.py: Image format conversion for Atari graphics modes
  - yail_image_streamer.py: Image streaming from various sources
  - yail_command_parser.py: Client command parsing and validation
  - yail_client_handler.py: Individual client connection handling
  - yail_server_state.py: Thread-safe state management
  - yail_gen.py: Image generation (OpenAI DALL-E, Google Gemini)
  - yail_camera.py: Webcam capture functionality
"""

import os
import sys
import argparse
import logging
import socket
import signal
from typing import List, Union, Callable
from threading import Thread

# Import modular components
from yail_gen import initialize_gen_config, OPENAI_AVAILABLE, GEMINI_AVAILABLE
from yail_camera import init_camera, shutdown_camera, PYGAME_AVAILABLE
from yail_server_state import server_state
from yail_client_handler import handle_client_connection

# Set up logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Constants
BIND_IP = '0.0.0.0'
BIND_PORT = 5556
DEFAULT_EXTENSIONS = ['.jpg', '.jpeg', '.gif', '.png']


def process_files(input_path: Union[str, List[str]], 
                  extensions: List[str], 
                  callback: Callable[[str], None]) -> None:
    """
    Process files from input path and call callback for each matching file.
    
    Args:
        input_path: Directory path or list of file paths
        extensions: List of file extensions to include
        callback: Function to call for each matching file
    """
    extensions = [ext.lower() if ext.startswith('.') else f'.{ext.lower()}' for ext in extensions]

    def process_file(file_path: str):
        _, ext = os.path.splitext(file_path)
        if ext.lower() in extensions:
            callback(file_path)

    if isinstance(input_path, list):
        for file_path in input_path:
            process_file(file_path)
    elif os.path.isdir(input_path):
        for root, _, files in os.walk(input_path):
            for file in files:
                process_file(os.path.join(root, file))
    else:
        raise ValueError("input_path must be a directory path or a list of file paths.")


def add_filename_callback(file_path: str) -> None:
    """Callback to add a filename to server state."""
    logger.info(f"Processing file: {file_path}")
    server_state.add_filename(file_path)


def main():
    """Main function to start the YAIL server."""
    active_threads = []
    
    # Signal handler for graceful shutdown
    def signal_handler(sig, frame):
        logger.info("Shutting down YAIL server...")
        
        # Stop the camera
        shutdown_camera()
        
        # Close the server socket
        if 'server' in locals():
            try:
                server.close()
                logger.info("Server socket closed")
            except Exception as e:
                logger.error(f"Error closing server socket: {e}")
        
        # Wait for all client threads to finish
        if active_threads:
            logger.info(f"Waiting for {len(active_threads)} client threads to finish...")
            for thread in active_threads:
                if thread.is_alive():
                    thread.join(timeout=1.0)
        
        logger.info("YAIL server shutdown complete")
        sys.exit(0)
    
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)   # Ctrl+C
    signal.signal(signal.SIGTERM, signal_handler)  # Termination signal
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='YAIL Server - Stream images to Atari 8-bit computers')
    parser.add_argument('--paths', nargs='*', help='Directory containing images to stream')
    parser.add_argument('--extensions', nargs='*', default=DEFAULT_EXTENSIONS, 
                       help='File extensions to include')
    parser.add_argument('--camera', nargs='?', help='Camera device to use')
    parser.add_argument('--port', type=int, help='Port to listen on')
    parser.add_argument('--loglevel', help='Logging level (DEBUG, INFO, WARN, ERROR, CRITICAL)')
    parser.add_argument('--openai-api-key', help='OpenAI API key')
    parser.add_argument('--gen-model', help='Image generation model (dall-e-3, dall-e-2, or gemini)')
    parser.add_argument('--openai-size', help='Image size for DALL-E models')
    parser.add_argument('--openai-quality', help='Image quality for DALL-E models')
    parser.add_argument('--openai-style', help='Image style for DALL-E models')
    args = parser.parse_args()

    # Process file paths
    if args.paths:
        if len(args.paths) == 1 and os.path.isdir(args.paths[0]):
            logger.info(f"Processing files in directory: {args.paths[0]}")
            process_files(args.paths[0], args.extensions, add_filename_callback)
        else:
            logger.info(f"Processing {len(args.paths)} files")
            process_files(args.paths, args.extensions, add_filename_callback)

    # Set logging level
    if args.loglevel:
        loglevel = getattr(logging, args.loglevel.upper(), logging.INFO)
        logger.setLevel(loglevel)

    # Load environment variables from env file
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'env')
    if os.path.exists(env_path):
        logger.info(f"Loading environment variables from {env_path}")
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    try:
                        key, value = line.split('=', 1)
                        value = value.strip().strip("'\"")
                        os.environ[key.strip()] = value
                        logger.debug(f"Set environment variable: {key}")
                    except ValueError:
                        logger.warning(f"Invalid line in env file: {line}")
    else:
        logger.info(f"No env file found at {env_path}")

    # Log environment configuration
    logger.info("Environment Configuration:")
    logger.info(f"  OPENAI_API_KEY: {'Set' if os.environ.get('OPENAI_API_KEY') else 'Not set'}")
    logger.info(f"  GEMINI_API_KEY: {'Set' if os.environ.get('GEMINI_API_KEY') else 'Not set'}")
    logger.info(f"  GEN_MODEL: {os.environ.get('GEN_MODEL', 'Not set (default: dall-e-3)')}")

    # Initialize image generation configuration
    logger.info("Initializing image generation configuration...")
    gen_config = initialize_gen_config()
    if gen_config:
        logger.info(f"  Model: {gen_config.model}")
        logger.info(f"  Is Gemini: {gen_config.is_gemini_model()}")
        logger.info(f"  Is OpenAI: {gen_config.is_openai_model()}")
    else:
        logger.error("Failed to initialize image generation configuration")

    # Override with command-line arguments
    if args.openai_api_key:
        gen_config.set_api_key(args.openai_api_key)
    if args.gen_model:
        gen_config.set_model(args.gen_model)
    if args.openai_size:
        gen_config.set_size(args.openai_size)
    if args.openai_quality:
        gen_config.set_quality(args.openai_quality)
    if args.openai_style:
        gen_config.set_style(args.openai_style)

    # Create server socket
    bind_port = args.port if args.port else BIND_PORT
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    try:
        server.bind((BIND_IP, bind_port))
        server.listen(10)
    except OSError as e:
        logger.error(f"Error binding to {BIND_IP}:{bind_port}: {e}")
        logger.error("Port may already be in use. Try killing any existing YAIL processes.")
        sys.exit(1)

    logger.info('=' * 60)
    logger.info(f'YAIL Server started successfully')
    logger.info(f'Listening on {BIND_IP}:{bind_port}')
    
    # Log network information
    logger.info('Network Information:')
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        logger.info(f"  Local IP: {local_ip}")
    except Exception as e:
        logger.warning(f"  Could not determine IP: {e}")
    
    # Try netifaces for more detailed network info
    try:
        import netifaces
        logger.info('  Available Interfaces:')
        for interface in netifaces.interfaces():
            try:
                addresses = netifaces.ifaddresses(interface)
                if netifaces.AF_INET in addresses:
                    for address in addresses[netifaces.AF_INET]:
                        ip = address.get('addr', '')
                        if ip and not ip.startswith('127.'):
                            logger.info(f"    {interface}: {ip}")
            except Exception:
                pass
    except ImportError:
        logger.debug("netifaces not available")
    
    logger.info('=' * 60)

    # Initialize camera
    if args.camera:
        if not init_camera(args.camera):
            logger.error("Failed to initialize camera. Exiting.")
            sys.exit(1)
    else:
        init_camera()

    # Main server loop
    logger.info("Accepting client connections...")
    try:
        while True:
            # Clean up finished threads
            active_threads[:] = [t for t in active_threads if t.is_alive()]
            
            # Accept new client connection
            client_sock, address = server.accept()
            logger.info(f'Accepted connection from {address[0]}:{address[1]}')
            
            # Create client handler thread
            client_handler = Thread(
                target=handle_client_connection,
                args=(client_sock, len(active_threads) + 1),
                daemon=True
            )
            client_handler.start()
            active_threads.append(client_handler)
    
    except KeyboardInterrupt:
        signal_handler(None, None)


if __name__ == "__main__":
    main()
