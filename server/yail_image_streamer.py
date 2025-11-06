#!/usr/bin/env python3
"""
YAIL Image Streamer Module

Handles streaming images to clients from various sources:
- Generated images (OpenAI DALL-E, Google Gemini)
- Web search results (DuckDuckGo)
- Local files
- Webcam
"""

import socket
import time
import random
import logging
import requests
from typing import List, Optional
from io import BytesIO
from PIL import Image
from tqdm import tqdm
from duckduckgo_search import DDGS

from yail_image_converter import convertImageToYAIL, createErrorPacket
from yail_gen import generate_image, generate_image_with_gemini
from yail_camera import capture_camera_image
from yail_server_state import server_state

logger = logging.getLogger(__name__)

# Constants
SOCKET_WAIT_TIME = 1
GRAPHICS_8 = 2
GRAPHICS_9 = 4
VBXE = 16
YAIL_W = 320
YAIL_H = 220


def stream_YAI(client: socket.socket, gfx_mode: int, url: str = None, 
               filepath: str = None) -> bool:
    """
    Stream an image to the client.
    
    Downloads image from URL or loads from file, converts to YAIL format,
    and sends to client.
    
    Args:
        client: Client socket to stream to
        gfx_mode: Graphics mode to use
        url: URL of image to download (optional)
        filepath: Path to local image file (optional)
    
    Returns:
        True if successful, False otherwise
    """
    try:
        if url is not None:
            logger.info(f'Loading {url}')

            file_size = 0

            response = requests.get(url, stream=True, timeout=5)

            # get the file name
            filepath = ''
            exts = ['.jpg', '.jpeg', '.gif', '.png']
            import re
            ext = re.findall('|'.join(exts), url)
            if len(ext):
                pos_ext = url.find(ext[0])
                if pos_ext >= 0:
                    pos_name = url.rfind("/", 0, pos_ext)
                    filepath = url[pos_name + 1:pos_ext + 4]

            # progress bar, changing the unit to bytes instead of iteration (default by tqdm)
            image_data = b''
            progress = tqdm(response.iter_content(256), f"Downloading {filepath}", 
                          total=file_size, unit="B", unit_scale=True, unit_divisor=256)
            for data in progress:
                # collect all the data
                image_data += data
                # update the progress bar manually
                progress.update(len(data))

            image_bytes_io = BytesIO()
            image_bytes_io.write(image_data)
            image = Image.open(image_bytes_io)

        elif filepath is not None:
            image = Image.open(filepath)

        image_yai = convertImageToYAIL(image, gfx_mode)

        client.sendall(image_yai)

        return True

    except Exception as e:
        logger.error(f'Exception: {e}')
        return False


def search_images(term: str, max_images: int = 100) -> List[str]:
    """
    Search for images using DuckDuckGo.
    
    Args:
        term: Search term
        max_images: Maximum number of images to return
    
    Returns:
        List of image URLs
    """
    try:
        ddgs = DDGS()
        results = ddgs.images(term, max_results=max_images)
        
        # Extract image URLs from results
        urls = [result['image'] for result in results]
        logger.info(f"Found {len(urls)} images for search term: '{term}'")
        return urls
    except Exception as e:
        logger.error(f"Error searching for images: {e}")
        return []


def stream_random_image_from_urls(client_socket: socket.socket, urls: list, 
                                  gfx_mode: int) -> None:
    """
    Stream a random image from a list of URLs to the client.
    
    Handles retries if an image fails to stream.
    
    Args:
        client_socket: The client socket to stream to
        urls: List of image URLs
        gfx_mode: The graphics mode to use
    """
    if not urls:
        send_client_response(client_socket, "No images found", is_error=True)
        return
        
    url_idx = random.randint(0, len(urls) - 1)
    url = urls[url_idx]
    
    # Loop if we have a problem with the image, selecting the next
    while not stream_YAI(client_socket, gfx_mode, url=url):
        logger.warning(f'Problem with {url} trying another...')
        url_idx = random.randint(0, len(urls) - 1)
        url = urls[url_idx]
        time.sleep(SOCKET_WAIT_TIME)


def stream_random_image_from_files(client_socket: socket.socket, gfx_mode: int) -> None:
    """
    Stream a random image from the loaded filenames to the client.
    
    Handles retries if an image fails to stream.
    
    Args:
        client_socket: The client socket to stream to
        gfx_mode: The graphics mode to use
    """
    filename = server_state.get_random_filename()
    if not filename:
        send_client_response(client_socket, "No image files available", is_error=True)
        return
    
    # Loop if we have a problem with the image, selecting the next
    while not stream_YAI(client_socket, gfx_mode, filepath=filename):
        logger.warning(f'Problem with {filename} trying another...')
        filename = server_state.get_random_filename()
        if not filename:
            send_client_response(client_socket, "No image files available", is_error=True)
            return
        time.sleep(SOCKET_WAIT_TIME)


def stream_generated_image(client_socket: socket.socket, prompt: str, 
                          gfx_mode: int) -> None:
    """
    Generate an image with the configured model and stream it to the client.
    
    Args:
        client_socket: The client socket to stream to
        prompt: The text prompt for image generation
        gfx_mode: The graphics mode to use
    """
    logger.info(f"Generating image with prompt: '{prompt}'")
    
    # Generate image using the configured model
    url_or_path = generate_image(prompt)
    
    if url_or_path:
        # Stream the generated image to the client
        if url_or_path.startswith('http'):
            # It's a URL (from OpenAI)
            if not stream_YAI(client_socket, gfx_mode, url=url_or_path):
                logger.warning(f'Problem with generated image: {url_or_path}')
                send_client_response(client_socket, "Failed to stream generated image", is_error=True)
        else:
            # It's a local file path (from Gemini)
            if not stream_YAI(client_socket, gfx_mode, filepath=url_or_path):
                logger.warning(f'Problem with generated image: {url_or_path}')
                send_client_response(client_socket, "Failed to stream generated image", is_error=True)
    else:
        logger.warning('Failed to generate image')
        send_client_response(client_socket, "Failed to generate image", is_error=True)


def stream_generated_image_gemini(client_socket: socket.socket, prompt: str, 
                                 gfx_mode: int) -> None:
    """
    Generate an image with Gemini and stream it to the client.
    
    Args:
        client_socket: The client socket to stream to
        prompt: The text prompt for image generation
        gfx_mode: The graphics mode to use
    """
    logger.info(f"Generating image with prompt: '{prompt}'")
    
    # Generate image using Gemini
    image_path = generate_image_with_gemini(prompt)
    
    if image_path:
        # Stream the generated image to the client
        if not stream_YAI(client_socket, gfx_mode, filepath=image_path):
            logger.warning(f'Problem with generated image: {image_path}')
            send_client_response(client_socket, "Failed to stream generated image", is_error=True)
    else:
        logger.warning('Failed to generate image with Gemini')
        send_client_response(client_socket, "Failed to generate image", is_error=True)


def stream_camera_frame(client_socket: socket.socket, gfx_mode: int) -> None:
    """
    Capture and stream a frame from the webcam.
    
    Args:
        client_socket: The client socket to stream to
        gfx_mode: The graphics mode to use
    """
    vid_frame = capture_camera_image(YAIL_W, YAIL_H)
    if vid_frame:
        vid_frame_yail = convertImageToYAIL(vid_frame, gfx_mode)
        client_socket.sendall(vid_frame_yail)
    else:
        send_client_response(client_socket, "Failed to capture camera frame", is_error=True)


def send_client_response(client_socket: socket.socket, message: str, 
                        is_error: bool = False) -> None:
    """
    Send a standardized response to the client.
    
    Args:
        client_socket: The client socket to send the response to
        message: The message to send
        is_error: Whether this is an error message
    """
    prefix = "ERROR: " if is_error else "OK: "
    try:
        if is_error:
            message_packet = createErrorPacket(message.encode('utf-8'), gfx_mode=GRAPHICS_8)
            client_socket.sendall(message_packet)
        else:
            # For non-error messages, send as plain text with OK prefix
            client_socket.sendall(bytes(f"{prefix}{message}\r\n".encode('utf-8')))
            
        if is_error:
            logger.warning(f"Sent error to client: {message}")
        else:
            logger.info(f"Sent response to client: {message}")
    except Exception as e:
        logger.error(f"Failed to send response to client: {e}")
