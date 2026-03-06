"""Local tools for general-purpose tasks

This package contains tools that don't require specific AWS services:
- Weather lookup
- URL fetching and content extraction
- Data visualization
- Cludo search (Boise State University)
"""

from .weather import get_current_weather
from .url_fetcher import fetch_url_content
from .visualization import create_visualization
from .cludo_search import search_boise_state

__all__ = [
    'get_current_weather',
    'fetch_url_content',
    'create_visualization',
    'search_boise_state',
]
