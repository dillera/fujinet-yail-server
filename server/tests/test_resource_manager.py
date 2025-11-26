import unittest
import sys
import os
import time
import shutil
import tempfile

# Add parent directory to path to import modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from yail_resource_manager import ResourceManager

class TestResourceManager(unittest.TestCase):
    def setUp(self):
        # Create a temp directory
        self.test_dir = tempfile.mkdtemp()
        self.manager = ResourceManager(generated_dir=self.test_dir)

    def tearDown(self):
        # Remove temp directory
        shutil.rmtree(self.test_dir)

    def test_cleanup_old_files(self):
        # Create an old file (25 hours old)
        old_file = os.path.join(self.test_dir, "old.png")
        with open(old_file, 'w') as f:
            f.write("test")
        
        # Set mtime to 25 hours ago
        past_time = time.time() - (25 * 3600)
        os.utime(old_file, (past_time, past_time))
        
        # Create a new file (1 hour old)
        new_file = os.path.join(self.test_dir, "new.png")
        with open(new_file, 'w') as f:
            f.write("test")
            
        # Run cleanup
        deleted = self.manager.cleanup_generated_images(max_age_hours=24)
        
        self.assertEqual(deleted, 1)
        self.assertFalse(os.path.exists(old_file))
        self.assertTrue(os.path.exists(new_file))

    def test_get_disk_usage(self):
        file1 = os.path.join(self.test_dir, "file1.txt")
        with open(file1, 'w') as f:
            f.write("12345") # 5 bytes
            
        usage = self.manager.get_disk_usage()
        self.assertEqual(usage, 5)

if __name__ == '__main__':
    unittest.main()
