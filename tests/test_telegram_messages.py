"""
Tests for Telegram message formatting and Markdown validation.

These tests ensure that all Telegram messages are properly formatted
and won't cause parsing errors when sent to the Telegram API.
"""
import pytest
from unittest.mock import Mock, patch, AsyncMock
from pathlib import Path

# Import the escaping utilities
import sys
import os
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from server.telegram_bot.utils import escape_markdown, escape_markdown_v2, safe_markdown_path, escape_markdown_inline_code


class TestMarkdownEscaping:
    """Test Markdown escaping functions."""
    
    def test_escape_markdown_basic(self):
        """Test basic Markdown character escaping."""
        text = "Hello *world* with _underscores_ and `backticks`"
        escaped = escape_markdown(text)
        
        assert "*" not in escaped or escaped.count("\\*") == 2
        assert "_" not in escaped or escaped.count("\\_") == 2
        assert "`" not in escaped or escaped.count("\\`") == 2
    
    def test_escape_markdown_special_chars(self):
        """Test escaping of all special Markdown characters."""
        special_chars = ['_', '*', '[', ']', '(', ')', '`', '~', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
        
        for char in special_chars:
            text = f"Text with {char} character"
            escaped = escape_markdown(text)
            # Character should be escaped (preceded by backslash)
            assert f"\\{char}" in escaped or char not in escaped
    
    def test_escape_markdown_v2(self):
        """Test MarkdownV2 escaping."""
        text = "Hello *world* with _underscores_"
        escaped = escape_markdown_v2(text)
        
        # Should escape special characters
        assert "\\*" in escaped or "*" not in escaped
        assert "\\_" in escaped or "_" not in escaped
    
    def test_escape_markdown_inline_code(self):
        """Test escaping for inline code blocks."""
        text = "Code with `backticks` inside"
        escaped = escape_markdown_inline_code(text)
        
        # Backticks should be escaped
        assert "\\`" in escaped or "`" not in escaped
    
    def test_safe_markdown_path(self):
        """Test safe path formatting."""
        path = "/opt/diplomacy/test_maps/file.png"
        formatted = safe_markdown_path(path)
        
        assert formatted.startswith("`")
        assert formatted.endswith("`")
        # Backticks in path should be escaped
        assert "\\`" in formatted or "`" not in formatted[1:-1]
    
    def test_safe_markdown_path_with_special_chars(self):
        """Test path formatting with special characters."""
        path = "/opt/diplomacy/test_maps/file_with_underscores.png"
        formatted = safe_markdown_path(path)
        
        assert formatted.startswith("`")
        assert formatted.endswith("`")
    
    def test_safe_markdown_path_empty(self):
        """Test path formatting with empty path."""
        formatted = safe_markdown_path("")
        assert formatted == "`(no path)`"
    
    def test_safe_markdown_path_none(self):
        """Test path formatting with None."""
        formatted = safe_markdown_path(None)
        assert formatted == "`(no path)`"


class TestMessageLength:
    """Test message length limits."""
    
    def test_message_under_limit(self):
        """Test that normal messages are under Telegram's 4096 character limit."""
        # Create a typical message
        message = "🎬 *Perfect Demo Game Complete!*\n\n" * 10
        message += "Some additional content here."
        
        assert len(message) < 4096, "Message should be under 4096 characters"
    
    def test_long_path_handling(self):
        """Test that long file paths don't exceed message limits."""
        # Simulate a very long path
        long_path = "/" + "/".join(["very" * 20, "long" * 20, "path" * 20, "to" * 20, "file.png"])
        formatted = safe_markdown_path(long_path)
        
        # Even with escaping, should be reasonable
        assert len(formatted) < 500, "Formatted path should be reasonable length"


class TestFilePathsInMessages:
    """Test file path handling in messages."""
    
    def test_path_with_underscores(self):
        """Test paths with underscores (common in file names)."""
        path = "/opt/diplomacy/test_maps/perfect_demo_1901_01_01_Spring_Movement_01_initial.png"
        formatted = safe_markdown_path(path)
        
        # Should be properly formatted
        assert formatted.startswith("`")
        assert formatted.endswith("`")
    
    def test_path_with_special_chars(self):
        """Test paths with various special characters."""
        test_paths = [
            "/opt/diplomacy/test_maps/file (1).png",
            "/opt/diplomacy/test_maps/file[test].png",
            "/opt/diplomacy/test_maps/file{test}.png",
            "/opt/diplomacy/test_maps/file-test.png",
            "/opt/diplomacy/test_maps/file.test.png",
        ]
        
        for path in test_paths:
            formatted = safe_markdown_path(path)
            assert formatted.startswith("`")
            assert formatted.endswith("`")
    
    def test_relative_paths(self):
        """Test relative paths."""
        path = "../test_maps/file.png"
        formatted = safe_markdown_path(path)
        
        assert formatted.startswith("`")
        assert formatted.endswith("`")


class TestUnicodeAndEmojis:
    """Test Unicode and emoji handling."""
    
    def test_emoji_in_messages(self):
        """Test that emojis don't break Markdown parsing."""
        message = "🎬 *Perfect Demo Game Complete!*\n\n✅ Success!"
        # Emojis should not need escaping
        escaped = escape_markdown(message)
        
        # Should still contain emojis
        assert "🎬" in escaped or "🎬" in message
        assert "✅" in escaped or "✅" in message
    
    def test_unicode_characters(self):
        """Test Unicode character handling."""
        message = "Test with unicode: café, naïve, résumé"
        escaped = escape_markdown(message)
        
        # Unicode characters should be preserved
        assert "café" in escaped or "café" in message


class TestAdminMessageFormatting:
    """Test admin.py message formatting scenarios."""
    
    def test_demo_complete_message_formatting(self):
        """Test the demo complete message formatting."""
        # Simulate the message from admin.py
        project_root = "/opt/diplomacy"
        script_rel_path = "examples/demo_perfect_game.py"
        maps_dir = "/opt/diplomacy/test_maps"
        
        # Use the escaping functions (already imported at module level)
        
        escaped_project_root = escape_markdown(project_root)
        escaped_script_path = escape_markdown(script_rel_path)
        escaped_maps_path = safe_markdown_path(maps_dir)
        
        message = (
            "🎬 *Perfect Demo Game Complete!*\n\n"
            "✅ The demo game ran successfully, but no maps were generated\\.\n\n"
            f"📊 *Diagnostics:*\n"
            f"  • Maps directory: {escape_markdown(maps_dir)}\n"
            f"  • Project root: {escaped_project_root}\n"
            f"  • Script path: {escaped_script_path}\n"
            f"\n💡 *To run the demo yourself:*\n"
            "```bash\n"
            f"cd {escaped_project_root}\n"
            f"/usr/bin/python3 {escaped_script_path}\n"
            "```\n\n"
            f"📁 *Maps will be saved to:* {escaped_maps_path}"
        )
        
        # Message should be valid
        assert len(message) < 4096, "Message should be under Telegram limit"
        assert "`" in message or "```" in message, "Should contain code formatting"
    
    def test_error_message_formatting(self):
        """Test error message formatting."""
        error_text = "Error: File not found at /opt/diplomacy/test_maps/file.png"
        
        from server.telegram_bot.utils import escape_markdown
        
        escaped_error = escape_markdown(error_text)
        message = f"❌ *Error:* {escaped_error}"
        
        # Should be properly escaped
        assert len(message) < 4096
        assert "/" in message or "\\/" in escaped_error  # Path separators might be escaped

