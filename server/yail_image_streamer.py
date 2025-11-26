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
import os
from typing import List, Optional
from io import BytesIO
from PIL import Image
from tqdm import tqdm
from duckduckgo_search import DDGS

from yail_image_converter import convertImageToYAIL, createErrorPacket
from yail_gen import generate_image, generate_image_with_gemini
from yail_camera import capture_camera_image
from yail_server_state import server_state
from yail_image_cache import image_cache

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
        # Generate cache key
        source_key = url if url else filepath
        if not source_key:
            return False
            
        cache_key = f"{source_key}_{gfx_mode}"
        
        # Check cache
        cached_data = image_cache.get(cache_key)
        if cached_data:
            try:
                logger.info(f"Cache hit for {cache_key}")
                client.sendall(cached_data)
                return True
            except Exception as e:
                logger.error(f"Error sending cached data: {e}")
                return False

        if url is not None:
            logger.info(f'Loading {url}')

            headers = {'User-Agent': 'FujiNet-YAIL/1.0 (retro-computing-server)'}
            response = requests.get(url, stream=True, timeout=10, headers=headers)
            file_size = int(response.headers.get('Content-Length', 0))

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

            # progress bar
            image_data = b''
            start_dl_time = time.time()
            with tqdm(total=file_size, unit="B", unit_scale=True, unit_divisor=1024, desc=f"Downloading {filepath}") as progress:
                for data in response.iter_content(8192):
                    image_data += data
                    progress.update(len(data))
            
            dl_time = time.time() - start_dl_time
            logger.info(f"Download complete. Size: {len(image_data)} bytes. Time: {dl_time:.2f}s")
            
            logger.info("Processing image...")
            image_bytes_io = BytesIO()
            image_bytes_io.write(image_data)
            try:
                image = Image.open(image_bytes_io)
                logger.info(f"Image opened. Format: {image.format}, Size: {image.size}, Mode: {image.mode}")
            except Exception as e:
                # Debug: Print first 100 bytes to see if it's HTML or error message
                header = image_data[:100]
                logger.error(f"Failed to open image. Header: {header}")
                raise e

        elif filepath is not None:
            logger.info(f"Opening local file: {filepath}")
            image = Image.open(filepath)
            logger.info(f"Image opened. Format: {image.format}, Size: {image.size}, Mode: {image.mode}")

        logger.info(f"Converting image to YAIL format for mode {gfx_mode}...")
        start_conv_time = time.time()
        image_yai = convertImageToYAIL(image, gfx_mode)
        conv_time = time.time() - start_conv_time
        logger.info(f"Conversion complete. Result size: {len(image_yai)} bytes. Time: {conv_time:.2f}s")
        
        # Cache the result
        image_cache.put(cache_key, image_yai)

        logger.info(f"Starting transmission of {len(image_yai)} bytes to client...")
        start_send_time = time.time()
        client.sendall(image_yai)
        send_time = time.time() - start_send_time
        logger.info(f"Transmission complete. Time: {send_time:.2f}s")

        return True

    except (socket.error, BrokenPipeError, ConnectionResetError) as e:
        logger.warning(f"Client disconnected during stream: {e}")
        raise e
    except Exception as e:
        logger.error(f'Exception in stream_YAI: {e}')
        return False


def search_pollinations(term: str, max_images: int = 10) -> List[str]:
    """
    Generate/Search images using Pollinations.ai (Fallback).
    
    Args:
        term: Search term
        max_images: Maximum number of images to return
        
    Returns:
        List of image URLs
    """
    # Clean term
    term = term.strip('"\' ')
    urls = []
    
    try:
        # Pollinations.ai allows generating images via URL
        # We can generate multiple variations by using different seeds
        base_url = "https://image.pollinations.ai/prompt"
        encoded_term = requests.utils.quote(term)
        
        for i in range(max_images):
            seed = random.randint(0, 1000000)
            # Request size matching YAIL_W/YAIL_H to save bandwidth/processing
            url = f"{base_url}/{encoded_term}?width={YAIL_W}&height={YAIL_H}&seed={seed}&nologo=true"
            urls.append(url)
            
        logger.info(f"Generated {len(urls)} Pollinations.ai URLs for '{term}'")
        return urls
        
    except Exception as e:
        logger.error(f"Error creating Pollinations URLs: {e}")
        return []

def search_brave(term: str, max_images: int = 50) -> List[str]:
    """
    Search for images using Brave Search API.
    
    Args:
        term: Search term
        max_images: Maximum number of images to return
        
    Returns:
        List of image URLs
    """
    api_key = os.environ.get("BRAVE_API_KEY")
    if not api_key:
        return []
        
    # Clean term
    term = term.strip('"\' ')
    
    try:
        url = "https://api.search.brave.com/res/v1/images/search"
        headers = {
            "Accept": "application/json",
            "Accept-Encoding": "gzip",
            "X-Subscription-Token": api_key
        }
        params = {
            "q": term,
            "count": min(max_images, 50) # Brave max count is often 50
        }
        
        response = requests.get(url, headers=headers, params=params, timeout=10)
        
        if response.status_code != 200:
            logger.error(f"Brave Search API error: {response.status_code} {response.text}")
            return []
            
        data = response.json()
        urls = []
        
        if 'results' in data:
            for result in data['results']:
                if 'properties' in result and 'url' in result['properties']:
                    urls.append(result['properties']['url'])
                elif 'url' in result: # Fallback depending on API version
                    urls.append(result['url'])
                    
        logger.info(f"Found {len(urls)} images on Brave Search for '{term}'")
        return urls
        
    except Exception as e:
        logger.error(f"Error searching Brave: {e}")
        return []

def search_images(term: str, max_images: int = 50) -> List[str]:
    """
    Search for images using available providers (Brave > DDG > Pollinations).
    
    Args:
        term: Search term
        max_images: Maximum number of images to return
    
    Returns:
        List of image URLs
    """
    # Clean term
    term = term.strip('"\' ')
    urls = []
    
    # 1. Try Brave Search if configured (Most reliable if key exists)
    if os.environ.get("BRAVE_API_KEY"):
        urls = search_brave(term, max_images)
        if urls:
            return urls
            
    # 2. Try DuckDuckGo (Free, but rate limits)
    try:
        ddgs = DDGS()
        results = ddgs.images(term, max_results=max_images)
        urls = [result['image'] for result in results]
        logger.info(f"Found {len(urls)} images on DuckDuckGo for '{term}'")
    except Exception as e:
        logger.warning(f"DuckDuckGo search failed ({e}), trying fallback...")
    
    # 3. Fallback to Pollinations.ai (AI generation, always works)
    if not urls:
        logger.info("Attempting search on Pollinations.ai...")
        urls = search_pollinations(term, max_images=10)
        
    return urls


def stream_random_image_from_urls(client_socket: socket.socket, urls: list, 
                                  gfx_mode: int) -> None:
    """
    Stream random images from a list of URLs to the client continuously (slideshow).
    
    Args:
        client_socket: The client socket to stream to
        urls: List of image URLs
        gfx_mode: The graphics mode to use
    """
    if not urls:
        send_client_response(client_socket, "No images found", is_error=True)
        return
        
    logger.info(f"Starting slideshow with {len(urls)} images")
    
    try:
        while True:
            url_idx = random.randint(0, len(urls) - 1)
            url = urls[url_idx]
            
            success = stream_YAI(client_socket, gfx_mode, url=url)
            
            if success:
                # Wait before sending next image
                time.sleep(5)
            else:
                # If streaming failed (but not socket error), try another immediately
                logger.warning(f'Problem with {url} trying another...')
                time.sleep(1)
                
    except (socket.error, BrokenPipeError, ConnectionResetError):
        logger.info("Slideshow stopped (client disconnected)")
        # Re-raise to let handler clean up
        raise


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
                          gfx_mode: int, model: str = None) -> None:
    """
    Generate an image with the configured model and stream it to the client.
    
    Args:
        client_socket: The client socket to stream to
        prompt: The text prompt for image generation
        gfx_mode: The graphics mode to use
        model: Optional model name to override configuration
    """
    logger.info(f"Generating image with prompt: '{prompt}' model: {model}")
    
    # Generate image using the configured model
    url_or_path = generate_image(prompt, model=model)
    
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
            message_packet = createErrorPacket(message, gfx_mode=GRAPHICS_8)
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
