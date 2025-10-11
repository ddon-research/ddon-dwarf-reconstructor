"""Path utilities for cross-platform file operations."""

import re
import string


def sanitize_for_filesystem(name: str, replacement: str = "_") -> str:
    """Sanitize a string to be safe for use as a filename."""
    if not name:
        return "unnamed"
    
    # First handle C++ template syntax
    sanitized = name
    sanitized = sanitized.replace("::", "__")
    sanitized = sanitized.replace("<", "_")
    sanitized = sanitized.replace(">", "_")
    
    # Use standard library to define valid characters
    valid_chars = set(string.ascii_letters + string.digits + "_-.")
    sanitized = "".join(c if c in valid_chars else replacement for c in sanitized)
    
    # Collapse multiple replacement characters
    if replacement in sanitized:
        pattern = re.escape(replacement) + "+"
        sanitized = re.sub(pattern, replacement, sanitized)
    
    # Remove leading/trailing replacement characters
    sanitized = sanitized.strip(replacement)
    
    # Ensure we have something
    if not sanitized:
        sanitized = "unnamed"
    
    # Truncate if too long (leaving room for .h extension)
    if len(sanitized) > 200:
        sanitized = sanitized[:200].rstrip(replacement)
    
    return sanitized


def create_header_filename(class_name: str, suffix: str = "") -> str:
    """Create a safe header filename for a class."""
    base_name = sanitize_for_filesystem(class_name)
    if suffix:
        suffix = sanitize_for_filesystem(suffix)
        base_name = f"{base_name}_{suffix}"
    
    return f"{base_name}.h"
