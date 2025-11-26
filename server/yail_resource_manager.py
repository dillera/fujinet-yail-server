#!/usr/bin/env python3
"""
YAIL Resource Manager Module

Handles cleanup of temporary files and resource management.
"""

import os
import time
import logging
import shutil
from pathlib import Path

logger = logging.getLogger(__name__)

class ResourceManager:
    """Manages server resources and cleanup."""
    
    def __init__(self, generated_dir: str = "generated_images"):
        self.generated_dir = generated_dir
        
    def cleanup_generated_images(self, max_age_hours: float = 24) -> int:
        """
        Clean up generated images older than max_age_hours.
        
        Args:
            max_age_hours: Maximum age in hours
            
        Returns:
            Number of files deleted
        """
        if not os.path.exists(self.generated_dir):
            return 0
            
        count = 0
        current_time = time.time()
        max_age_seconds = max_age_hours * 3600
        
        try:
            for filename in os.listdir(self.generated_dir):
                filepath = os.path.join(self.generated_dir, filename)
                
                # Skip if not a file
                if not os.path.isfile(filepath):
                    continue
                    
                # Check age
                file_age = current_time - os.path.getmtime(filepath)
                
                if file_age > max_age_seconds:
                    try:
                        os.remove(filepath)
                        count += 1
                        logger.debug(f"Deleted old generated image: {filepath}")
                    except Exception as e:
                        logger.error(f"Failed to delete {filepath}: {e}")
                        
            if count > 0:
                logger.info(f"Cleaned up {count} old generated images")
                
        except Exception as e:
            logger.error(f"Error during image cleanup: {e}")
            
        return count

    def get_disk_usage(self) -> int:
        """
        Get size of generated images directory in bytes.
        
        Returns:
            Size in bytes
        """
        if not os.path.exists(self.generated_dir):
            return 0
            
        total_size = 0
        try:
            for dirpath, _, filenames in os.walk(self.generated_dir):
                for f in filenames:
                    fp = os.path.join(dirpath, f)
                    if not os.path.islink(fp):
                        total_size += os.path.getsize(fp)
        except Exception as e:
            logger.error(f"Error calculating disk usage: {e}")
            
        return total_size

# Global instance
resource_manager = ResourceManager()
