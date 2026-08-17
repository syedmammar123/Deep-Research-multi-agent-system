"""Tavily web search."""

import logging

from tavily import TavilyClient

from research.citations import Source
from research.config import TVLY_API_KEY
from research.resilience import tavily_retry

logger = logging.getLogger(__name__)

MAX_RESULTS = 5


@tavily_retry
def _search(query: str) -> dict:
    """Kept separate so retries fire before `search_web` swallows the exception."""
    client = TavilyClient(api_key=TVLY_API_KEY)
    return client.search(query, search_depth="advanced", max_results=MAX_RESULTS)


def search_web(query: str) -> list[Source]:
    """Search the web, returning sources numbered locally to this one search.

    A failed search degrades to no sources rather than raising, so one dead
    branch doesn't discard what the others found.
    """
    try:
        results = _search(query).get("results", [])
    except Exception as e:
        logger.warning("Tavily search failed for %r: %s", query, e)
        return []

    return [
        Source(
            id=i,
            title=result.get("title") or "Untitled",
            url=result.get("url") or "",
            content=result.get("content", ""),
        )
        for i, result in enumerate(results, 1)
        if result.get("url")  # a source with no URL can't be cited
    ]
