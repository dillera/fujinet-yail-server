# YAIL Server - Quick Fixes & Code Examples

This document provides ready-to-implement code for the most impactful improvements.

---

## Fix 1: Clean Up requirements.txt (5 minutes)

### Current State
```
requests>=1.0.0
duckduckgo-search>=1.0.0
fastcore>=1.0.0
pillow>=9.0.0
tqdm>=1.0.0
olefile>=0.0.0
numpy>=1.0.0
fastcore>=1.0.0
numpy>=1.24.0
tqdm>=4.66.0
pygame>=2.5.0
requests>=2.30
openai>=1.0.0
python-dotenv>=1.0.0
```

### Cleaned Version
```
# Image processing
pillow>=10.0.0
numpy>=1.24.0

# API clients
openai>=1.3.0
google-generativeai>=0.3.0
requests>=2.31.0

# Search and utilities
duckduckgo-search>=3.9.0
fastcore>=1.5.0

# Media and UI
pygame>=2.5.0

# Configuration
python-dotenv>=1.0.0

# System utilities
netifaces>=0.11.0
tqdm>=4.66.0
```

**Action**: Replace `server/requirements.txt` with cleaned version

---

## Fix 2: Update env.example (5 minutes)

### Current State
```bash
# OpenAI API Configuration
OPENAI_API_KEY=your_openai_api_key_here

# Optional: OpenAI Model Configuration
# OPENAI_MODEL=dall-e-3
# OPENAI_SIZE=1024x1024
# OPENAI_QUALITY=standard
# OPENAI_STYLE=vivid
# OPENAI_SYSTEM_PROMPT="You are an image generation assistant..."
```

### Enhanced Version
```bash
# ============================================
# YAIL Server Configuration
# ============================================

# Image Generation API Configuration
# Choose ONE of the following:
# - OpenAI (DALL-E 3, DALL-E 2)
# - Google Gemini

# OpenAI Configuration (for DALL-E models)
OPENAI_API_KEY=your_openai_api_key_here

# Google Gemini Configuration (alternative to OpenAI)
GEMINI_API_KEY=your_gemini_api_key_here

# Image Generation Model Selection
# Options: dall-e-3, dall-e-2, gemini-2.5-pro-exp-03-25
# Default: dall-e-3
GEN_MODEL=dall-e-3

# OpenAI-specific Configuration (used only with dall-e models)
OPENAI_SIZE=1024x1024              # Options: 1024x1024, 1792x1024, 1024x1792
OPENAI_QUALITY=standard            # Options: standard, hd (DALL-E 3 only)
OPENAI_STYLE=vivid                 # Options: vivid, natural (DALL-E 3 only)
OPENAI_SYSTEM_PROMPT=You are an expert illustrator creating beautiful, imaginative artwork

# Server Configuration
# PORT=5556                         # Default: 5556
# LOGLEVEL=INFO                     # Options: DEBUG, INFO, WARN, ERROR, CRITICAL

# Image Processing
# GRAPHICS_MODE=8                   # Default graphics mode (8, 9, or 16 for VBXE)
```

**Action**: Replace `server/env.example` with enhanced version

---

## Fix 3: Add Thread-Safe State Management (30 minutes)

### New File: `server/yail_server_state.py`

```python
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
```

### Usage in yail.py

Replace global variables:
```python
# OLD (lines 71-78)
yail_data = bytearray()
yail_mutex = threading.Lock()
active_client_threads = []
connections = 0
filenames = []
last_prompt = None
last_gen_model = None

# NEW
from yail_server_state import server_state

# Then use:
server_state.increment_connections()
server_state.add_filename(path)
server_state.set_last_prompt(prompt)
```

---

## Fix 4: Add Image Generation Timeout (20 minutes)

### Update: `server/yail_gen.py`

Add timeout wrapper function:

```python
import signal
import os
from typing import Optional, Callable, Any

def with_timeout(timeout_seconds: int, default_return: Any = None):
    """
    Decorator to add timeout to a function.
    
    Args:
        timeout_seconds: Timeout in seconds
        default_return: Value to return on timeout
    
    Usage:
        @with_timeout(120)
        def my_function():
            # This will timeout after 120 seconds
            pass
    """
    def decorator(func: Callable) -> Callable:
        def timeout_handler(signum, frame):
            raise TimeoutError(f"Function {func.__name__} timed out after {timeout_seconds}s")
        
        def wrapper(*args, **kwargs):
            # Only use signal-based timeout on Unix systems
            if hasattr(signal, 'SIGALRM'):
                old_handler = signal.signal(signal.SIGALRM, timeout_handler)
                signal.alarm(timeout_seconds)
                try:
                    result = func(*args, **kwargs)
                    signal.alarm(0)  # Cancel alarm
                    return result
                except TimeoutError as e:
                    logger.error(f"Timeout: {e}")
                    return default_return
                finally:
                    signal.signal(signal.SIGALRM, old_handler)
                    signal.alarm(0)
            else:
                # Fallback for Windows (no signal.SIGALRM)
                logger.warning("Timeout not supported on this platform")
                return func(*args, **kwargs)
        
        return wrapper
    return decorator


# Apply timeout to image generation functions
@with_timeout(120)  # 2 minute timeout
def generate_image_with_openai(prompt: str, api_key: str = None, 
                               model: str = None, size: str = None, 
                               quality: str = None, style: str = None) -> Optional[str]:
    """Generate an image using OpenAI (with 2-minute timeout)."""
    # ... existing code ...


@with_timeout(120)  # 2 minute timeout
def generate_image_with_gemini(prompt: str) -> Optional[str]:
    """Generate an image using Gemini (with 2-minute timeout)."""
    # ... existing code ...
```

---

## Fix 5: Add Input Validation (25 minutes)

### New File: `server/yail_command_validator.py`

```python
#!/usr/bin/env python3
"""
Command validation for YAIL server.
Validates all client commands before processing.
"""

import logging
from typing import Tuple, List, Optional

logger = logging.getLogger(__name__)

# Constants
MAX_PROMPT_LENGTH = 1000
MAX_SEARCH_TERMS_LENGTH = 200
VALID_GRAPHICS_MODES = [2, 4, 8, 16]  # GRAPHICS_8, GRAPHICS_9, GRAPHICS_11, VBXE
VALID_CONFIG_PARAMS = ['model', 'size', 'quality', 'style', 'system_prompt']


class CommandValidator:
    """Validates client commands."""
    
    @staticmethod
    def validate_gen_command(tokens: List[str]) -> Tuple[bool, Optional[str]]:
        """Validate 'gen' command."""
        if len(tokens) < 2:
            return False, "gen command requires a prompt"
        
        prompt = ' '.join(tokens[1:])
        
        if len(prompt) > MAX_PROMPT_LENGTH:
            return False, f"Prompt too long (max {MAX_PROMPT_LENGTH} characters)"
        
        if len(prompt.strip()) == 0:
            return False, "Prompt cannot be empty"
        
        return True, None
    
    @staticmethod
    def validate_search_command(tokens: List[str]) -> Tuple[bool, Optional[str]]:
        """Validate 'search' command."""
        if len(tokens) < 2:
            return False, "search command requires search terms"
        
        terms = ' '.join(tokens[1:])
        
        if len(terms) > MAX_SEARCH_TERMS_LENGTH:
            return False, f"Search terms too long (max {MAX_SEARCH_TERMS_LENGTH} characters)"
        
        if len(terms.strip()) == 0:
            return False, "Search terms cannot be empty"
        
        return True, None
    
    @staticmethod
    def validate_gfx_command(tokens: List[str]) -> Tuple[bool, Optional[str]]:
        """Validate 'gfx' command."""
        if len(tokens) < 2:
            return False, "gfx command requires a graphics mode"
        
        try:
            mode = int(tokens[1])
            if mode not in VALID_GRAPHICS_MODES:
                valid_modes = ', '.join(map(str, VALID_GRAPHICS_MODES))
                return False, f"Invalid graphics mode: {mode}. Valid modes: {valid_modes}"
            return True, None
        except ValueError:
            return False, f"Graphics mode must be an integer, got: {tokens[1]}"
    
    @staticmethod
    def validate_config_command(tokens: List[str]) -> Tuple[bool, Optional[str]]:
        """Validate 'openai-config' command."""
        if len(tokens) < 2:
            return True, None  # Allowed to query config without params
        
        param = tokens[1].lower()
        
        if param not in VALID_CONFIG_PARAMS:
            valid = ', '.join(VALID_CONFIG_PARAMS)
            return False, f"Invalid config parameter: {param}. Valid: {valid}"
        
        if len(tokens) < 3:
            return False, f"Config parameter '{param}' requires a value"
        
        return True, None
    
    @staticmethod
    def validate_command(tokens: List[str]) -> Tuple[bool, Optional[str]]:
        """Validate any command."""
        if not tokens:
            return False, "Empty command"
        
        command = tokens[0].lower()
        
        if command in ['gen', 'generate']:
            return CommandValidator.validate_gen_command(tokens)
        elif command == 'search':
            return CommandValidator.validate_search_command(tokens)
        elif command == 'gfx':
            return CommandValidator.validate_gfx_command(tokens)
        elif command == 'openai-config':
            return CommandValidator.validate_config_command(tokens)
        elif command in ['video', 'camera', 'files', 'next', 'quit']:
            return True, None  # No arguments needed
        else:
            return False, f"Unknown command: {command}"


# Usage in yail.py:
# from yail_command_validator import CommandValidator
# 
# is_valid, error_msg = CommandValidator.validate_command(tokens)
# if not is_valid:
#     send_client_response(client_socket, error_msg, is_error=True)
#     continue
```

---

## Fix 6: Add API Key Validation at Startup (15 minutes)

### Update: `server/yail.py` - `main()` function

Add this before server starts:

```python
def validate_configuration():
    """
    Validate that required configuration is present.
    Exit with clear error if missing.
    """
    issues = []
    
    # Check for image generation API keys
    openai_key = os.environ.get("OPENAI_API_KEY")
    gemini_key = os.environ.get("GEMINI_API_KEY")
    
    if not openai_key and not gemini_key:
        issues.append("Neither OPENAI_API_KEY nor GEMINI_API_KEY is set")
    
    # Check for model configuration
    gen_model = os.environ.get("GEN_MODEL", "dall-e-3")
    
    if "dall-e" in gen_model.lower() and not openai_key:
        issues.append(f"Model {gen_model} requires OPENAI_API_KEY")
    
    if "gemini" in gen_model.lower() and not gemini_key:
        issues.append(f"Model {gen_model} requires GEMINI_API_KEY")
    
    if issues:
        logger.error("Configuration validation failed:")
        for issue in issues:
            logger.error(f"  - {issue}")
        logger.error("\nPlease set the required environment variables:")
        logger.error("  export OPENAI_API_KEY=your_key_here")
        logger.error("  export GEMINI_API_KEY=your_key_here")
        sys.exit(1)
    
    logger.info("Configuration validation passed")


# In main(), add before server starts:
if __name__ == "__main__":
    main()

def main():
    # ... existing code ...
    
    # Validate configuration
    validate_configuration()
    
    # ... rest of main() ...
```

---

## Fix 7: Improve Logging (20 minutes)

### Add to `server/yail.py`

```python
import time
from functools import wraps

def log_performance(func):
    """Decorator to log function execution time."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start = time.time()
        try:
            result = func(*args, **kwargs)
            elapsed = time.time() - start
            logger.info(f"{func.__name__} completed in {elapsed:.2f}s")
            return result
        except Exception as e:
            elapsed = time.time() - start
            logger.error(f"{func.__name__} failed after {elapsed:.2f}s: {e}")
            raise
    return wrapper


# Apply to image streaming functions
@log_performance
def stream_YAI(client, gfx_mode, url=None, filepath=None):
    """Stream image to client (with performance logging)."""
    # ... existing code ...


# Add metrics logging to handle_client_connection
def handle_client_connection(client_socket, thread_id):
    """Handle a client connection in a separate thread."""
    start_time = time.time()
    
    try:
        # ... existing code ...
        pass
    finally:
        elapsed = time.time() - start_time
        logger.info(f"Connection {thread_id} closed after {elapsed:.1f}s")
```

---

## Fix 8: Add Comments to Image Conversion (15 minutes)

### Update: `server/yail.py` - Image conversion functions

Add detailed comments:

```python
def convertToYaiVBXE(image_data: bytes, palette_data: bytes, gfx_mode: int) -> bytearray:
    """
    Convert image data to YAIL format for VBXE (Atari graphics mode 16).
    
    VBXE (Video Board Extended) uses 256-color palette mode with special requirements:
    - Palette entries are offset by 1 (entry 0 is reserved)
    - Image data byte values are offset by 1 (0 maps to palette entry 1)
    - This allows palette entry 0 to be used for transparency/background
    
    Args:
        image_data (bytes): 8-bit indexed image data (320x240 = 76,800 bytes)
        palette_data (bytes): RGB palette data (256 colors * 3 bytes = 768 bytes)
        gfx_mode (int): Graphics mode identifier (16 for VBXE)
    
    Returns:
        bytearray: YAIL format binary data with header, palette, and image
    
    Binary Format:
        [0:3]   Version (1, 4, 0)
        [3]     Graphics mode (16 for VBXE)
        [4]     Number of memory blocks (2: palette + image)
        [5]     Block type (0x06 for palette)
        [6:10]  Palette size (little-endian uint32)
        [10:778]    Palette data (768 bytes)
        [778]   Block type (0x07 for image)
        [779:783]   Image size (little-endian uint32)
        [783:]  Image data
    """
    import struct
    
    # Log information about the source image
    logger.debug(f'Image data size: {len(image_data)}')
    logger.debug(f'Palette data size: {len(palette_data)}')
    
    image_yai = bytearray()
    image_yai += bytes([1, 4, 0])            # version
    image_yai += bytes([gfx_mode])           # gfx mode (16 for VBXE)
    image_yai += struct.pack("<B", 2)        # number of memory blocks (palette + image)
    
    # Palette block
    image_yai += bytes([PALETTE_BLOCK])             # Memory block type (0x06)
    image_yai += struct.pack("<I", len(palette_data)) # palette size
    image_yai += bytearray(palette_data)  # palette data
    
    # Image block
    image_yai += bytes([IMAGE_BLOCK])                  # Memory block type (0x07)
    image_yai += struct.pack("<I", len(image_data)) # image size
    image_yai += bytearray(image_data)       # image data
    
    logger.debug(f'YAI size: {len(image_yai)}')
    
    return image_yai
```

---

## Implementation Order

1. **Fix 1** (5 min): Clean up requirements.txt
2. **Fix 2** (5 min): Update env.example
3. **Fix 8** (15 min): Add comments
4. **Fix 7** (20 min): Improve logging
5. **Fix 4** (20 min): Add timeout
6. **Fix 5** (25 min): Add validation
7. **Fix 3** (30 min): Thread-safe state
8. **Fix 6** (15 min): API key validation

**Total Time**: ~2.5 hours for all quick fixes

---

## Testing After Fixes

```bash
# Test 1: Verify requirements install
pip install -r server/requirements.txt

# Test 2: Verify server starts with validation
python server/yail.py --gen-model dall-e-3

# Test 3: Test with missing API key (should fail gracefully)
unset OPENAI_API_KEY
python server/yail.py --gen-model dall-e-3

# Test 4: Test with validation
python server/yail.py --gen-model dall-e-3 --openai-api-key test_key

# Test 5: Test client commands
python deployment/test_gen_command.py "happy cat"
```

---

## Next Steps

After implementing these quick fixes:
1. Commit changes with clear messages
2. Test thoroughly with multiple clients
3. Move to Phase 2 (code refactoring)
4. Add unit tests
5. Deploy to staging

