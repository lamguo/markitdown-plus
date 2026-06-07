"""Custom exceptions used by markitdown-plus."""


class MarkItDownPlusError(Exception):
    """Base exception for markitdown-plus."""


class ConversionError(MarkItDownPlusError):
    """Raised when a file cannot be converted."""


class DependencyError(MarkItDownPlusError):
    """Raised when an optional or required dependency is missing."""
