"""
Utility functions for Telegram bot, including Markdown escaping.
"""
import re
from typing import Union


def escape_markdown(text: Union[str, None]) -> str:
    """
    Escape special characters for Telegram Markdown (legacy mode).
    
    Characters that need escaping: _ * [ ] ( ) ` ~ > # + - = | { } . !
    
    Args:
        text: Text to escape
        
    Returns:
        Escaped text safe for Telegram Markdown parsing
    """
    if not text:
        return text
    
    # Characters that need escaping in Markdown mode
    escape_chars = ['_', '*', '[', ']', '(', ')', '`', '~', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    
    result = text
    for char in escape_chars:
        result = result.replace(char, f'\\{char}')
    
    return result


def escape_markdown_v2(text: Union[str, None]) -> str:
    """
    Escape special characters for Telegram MarkdownV2.
    
    Characters that need escaping: _ * [ ] ( ) ~ ` > # + - = | { } . !
    
    Args:
        text: Text to escape
        
    Returns:
        Escaped text safe for Telegram MarkdownV2 parsing
    """
    if not text:
        return text
    
    # Characters that need escaping in MarkdownV2 mode
    escape_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    
    result = text
    for char in escape_chars:
        result = result.replace(char, f'\\{char}')
    
    return result


def escape_markdown_inline_code(text: Union[str, None]) -> str:
    """
    Escape text for use inside inline code blocks (backticks).
    
    Only backticks need to be escaped inside code blocks.
    
    Args:
        text: Text to escape for inline code
        
    Returns:
        Escaped text safe for inline code blocks
    """
    if not text:
        return text
    
    # Only backticks need escaping inside code blocks
    return text.replace('`', '\\`')


def safe_markdown_path(path: Union[str, None]) -> str:
    """
    Safely format a file path in Markdown, escaping special characters.
    
    This is a convenience function for formatting file paths that will be
    displayed in Telegram messages with Markdown formatting.
    
    Args:
        path: File path to format
        
    Returns:
        Escaped path safe for Markdown, wrapped in backticks for code formatting
    """
    if not path:
        return '`(no path)`'
    
    # Escape backticks in the path
    escaped = escape_markdown_inline_code(path)
    return f'`{escaped}`'

