"""Shared exception for the offline transport guard and its tests."""


class UnexpectedNetwork(BaseException):
    """Bypass the plugin's broad Exception handlers so accidental I/O always fails."""
