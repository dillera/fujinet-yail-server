#!/usr/bin/env python3
"""
Thread-safe state management for YAIL server.
Centralizes all global state with proper synchronization.
"""

import threading
import random
import logging
from typing import List, Optional

logger = logging.getLogger(__name__)


class ServerState:
    """
    Thread-safe state manager for the YAIL server.
    Encapsulates all global state with proper locking.
    """
    
    def __init__(self):
        self._lock = threading.RLock()  # Reentrant lock
        self._filenames: List[str] = []
        self._connections: int = 0
        self._last_prompt: Optional[str] = None
        self._last_gen_model: Optional[str] = None
    
    # Filename management
    def add_filename(self, path: str) -> None:
        """Add a filename to the list."""
        with self._lock:
            if path not in self._filenames:
                self._filenames.append(path)
                logger.debug(f"Added filename: {path}")
    
    def get_random_filename(self) -> Optional[str]:
        """Get a random filename from the list."""
        with self._lock:
            if not self._filenames:
                return None
            return random.choice(self._filenames)
    
    def get_filenames_count(self) -> int:
        """Get the number of filenames."""
        with self._lock:
            return len(self._filenames)
    
    def clear_filenames(self) -> None:
        """Clear all filenames."""
        with self._lock:
            self._filenames.clear()
            logger.info("Cleared all filenames")
    
    # Connection management
    def increment_connections(self) -> int:
        """Increment connection counter and return new value."""
        with self._lock:
            self._connections += 1
            return self._connections
    
    def decrement_connections(self) -> int:
        """Decrement connection counter and return new value."""
        with self._lock:
            self._connections = max(0, self._connections - 1)
            return self._connections
    
    def get_connections(self) -> int:
        """Get current connection count."""
        with self._lock:
            return self._connections
    
    # Prompt management
    def set_last_prompt(self, prompt: str) -> None:
        """Set the last prompt."""
        with self._lock:
            self._last_prompt = prompt
    
    def get_last_prompt(self) -> Optional[str]:
        """Get the last prompt."""
        with self._lock:
            return self._last_prompt
    
    # Model management
    def set_last_gen_model(self, model: str) -> None:
        """Set the last generation model."""
        with self._lock:
            self._last_gen_model = model
    
    def get_last_gen_model(self) -> Optional[str]:
        """Get the last generation model."""
        with self._lock:
            return self._last_gen_model
    
    def __repr__(self) -> str:
        with self._lock:
            return (f"ServerState(connections={self._connections}, "
                   f"filenames={len(self._filenames)}, "
                   f"last_prompt={self._last_prompt})")


# Global instance
server_state = ServerState()
