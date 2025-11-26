#!/usr/bin/env python3
"""
YAIL Image Cache Module

Provides thread-safe LRU caching for processed images to reduce
re-processing overhead and latency.
"""

import threading
import logging
from typing import Optional
from collections import OrderedDict

logger = logging.getLogger(__name__)

class ImageCache:
    """
    Thread-safe LRU cache for image data.
    """
    
    def __init__(self, max_size_mb: int = 50, max_items: int = 20):
        """
        Initialize the cache.
        
        Args:
            max_size_mb: Maximum cache size in megabytes
            max_items: Maximum number of items in cache
        """
        self.cache = OrderedDict()
        self.lock = threading.RLock()
        self.max_size_bytes = max_size_mb * 1024 * 1024
        self.max_items = max_items
        self.current_size_bytes = 0
        logger.info(f"Image cache initialized: {max_items} items, {max_size_mb}MB")
        
    def get(self, key: str) -> Optional[bytes]:
        """
        Get item from cache.
        
        Args:
            key: Cache key
            
        Returns:
            Cached data bytes or None if not found
        """
        with self.lock:
            if key not in self.cache:
                return None
            # Move to end (most recently used)
            self.cache.move_to_end(key)
            logger.debug(f"Cache hit: {key}")
            return self.cache[key]
            
    def put(self, key: str, data: bytes) -> None:
        """
        Add item to cache.
        
        Args:
            key: Cache key
            data: Data bytes
        """
        with self.lock:
            data_size = len(data)
            
            # If item is too big for cache, don't cache it
            if data_size > self.max_size_bytes:
                logger.warning(f"Item too large for cache: {data_size} bytes")
                return

            if key in self.cache:
                self.current_size_bytes -= len(self.cache[key])
                self.cache.move_to_end(key)
            else:
                logger.debug(f"Cache add: {key} ({data_size} bytes)")
            
            self.cache[key] = data
            self.current_size_bytes += data_size
            
            self._prune()
            
    def _prune(self):
        """Remove old items to stay within limits."""
        # Prune by count
        while len(self.cache) > self.max_items:
            key, data = self.cache.popitem(last=False) # FIFO (remove oldest)
            self.current_size_bytes -= len(data)
            logger.debug(f"Cache pruned (count): {key}")
            
        # Prune by size
        while self.current_size_bytes > self.max_size_bytes and self.cache:
            key, data = self.cache.popitem(last=False)
            self.current_size_bytes -= len(data)
            logger.debug(f"Cache pruned (size): {key}")

    def clear(self):
        """Clear the cache."""
        with self.lock:
            self.cache.clear()
            self.current_size_bytes = 0
            logger.info("Image cache cleared")

    def stats(self) -> dict:
        """Get cache statistics."""
        with self.lock:
            return {
                "items": len(self.cache),
                "size_bytes": self.current_size_bytes,
                "max_items": self.max_items,
                "max_size_bytes": self.max_size_bytes
            }

# Global instance
image_cache = ImageCache()
