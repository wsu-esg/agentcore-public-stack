"""
Global state management for stream processor

Note: This module is deprecated. The new stream processor is stateless.
The functions are kept for backward compatibility but return None.
"""
from typing import Optional


def set_global_stream_processor(processor: any) -> None:
    """
    DEPRECATED: Set the global stream processor instance

    This function is a no-op kept for backward compatibility.
    The new stream processor is stateless and doesn't require global state.
    """
    pass


def get_global_stream_processor() -> Optional[any]:
    """
    DEPRECATED: Get the global stream processor instance

    Returns None as the new stream processor is stateless.
    """
    return None
