"""Project-specific exceptions."""


class LogmaskError(Exception):
    """Base class for logmask-drain errors."""


class MaskValidationError(LogmaskError):
    """Raised when a mask bundle fails validation."""


class BundleError(LogmaskError):
    """Raised when a mask bundle cannot be loaded or interpreted."""

