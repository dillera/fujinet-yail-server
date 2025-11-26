#!/usr/bin/env python3
"""
Configuration Reset Utility for YAIL Server.

This script allows resetting the configuration to default values or clearing specific settings.
Usage:
    python reset_config.py --reset-all      # Reset all configuration to defaults
    python reset_config.py --clear-keys     # Clear API keys only
"""

import os
import shutil
import argparse
import sys

def reset_all():
    """Reset the .env file to the example defaults."""
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'env')
    example_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'env.example')
    
    if not os.path.exists(example_path):
        print(f"Error: {example_path} not found. Cannot reset configuration.")
        return False
        
    try:
        shutil.copy2(example_path, env_path)
        print(f"Configuration reset successfully. Copied {example_path} to {env_path}")
        print("Please edit server/env to add your API keys.")
        return True
    except Exception as e:
        print(f"Error resetting configuration: {e}")
        return False

def clear_cache():
    """Clear generated images and pycache."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Clear generated_images
    gen_dir = os.path.join(base_dir, 'generated_images')
    if os.path.exists(gen_dir):
        try:
            shutil.rmtree(gen_dir)
            print(f"Cleared directory: {gen_dir}")
        except Exception as e:
            print(f"Error clearing generated_images: {e}")
            
    # Clear __pycache__
    cache_dir = os.path.join(base_dir, '__pycache__')
    if os.path.exists(cache_dir):
        try:
            shutil.rmtree(cache_dir)
            print(f"Cleared directory: {cache_dir}")
        except Exception as e:
            print(f"Error clearing __pycache__: {e}")

    print("Cache cleared.")
    return True

def clear_keys():
    """Clear API keys from the .env file but keep other settings."""
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'env')
    
    if not os.path.exists(env_path):
        print(f"Error: {env_path} not found.")
        return False
        
    try:
        with open(env_path, 'r') as f:
            lines = f.readlines()
            
        with open(env_path, 'w') as f:
            for line in lines:
                if line.strip().startswith('OPENAI_API_KEY='):
                    f.write('OPENAI_API_KEY=\n')
                elif line.strip().startswith('GEMINI_API_KEY='):
                    f.write('GEMINI_API_KEY=\n')
                else:
                    f.write(line)
                    
        print("API keys cleared from configuration.")
        return True
    except Exception as e:
        print(f"Error clearing keys: {e}")
        return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Reset YAIL Server Configuration")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--reset-all', action='store_true', help='Reset configuration to defaults (overwrites env file)')
    group.add_argument('--clear-keys', action='store_true', help='Clear API keys only')
    group.add_argument('--clear-cache', action='store_true', help='Clear generated images and pycache')
    
    args = parser.parse_args()
    
    if args.reset_all:
        reset_all()
    elif args.clear_keys:
        clear_keys()
    elif args.clear_cache:
        clear_cache()
