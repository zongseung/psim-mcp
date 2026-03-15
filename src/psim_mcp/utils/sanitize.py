"""Output sanitization utilities for MCP responses."""

import re

# Max response size in bytes (50KB as per security docs)
MAX_RESPONSE_SIZE = 50_000

def sanitize_for_llm_context(text: str) -> str:
    """Remove control characters and suspicious patterns from text before returning to LLM."""
    # Remove control characters except newline and tab
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
    # Remove potential prompt injection patterns
    text = re.sub(r'<\|.*?\|>', '', text)
    text = re.sub(r'\[INST\].*?\[/INST\]', '', text, flags=re.DOTALL)
    text = re.sub(r'<system>.*?</system>', '', text, flags=re.DOTALL)
    return text

def sanitize_path_for_display(path: str) -> str:
    """Replace full system path with just filename for user-facing messages."""
    from pathlib import PurePosixPath, PureWindowsPath
    try:
        # Try both path styles
        name = PureWindowsPath(path).name if '\\' in path else PurePosixPath(path).name
        return name if name else path
    except Exception:
        return "<path>"

def truncate_response(response_str: str, max_size: int = MAX_RESPONSE_SIZE) -> str:
    """Truncate response if it exceeds max size."""
    if len(response_str.encode('utf-8')) <= max_size:
        return response_str
    # Truncate and add warning
    truncated = response_str[:max_size - 100]
    return truncated + '\n... [응답이 크기 제한(50KB)을 초과하여 잘렸습니다]'

def sanitize_component_name(name: str) -> str:
    """Sanitize component name from PSIM data."""
    # Only allow alphanumeric, underscore, hyphen, dot
    return re.sub(r'[^A-Za-z0-9_\-.]', '_', name)
