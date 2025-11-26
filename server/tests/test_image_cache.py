import unittest
import sys
import os

# Add parent directory to path to import modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from yail_image_cache import ImageCache

class TestImageCache(unittest.TestCase):
    def setUp(self):
        self.cache = ImageCache(max_size_mb=1, max_items=3)

    def test_basic_put_get(self):
        data = b"12345"
        self.cache.put("key1", data)
        
        retrieved = self.cache.get("key1")
        self.assertEqual(retrieved, data)
        
        self.assertIsNone(self.cache.get("missing"))

    def test_lru_eviction_by_count(self):
        self.cache.put("key1", b"1")
        self.cache.put("key2", b"2")
        self.cache.put("key3", b"3")
        
        # Cache is full (3 items)
        self.assertEqual(self.cache.stats()['items'], 3)
        
        # Access key1 to make it most recently used
        self.cache.get("key1")
        
        # Add key4, should evict LRU (which is now key2, since key1 was accessed)
        self.cache.put("key4", b"4")
        
        self.assertEqual(self.cache.stats()['items'], 3)
        self.assertIsNotNone(self.cache.get("key1"))
        self.assertIsNotNone(self.cache.get("key3"))
        self.assertIsNotNone(self.cache.get("key4"))
        self.assertIsNone(self.cache.get("key2")) # key2 should be gone

    def test_eviction_by_size(self):
        # Max size is 1MB. 
        # Let's make a cache with small size for testing
        small_cache = ImageCache(max_size_mb=0.00001, max_items=10) # ~10 bytes
        
        small_cache.put("key1", b"12345") # 5 bytes
        small_cache.put("key2", b"67890") # 5 bytes -> total 10 bytes
        
        self.assertEqual(small_cache.stats()['items'], 2)
        
        small_cache.put("key3", b"abc") # 3 bytes -> total 13 bytes > 10
        
        # key1 should be evicted
        self.assertIsNone(small_cache.get("key1"))
        self.assertIsNotNone(small_cache.get("key2"))
        self.assertIsNotNone(small_cache.get("key3"))

    def test_too_large_item(self):
        small_cache = ImageCache(max_size_mb=0.000001, max_items=10) # ~1 byte
        small_cache.put("key1", b"too big")
        
        self.assertIsNone(small_cache.get("key1"))
        self.assertEqual(small_cache.stats()['items'], 0)

    def test_clear(self):
        self.cache.put("key1", b"data")
        self.cache.clear()
        self.assertEqual(self.cache.stats()['items'], 0)
        self.assertEqual(self.cache.stats()['size_bytes'], 0)

if __name__ == '__main__':
    unittest.main()
