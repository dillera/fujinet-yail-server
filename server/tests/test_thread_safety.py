#!/usr/bin/env python3
"""
Test script to verify thread safety of ServerState.
Tests concurrent access from multiple threads.
"""

import threading
import time
import logging
from yail_server_state import server_state

# Set up logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - [%(threadName)s] - %(message)s')
logger = logging.getLogger(__name__)


def test_concurrent_filenames():
    """Test concurrent filename additions."""
    logger.info("Testing concurrent filename additions...")
    
    def add_files(thread_id, count):
        for i in range(count):
            filename = f"file_{thread_id}_{i}.jpg"
            server_state.add_filename(filename)
            time.sleep(0.001)  # Small delay to increase contention
    
    # Clear state
    server_state.clear_filenames()
    
    # Create threads
    threads = []
    for i in range(5):
        t = threading.Thread(target=add_files, args=(i, 10), name=f"FileAdder-{i}")
        threads.append(t)
        t.start()
    
    # Wait for all threads
    for t in threads:
        t.join()
    
    # Verify
    count = server_state.get_filenames_count()
    expected = 5 * 10
    assert count == expected, f"Expected {expected} files, got {count}"
    logger.info(f"✓ Successfully added {count} files from 5 threads")


def test_concurrent_connections():
    """Test concurrent connection counter updates."""
    logger.info("Testing concurrent connection counter updates...")
    
    def simulate_connections(thread_id, count):
        for i in range(count):
            conn_count = server_state.increment_connections()
            time.sleep(0.001)
            server_state.decrement_connections()
    
    # Reset state
    initial_count = server_state.get_connections()
    
    # Create threads
    threads = []
    for i in range(10):
        t = threading.Thread(target=simulate_connections, args=(i, 5), name=f"ConnSim-{i}")
        threads.append(t)
        t.start()
    
    # Wait for all threads
    for t in threads:
        t.join()
    
    # Verify
    final_count = server_state.get_connections()
    assert final_count == initial_count, f"Expected {initial_count}, got {final_count}"
    logger.info(f"✓ Connection counter is correct: {final_count}")


def test_concurrent_prompts():
    """Test concurrent prompt updates."""
    logger.info("Testing concurrent prompt updates...")
    
    results = []
    
    def update_prompt(thread_id, count):
        for i in range(count):
            prompt = f"prompt_{thread_id}_{i}"
            server_state.set_last_prompt(prompt)
            retrieved = server_state.get_last_prompt()
            results.append((prompt, retrieved))
            time.sleep(0.001)
    
    # Create threads
    threads = []
    for i in range(5):
        t = threading.Thread(target=update_prompt, args=(i, 5), name=f"PromptUpdater-{i}")
        threads.append(t)
        t.start()
    
    # Wait for all threads
    for t in threads:
        t.join()
    
    # Verify all prompts were retrievable
    assert len(results) == 25, f"Expected 25 results, got {len(results)}"
    logger.info(f"✓ Successfully updated and retrieved {len(results)} prompts")


def test_random_filename_selection():
    """Test random filename selection with concurrent access."""
    logger.info("Testing random filename selection...")
    
    # Add some files
    server_state.clear_filenames()
    for i in range(10):
        server_state.add_filename(f"image_{i}.jpg")
    
    selected_files = []
    lock = threading.Lock()
    
    def select_files(thread_id, count):
        for i in range(count):
            filename = server_state.get_random_filename()
            if filename:
                with lock:
                    selected_files.append(filename)
            time.sleep(0.001)
    
    # Create threads
    threads = []
    for i in range(5):
        t = threading.Thread(target=select_files, args=(i, 10), name=f"FileSelector-{i}")
        threads.append(t)
        t.start()
    
    # Wait for all threads
    for t in threads:
        t.join()
    
    # Verify
    assert len(selected_files) == 50, f"Expected 50 selections, got {len(selected_files)}"
    logger.info(f"✓ Successfully selected {len(selected_files)} files from 5 threads")


def test_state_representation():
    """Test string representation of state."""
    logger.info("Testing state representation...")
    
    server_state.clear_filenames()
    server_state.add_filename("test1.jpg")
    server_state.add_filename("test2.jpg")
    server_state.increment_connections()
    server_state.set_last_prompt("test prompt")
    
    state_str = repr(server_state)
    logger.info(f"State: {state_str}")
    
    assert "connections=1" in state_str
    assert "filenames=2" in state_str
    assert "test prompt" in state_str
    logger.info("✓ State representation is correct")


def main():
    """Run all tests."""
    logger.info("=" * 60)
    logger.info("Thread Safety Tests for ServerState")
    logger.info("=" * 60)
    
    try:
        test_concurrent_filenames()
        test_concurrent_connections()
        test_concurrent_prompts()
        test_random_filename_selection()
        test_state_representation()
        
        logger.info("=" * 60)
        logger.info("✓ ALL TESTS PASSED")
        logger.info("=" * 60)
        return 0
        
    except AssertionError as e:
        logger.error(f"✗ TEST FAILED: {e}")
        return 1
    except Exception as e:
        logger.error(f"✗ UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())
