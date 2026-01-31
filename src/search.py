"""
Search API Implementations for Where They Walked

Provides web search functionality using various providers:
- SerpAPI (Google Search)
- Brave Search API
- Mock search for testing

Configure via environment variables:
- SERPAPI_KEY: SerpAPI key (for Google search results)
- BRAVE_API_KEY: Brave Search API key
"""

import os
import json
import time
from typing import Optional, Callable
from urllib.parse import urlencode
from urllib.request import urlopen, Request
from urllib.error import HTTPError, URLError


class SearchError(Exception):
    """Error during search operation."""
    pass


def create_serpapi_search(api_key: str = None,
                           num_results: int = 10,
                           timeout: int = 30) -> Callable[[str], str]:
    """
    Create a search function using SerpAPI (Google Search).

    SerpAPI provides parsed Google search results.
    Sign up at: https://serpapi.com/

    Args:
        api_key: SerpAPI key (or set SERPAPI_KEY env var)
        num_results: Number of results to return
        timeout: Request timeout in seconds

    Returns:
        Function(query) -> search results text
    """
    api_key = api_key or os.environ.get("SERPAPI_KEY")
    if not api_key:
        raise ValueError("SerpAPI key required. Set SERPAPI_KEY environment variable or pass api_key.")

    def search(query: str) -> str:
        """Search Google via SerpAPI and return formatted results."""
        params = {
            "api_key": api_key,
            "q": query,
            "engine": "google",
            "num": num_results,
            "gl": "us",
            "hl": "en"
        }

        url = f"https://serpapi.com/search?{urlencode(params)}"

        try:
            req = Request(url, headers={"Accept": "application/json"})
            with urlopen(req, timeout=timeout) as response:
                data = json.loads(response.read().decode('utf-8'))
        except HTTPError as e:
            raise SearchError(f"SerpAPI HTTP error {e.code}: {e.reason}")
        except URLError as e:
            raise SearchError(f"SerpAPI connection error: {e.reason}")
        except json.JSONDecodeError as e:
            raise SearchError(f"SerpAPI invalid JSON response: {e}")

        # Format results as text for AI synthesis
        results = []

        # Add knowledge panel if present
        if "knowledge_graph" in data:
            kg = data["knowledge_graph"]
            results.append(f"== Knowledge Panel ==")
            if "title" in kg:
                results.append(f"Title: {kg['title']}")
            if "description" in kg:
                results.append(f"Description: {kg['description']}")
            if "source" in kg:
                results.append(f"Source: {kg['source'].get('link', '')}")
            results.append("")

        # Add organic search results
        if "organic_results" in data:
            results.append("== Search Results ==\n")
            for i, item in enumerate(data["organic_results"], 1):
                results.append(f"[{i}] {item.get('title', 'No title')}")
                results.append(f"URL: {item.get('link', '')}")
                if "snippet" in item:
                    results.append(f"Snippet: {item['snippet']}")
                if "rich_snippet" in item:
                    rich = item["rich_snippet"]
                    if "top" in rich:
                        for key, val in rich["top"].items():
                            results.append(f"{key}: {val}")
                results.append("")

        # Add related questions/people also ask
        if "related_questions" in data:
            results.append("== Related Information ==")
            for q in data["related_questions"][:3]:
                results.append(f"Q: {q.get('question', '')}")
                if "snippet" in q:
                    results.append(f"A: {q['snippet']}")
                results.append("")

        return "\n".join(results) if results else "No search results found."

    return search


def create_brave_search(api_key: str = None,
                        num_results: int = 10,
                        timeout: int = 30) -> Callable[[str], str]:
    """
    Create a search function using Brave Search API.

    Brave Search offers privacy-focused search with good coverage.
    Sign up at: https://brave.com/search/api/

    Args:
        api_key: Brave API key (or set BRAVE_API_KEY env var)
        num_results: Number of results to return
        timeout: Request timeout in seconds

    Returns:
        Function(query) -> search results text
    """
    api_key = api_key or os.environ.get("BRAVE_API_KEY")
    if not api_key:
        raise ValueError("Brave API key required. Set BRAVE_API_KEY environment variable or pass api_key.")

    def search(query: str) -> str:
        """Search via Brave Search API and return formatted results."""
        params = {
            "q": query,
            "count": num_results,
            "country": "us"
        }

        url = f"https://api.search.brave.com/res/v1/web/search?{urlencode(params)}"

        headers = {
            "Accept": "application/json",
            "X-Subscription-Token": api_key
        }

        try:
            req = Request(url, headers=headers)
            with urlopen(req, timeout=timeout) as response:
                data = json.loads(response.read().decode('utf-8'))
        except HTTPError as e:
            raise SearchError(f"Brave Search HTTP error {e.code}: {e.reason}")
        except URLError as e:
            raise SearchError(f"Brave Search connection error: {e.reason}")
        except json.JSONDecodeError as e:
            raise SearchError(f"Brave Search invalid JSON response: {e}")

        # Format results as text for AI synthesis
        results = []

        # Add infobox if present
        if "infobox" in data:
            infobox = data["infobox"]
            results.append("== Information Box ==")
            if "title" in infobox:
                results.append(f"Title: {infobox['title']}")
            if "description" in infobox:
                results.append(f"Description: {infobox['description']}")
            if "url" in infobox:
                results.append(f"Source: {infobox['url']}")
            results.append("")

        # Add web results
        web_results = data.get("web", {}).get("results", [])
        if web_results:
            results.append("== Search Results ==\n")
            for i, item in enumerate(web_results, 1):
                results.append(f"[{i}] {item.get('title', 'No title')}")
                results.append(f"URL: {item.get('url', '')}")
                if "description" in item:
                    results.append(f"Snippet: {item['description']}")
                if "extra_snippets" in item:
                    for snippet in item["extra_snippets"][:2]:
                        results.append(f"  - {snippet}")
                results.append("")

        # Add FAQ results if present
        faq_results = data.get("faq", {}).get("results", [])
        if faq_results:
            results.append("== FAQ ==")
            for faq in faq_results[:3]:
                results.append(f"Q: {faq.get('question', '')}")
                results.append(f"A: {faq.get('answer', '')}")
                results.append("")

        return "\n".join(results) if results else "No search results found."

    return search


def create_mock_search() -> Callable[[str], str]:
    """
    Create a mock search function for testing without API calls.
    Returns placeholder text indicating mock mode.
    """
    def search(query: str) -> str:
        return f"[Mock search results for: {query}]\n\nNo real search results available in mock mode."

    return search


def create_search_with_retry(search_fn: Callable[[str], str],
                              max_retries: int = 3,
                              base_delay: float = 1.0) -> Callable[[str], str]:
    """
    Wrap a search function with retry logic.

    Args:
        search_fn: Base search function
        max_retries: Maximum number of retry attempts
        base_delay: Base delay between retries (exponential backoff)

    Returns:
        Wrapped search function with retry logic
    """
    def search_with_retry(query: str) -> str:
        last_error = None

        for attempt in range(max_retries + 1):
            try:
                return search_fn(query)
            except SearchError as e:
                last_error = e
                if attempt < max_retries:
                    delay = base_delay * (2 ** attempt)
                    time.sleep(delay)

        # All retries exhausted
        raise last_error or SearchError("Search failed after retries")

    return search_with_retry


def create_rate_limited_search(search_fn: Callable[[str], str],
                                min_interval: float = 1.0) -> Callable[[str], str]:
    """
    Wrap a search function with rate limiting.

    Args:
        search_fn: Base search function
        min_interval: Minimum seconds between requests

    Returns:
        Wrapped search function with rate limiting
    """
    last_request_time = [0.0]  # Mutable for closure

    def rate_limited_search(query: str) -> str:
        elapsed = time.time() - last_request_time[0]
        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)

        last_request_time[0] = time.time()
        return search_fn(query)

    return rate_limited_search


def create_auto_search(prefer: str = "serpapi") -> Optional[Callable[[str], str]]:
    """
    Automatically create the best available search function.

    Checks environment for API keys and returns a configured search function,
    or None if no API keys are available.

    Args:
        prefer: Preferred provider if multiple available ("serpapi" or "brave")

    Returns:
        Configured search function or None
    """
    serpapi_key = os.environ.get("SERPAPI_KEY")
    brave_key = os.environ.get("BRAVE_API_KEY")

    if prefer == "serpapi" and serpapi_key:
        search_fn = create_serpapi_search(serpapi_key)
        return create_rate_limited_search(create_search_with_retry(search_fn))

    if prefer == "brave" and brave_key:
        search_fn = create_brave_search(brave_key)
        return create_rate_limited_search(create_search_with_retry(search_fn))

    # Try both in order of preference
    if serpapi_key:
        search_fn = create_serpapi_search(serpapi_key)
        return create_rate_limited_search(create_search_with_retry(search_fn))

    if brave_key:
        search_fn = create_brave_search(brave_key)
        return create_rate_limited_search(create_search_with_retry(search_fn))

    return None


def get_available_providers() -> list[str]:
    """
    Get list of search providers with configured API keys.

    Returns:
        List of available provider names
    """
    available = []

    if os.environ.get("SERPAPI_KEY"):
        available.append("serpapi")
    if os.environ.get("BRAVE_API_KEY"):
        available.append("brave")

    return available
