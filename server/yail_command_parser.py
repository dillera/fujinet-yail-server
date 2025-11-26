#!/usr/bin/env python3
"""
YAIL Command Parser Module

Parses and dispatches client commands.
Handles command validation and routing to appropriate handlers.
"""

import logging
from typing import List, Tuple, Optional, Callable, Dict, Any

logger = logging.getLogger(__name__)

# Graphics mode constants
GRAPHICS_8 = 2
GRAPHICS_9 = 4
GRAPHICS_11 = 8
VBXE = 16

VALID_GRAPHICS_MODES = [GRAPHICS_8, GRAPHICS_9, GRAPHICS_11, VBXE]

# Mapping from user-friendly Atari mode numbers to internal YAIL constants
# Users expect "gfx 8" to give them Graphics 8 (which is internal mode 2)
GRAPHICS_MODE_MAP = {
    '8': GRAPHICS_8,   # Atari Mode 8 -> YAIL Mode 2
    '9': GRAPHICS_9,   # Atari Mode 9 -> YAIL Mode 4
    '11': GRAPHICS_11, # Atari Mode 11 -> YAIL Mode 8
    'vbxe': VBXE,      # VBXE -> YAIL Mode 16
    '2': GRAPHICS_8,   # Internal ID support
    '4': GRAPHICS_9,   # Internal ID support
    '16': VBXE         # Internal ID support
}


class CommandValidator:
    """Validates client commands before processing."""
    
    MAX_PROMPT_LENGTH = 1000
    MAX_SEARCH_TERMS_LENGTH = 200
    VALID_CONFIG_PARAMS = ['model', 'size', 'quality', 'style', 'system_prompt']
    
    @staticmethod
    def validate_gen_command(tokens: List[str]) -> Tuple[bool, Optional[str]]:
        """Validate 'gen' command."""
        if len(tokens) < 2:
            return False, "gen command requires a prompt"
        
        prompt = ' '.join(tokens[1:])
        
        if len(prompt) > CommandValidator.MAX_PROMPT_LENGTH:
            return False, f"Prompt too long (max {CommandValidator.MAX_PROMPT_LENGTH} characters)"
        
        if len(prompt.strip()) == 0:
            return False, "Prompt cannot be empty"
        
        return True, None
    
    @staticmethod
    def validate_search_command(tokens: List[str]) -> Tuple[bool, Optional[str]]:
        """Validate 'search' command."""
        if len(tokens) < 2:
            return False, "search command requires search terms"
        
        terms = ' '.join(tokens[1:])
        
        if len(terms) > CommandValidator.MAX_SEARCH_TERMS_LENGTH:
            return False, f"Search terms too long (max {CommandValidator.MAX_SEARCH_TERMS_LENGTH} characters)"
        
        if len(terms.strip()) == 0:
            return False, "Search terms cannot be empty"
        
        return True, None
    
    @staticmethod
    def validate_gfx_command(tokens: List[str]) -> Tuple[bool, Optional[str]]:
        """Validate 'gfx' command."""
        if len(tokens) < 2:
            return False, "gfx command requires a graphics mode"
        
        mode_str = tokens[1].lower()
        if mode_str in GRAPHICS_MODE_MAP:
            return True, None
            
        valid_modes = ', '.join(sorted(GRAPHICS_MODE_MAP.keys()))
        return False, f"Invalid graphics mode: {tokens[1]}. Valid modes: {valid_modes}"

    @staticmethod
    def validate_config_command(tokens: List[str]) -> Tuple[bool, Optional[str]]:
        """Validate 'openai-config' command."""
        if len(tokens) < 2:
            return True, None  # Allowed to query config without params
        
        param = tokens[1].lower()
        
        if param not in CommandValidator.VALID_CONFIG_PARAMS:
            valid = ', '.join(CommandValidator.VALID_CONFIG_PARAMS)
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


class CommandContext:
    """Context for command execution."""
    
    def __init__(self):
        self.client_mode: Optional[str] = None
        self.gfx_mode: int = GRAPHICS_8
        self.urls: List[str] = []
        self.tokens: List[str] = []
    
    def reset_tokens(self):
        """Reset token buffer."""
        self.tokens = []
    
    def set_mode(self, mode: str):
        """Set current client mode."""
        self.client_mode = mode
    
    def set_graphics_mode(self, mode: int):
        """Set graphics mode."""
        if mode in VALID_GRAPHICS_MODES:
            self.gfx_mode = mode
            return True
        return False
    
    def set_search_urls(self, urls: List[str]):
        """Set URLs from search."""
        self.urls = urls


class CommandParser:
    """Parses and validates client commands."""
    
    def __init__(self):
        self.validator = CommandValidator()
    
    def parse_command(self, request: bytes) -> Tuple[bool, List[str], Optional[str]]:
        """
        Parse raw client request into command tokens.
        
        Args:
            request: Raw bytes from client
        
        Returns:
            Tuple of (is_valid, tokens, error_message)
        """
        try:
            r_string = request.decode('UTF-8')
            tokens = r_string.rstrip(' \r\n').split(' ')
            
            # Validate command
            is_valid, error = self.validator.validate_command(tokens)
            
            if not is_valid:
                return False, tokens, error
            
            return True, tokens, None
            
        except Exception as e:
            logger.error(f"Error parsing command: {e}")
            return False, [], f"Error parsing command: {e}"
    
    def extract_prompt(self, tokens: List[str], start_index: int = 1) -> str:
        """
        Extract prompt from tokens starting at index.
        
        Args:
            tokens: Command tokens
            start_index: Index to start extracting from
        
        Returns:
            Joined prompt string
        """
        prompt = ' '.join(tokens[start_index:])
        # Strip surrounding quotes if present
        if len(prompt) >= 2 and prompt.startswith('"') and prompt.endswith('"'):
            return prompt[1:-1]
        # Strip trailing quote if start quote is missing (heuristic for some clients)
        if prompt.endswith('"') and not prompt.startswith('"'):
             return prompt.rstrip('"')
        return prompt
    
    def extract_graphics_mode(self, tokens: List[str]) -> Optional[int]:
        """
        Extract graphics mode from tokens.
        
        Args:
            tokens: Command tokens
        
        Returns:
            Graphics mode or None if invalid
        """
        if not tokens:
            return None
            
        # If len >= 2, assume ['gfx', 'mode'] format
        # If len == 1, assume ['mode'] format (if command was popped)
        mode_token = tokens[1] if len(tokens) >= 2 else tokens[0]
        
        mode_str = mode_token.lower()
        if mode_str in GRAPHICS_MODE_MAP:
            return GRAPHICS_MODE_MAP[mode_str]
            
        return None
    
    def extract_config_param(self, tokens: List[str]) -> Tuple[Optional[str], Optional[str]]:
        """
        Extract config parameter and value from tokens.
        
        Args:
            tokens: Command tokens
        
        Returns:
            Tuple of (param, value) or (None, None) if invalid
        """
        if len(tokens) < 2:
            return None, None
        
        param = tokens[1].lower()
        value = tokens[2] if len(tokens) > 2 else None
        
        return param, value
