import unittest
import sys
import os

# Add parent directory to path to import modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from yail_command_parser import (
    CommandValidator, 
    CommandParser,
    GRAPHICS_8,
    GRAPHICS_9,
    VBXE
)

class TestCommandParser(unittest.TestCase):
    def setUp(self):
        self.validator = CommandValidator()
        self.parser = CommandParser()

    # --- Validator Tests ---

    def test_validate_gen_command(self):
        # Valid
        valid, msg = self.validator.validate_gen_command(["gen", "a", "cute", "cat"])
        self.assertTrue(valid)
        self.assertIsNone(msg)

        # Invalid - missing prompt
        valid, msg = self.validator.validate_gen_command(["gen"])
        self.assertFalse(valid)
        self.assertEqual(msg, "gen command requires a prompt")
        
        # Invalid - empty prompt
        valid, msg = self.validator.validate_gen_command(["gen", "   "])
        self.assertFalse(valid)
        self.assertEqual(msg, "Prompt cannot be empty")

    def test_validate_search_command(self):
        # Valid
        valid, msg = self.validator.validate_search_command(["search", "cats"])
        self.assertTrue(valid)
        self.assertIsNone(msg)

        # Invalid - missing terms
        valid, msg = self.validator.validate_search_command(["search"])
        self.assertFalse(valid)
        self.assertEqual(msg, "search command requires search terms")

    def test_validate_gfx_command(self):
        # Valid
        valid, msg = self.validator.validate_gfx_command(["gfx", str(GRAPHICS_8)])
        self.assertTrue(valid)
        
        # Invalid - invalid mode
        valid, msg = self.validator.validate_gfx_command(["gfx", "999"])
        self.assertFalse(valid)
        self.assertIn("Invalid graphics mode", msg)
        
        # Invalid - non-int
        valid, msg = self.validator.validate_gfx_command(["gfx", "abc"])
        self.assertFalse(valid)
        self.assertIn("must be an integer", msg)

    def test_validate_config_command(self):
        # Valid query
        valid, msg = self.validator.validate_config_command(["openai-config"])
        self.assertTrue(valid)
        
        # Valid set
        valid, msg = self.validator.validate_config_command(["openai-config", "size", "1024x1024"])
        self.assertTrue(valid)
        
        # Invalid param
        valid, msg = self.validator.validate_config_command(["openai-config", "badparam", "value"])
        self.assertFalse(valid)
        self.assertIn("Invalid config parameter", msg)
        
        # Missing value
        valid, msg = self.validator.validate_config_command(["openai-config", "size"])
        self.assertFalse(valid)
        self.assertIn("requires a value", msg)

    def test_validate_command_router(self):
        """Test the main validate_command router."""
        # Unknown command
        valid, msg = self.validator.validate_command(["unknown", "arg"])
        self.assertFalse(valid)
        self.assertIn("Unknown command", msg)
        
        # Known command (files) - no args needed
        valid, msg = self.validator.validate_command(["files"])
        self.assertTrue(valid)

    # --- Parser Tests ---

    def test_parse_command_valid(self):
        raw = b"gen a dog\r\n"
        valid, tokens, error = self.parser.parse_command(raw)
        self.assertTrue(valid)
        self.assertEqual(tokens, ["gen", "a", "dog"])
        self.assertIsNone(error)

    def test_parse_command_invalid(self):
        raw = b"gfx 999\r\n"
        valid, tokens, error = self.parser.parse_command(raw)
        self.assertFalse(valid)
        self.assertEqual(tokens, ["gfx", "999"])
        self.assertIsNotNone(error)

    def test_extract_prompt(self):
        tokens = ["gen", "hello", "world"]
        prompt = self.parser.extract_prompt(tokens)
        self.assertEqual(prompt, "hello world")

    def test_extract_graphics_mode(self):
        tokens = ["gfx", "2"]
        mode = self.parser.extract_graphics_mode(tokens)
        self.assertEqual(mode, 2)
        
        tokens = ["gfx", "bad"]
        mode = self.parser.extract_graphics_mode(tokens)
        self.assertIsNone(mode)

    def test_extract_config_param(self):
        tokens = ["openai-config", "size", "1024x1024"]
        param, value = self.parser.extract_config_param(tokens)
        self.assertEqual(param, "size")
        self.assertEqual(value, "1024x1024")
        
        tokens = ["openai-config", "size"]
        param, value = self.parser.extract_config_param(tokens)
        self.assertEqual(param, "size")
        self.assertIsNone(value)

if __name__ == '__main__':
    unittest.main()
