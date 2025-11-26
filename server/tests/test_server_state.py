import unittest
import threading
import time
from concurrent.futures import ThreadPoolExecutor
import sys
import os

# Add parent directory to path to import modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from yail_server_state import ServerState

class TestServerState(unittest.TestCase):
    def setUp(self):
        self.state = ServerState()

    def test_initial_state(self):
        """Test initial state values."""
        self.assertEqual(self.state.get_connections(), 0)
        self.assertEqual(self.state.get_filenames_count(), 0)
        self.assertIsNone(self.state.get_last_prompt())
        self.assertIsNone(self.state.get_last_gen_model())

    def test_filename_management(self):
        """Test filename management operations."""
        # Add filenames
        self.state.add_filename("test1.jpg")
        self.state.add_filename("test2.jpg")
        self.assertEqual(self.state.get_filenames_count(), 2)
        
        # Test duplicate prevention
        self.state.add_filename("test1.jpg")
        self.assertEqual(self.state.get_filenames_count(), 2)
        
        # Test random retrieval
        filename = self.state.get_random_filename()
        self.assertIn(filename, ["test1.jpg", "test2.jpg"])
        
        # Test clear
        self.state.clear_filenames()
        self.assertEqual(self.state.get_filenames_count(), 0)
        self.assertIsNone(self.state.get_random_filename())

    def test_connection_management(self):
        """Test connection counter operations."""
        self.assertEqual(self.state.increment_connections(), 1)
        self.assertEqual(self.state.increment_connections(), 2)
        self.assertEqual(self.state.decrement_connections(), 1)
        self.assertEqual(self.state.decrement_connections(), 0)
        
        # Test floor at 0
        self.assertEqual(self.state.decrement_connections(), 0)

    def test_prompt_management(self):
        """Test prompt storage."""
        self.state.set_last_prompt("test prompt")
        self.assertEqual(self.state.get_last_prompt(), "test prompt")
        
        self.state.set_last_prompt("new prompt")
        self.assertEqual(self.state.get_last_prompt(), "new prompt")

    def test_model_management(self):
        """Test model storage."""
        self.state.set_last_gen_model("dall-e-3")
        self.assertEqual(self.state.get_last_gen_model(), "dall-e-3")

    def test_thread_safety(self):
        """Test thread safety of connection counter."""
        target_count = 1000
        
        def increment_many():
            for _ in range(target_count):
                self.state.increment_connections()
                
        def decrement_many():
            for _ in range(target_count):
                self.state.decrement_connections()

        # Run concurrent increments
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(increment_many) for _ in range(4)]
            for future in futures:
                future.result()
                
        self.assertEqual(self.state.get_connections(), target_count * 4)
        
        # Run concurrent decrements
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(decrement_many) for _ in range(4)]
            for future in futures:
                future.result()
                
        self.assertEqual(self.state.get_connections(), 0)

if __name__ == '__main__':
    unittest.main()
