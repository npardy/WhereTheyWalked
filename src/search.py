"""
Search API Implementations for Where They Walked

Provides web search functionality using various providers:
- SerpAPI (Google Search)
- Brave Search API
- Combined search (both providers, deduplicated)
- Mock search for testing

Deep search can fetch full page content from search results.
For JavaScript-heavy sites (Geni, FamilySearch, etc.), ScrapingBee
can be used as a fallback for rendering.

Configure via environment variables:
- SERPAPI_KEY: SerpAPI key (for Google search results)
- BRAVE_API_KEY: Brave Search API key
- SCRAPINGBEE_API_KEY: ScrapingBee key (optional, for JS-heavy sites)
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


def create_combined_search(timeout: int = 30) -> Callable[[str], str]:
    """
    Create a search function that combines results from both SerpAPI and Brave.

    Runs both searches, dedupes by URL, and combines unique results.
    This provides better coverage at slightly higher cost.

    Args:
        timeout: Request timeout in seconds per provider

    Returns:
        Function(query) -> combined deduped search results text

    Raises:
        ValueError: If neither API key is configured
    """
    import re

    serpapi_key = os.environ.get("SERPAPI_KEY")
    brave_key = os.environ.get("BRAVE_API_KEY")

    if not serpapi_key and not brave_key:
        raise ValueError("At least one search API key required (SERPAPI_KEY or BRAVE_API_KEY)")

    # Create individual search functions
    serp_search = None
    brave_search = None

    if serpapi_key:
        serp_search = create_serpapi_search(serpapi_key, timeout=timeout)
    if brave_key:
        brave_search = create_brave_search(brave_key, timeout=timeout)

    def _parse_results(text: str) -> list[dict]:
        """Parse search results text into structured list."""
        results = []
        current = {}

        for line in text.split('\n'):
            line = line.strip()
            if not line:
                if current and current.get('url'):
                    results.append(current)
                current = {}
            elif line.startswith('[') and ']' in line:
                # New result: [1] Title
                if current and current.get('url'):
                    results.append(current)
                title = line.split(']', 1)[1].strip() if ']' in line else line
                current = {'title': title}
            elif line.startswith('URL:'):
                current['url'] = line[4:].strip()
            elif line.startswith('Snippet:'):
                current['snippet'] = line[8:].strip()
            elif current and 'snippet' not in current and not line.startswith('=='):
                # Additional content for snippet
                current['snippet'] = current.get('snippet', '') + ' ' + line

        # Don't forget last result
        if current and current.get('url'):
            results.append(current)

        return results

    def _format_results(results: list[dict]) -> str:
        """Format deduped results back to text."""
        lines = ["== Combined Search Results ==\n"]
        for i, r in enumerate(results, 1):
            lines.append(f"[{i}] {r.get('title', 'No title')}")
            lines.append(f"URL: {r.get('url', '')}")
            if r.get('snippet'):
                lines.append(f"Snippet: {r['snippet']}")
            if r.get('source'):
                lines.append(f"Source: {r['source']}")
            lines.append("")
        return "\n".join(lines)

    def combined_search(query: str) -> str:
        """Run both searches, dedupe by URL, combine results."""
        all_results = []
        seen_urls = set()

        # Run SerpAPI first (more reliable)
        if serp_search:
            try:
                serp_text = serp_search(query)
                for r in _parse_results(serp_text):
                    url = r.get('url', '').lower().rstrip('/')
                    if url and url not in seen_urls:
                        seen_urls.add(url)
                        r['source'] = 'Google'
                        all_results.append(r)
            except SearchError:
                pass  # Continue with Brave

        # Run Brave (may hit rate limits)
        if brave_search:
            try:
                # Small delay to avoid rate limits
                time.sleep(0.5)
                brave_text = brave_search(query)
                for r in _parse_results(brave_text):
                    url = r.get('url', '').lower().rstrip('/')
                    if url and url not in seen_urls:
                        seen_urls.add(url)
                        r['source'] = 'Brave'
                        all_results.append(r)
            except SearchError:
                pass  # Continue with what we have

        if not all_results:
            return "No search results found."

        return _format_results(all_results)

    return combined_search


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


# Domains known to require JavaScript rendering for content
JS_HEAVY_DOMAINS = [
    'geni.com',
    'familysearch.org',
    'ancestry.com',
    'ancestry.co.uk',
    'myheritage.com',
    'findagrave.com',
    'billiongraves.com',
    'wikitree.com',
]

# Domains that need premium proxy (have aggressive bot protection)
# Premium proxy costs 10-25 credits instead of 1, but gets through Incapsula/Cloudflare
PREMIUM_PROXY_DOMAINS = [
    'geni.com',
    'familysearch.org',
    'findagrave.com',
    'ancestry.com',
    'ancestry.co.uk',
    'billiongraves.com',
]


def fetch_url_with_js(url: str, timeout: int = 30, max_chars: int = 15000) -> Optional[str]:
    """
    Fetch URL content using ScrapingBee for JavaScript rendering.

    ScrapingBee handles JavaScript-heavy sites that block normal fetching.
    Requires SCRAPINGBEE_API_KEY environment variable.

    Args:
        url: The URL to fetch
        timeout: Request timeout in seconds
        max_chars: Maximum characters to return

    Returns:
        Extracted text content or None if failed/no API key
    """
    import re
    from html.parser import HTMLParser

    api_key = os.environ.get("SCRAPINGBEE_API_KEY")
    if not api_key:
        return None

    class TextExtractor(HTMLParser):
        def __init__(self):
            super().__init__()
            self.text_parts = []
            self.skip_tags = {'script', 'style', 'nav', 'header', 'footer', 'aside'}
            self.current_skip = 0

        def handle_starttag(self, tag, attrs):
            if tag in self.skip_tags:
                self.current_skip += 1

        def handle_endtag(self, tag):
            if tag in self.skip_tags and self.current_skip > 0:
                self.current_skip -= 1

        def handle_data(self, data):
            if self.current_skip == 0:
                text = data.strip()
                if text:
                    self.text_parts.append(text)

    try:
        # ScrapingBee API endpoint
        # Use premium proxy for heavily protected sites (costs 10-25 credits vs 1)
        use_premium = needs_premium_proxy(url)
        params = {
            'api_key': api_key,
            'url': url,
            'render_js': 'true',
            'premium_proxy': 'true' if use_premium else 'false',
            'block_ads': 'true',
            'block_resources': 'false',  # Need resources for JS rendering
        }

        api_url = f"https://app.scrapingbee.com/api/v1?{urlencode(params)}"

        req = Request(api_url, headers={
            "Accept": "text/html,application/xhtml+xml,*/*"
        })

        with urlopen(req, timeout=timeout) as response:
            html = response.read().decode('utf-8', errors='ignore')

        # Extract text from HTML
        extractor = TextExtractor()
        extractor.feed(html)
        text = ' '.join(extractor.text_parts)

        # Clean up whitespace
        text = re.sub(r'\s+', ' ', text)

        return text[:max_chars] if text else None

    except Exception:
        return None


def is_js_heavy_domain(url: str) -> bool:
    """Check if URL is from a known JavaScript-heavy domain."""
    url_lower = url.lower()
    return any(domain in url_lower for domain in JS_HEAVY_DOMAINS)


def needs_premium_proxy(url: str) -> bool:
    """Check if URL needs premium proxy to bypass bot protection."""
    url_lower = url.lower()
    return any(domain in url_lower for domain in PREMIUM_PROXY_DOMAINS)


def fetch_url_content(url: str, timeout: int = 15, max_chars: int = 15000) -> Optional[str]:
    """
    Fetch and extract text content from a URL.

    Args:
        url: The URL to fetch
        timeout: Request timeout in seconds
        max_chars: Maximum characters to return

    Returns:
        Extracted text content or None if failed
    """
    import re
    from html.parser import HTMLParser

    class TextExtractor(HTMLParser):
        def __init__(self):
            super().__init__()
            self.text_parts = []
            self.skip_tags = {'script', 'style', 'nav', 'header', 'footer', 'aside'}
            self.current_skip = 0

        def handle_starttag(self, tag, attrs):
            if tag in self.skip_tags:
                self.current_skip += 1

        def handle_endtag(self, tag):
            if tag in self.skip_tags and self.current_skip > 0:
                self.current_skip -= 1

        def handle_data(self, data):
            if self.current_skip == 0:
                text = data.strip()
                if text:
                    self.text_parts.append(text)

    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; WhereTheyWalked/1.0; genealogy research)",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
        }
        req = Request(url, headers=headers)

        with urlopen(req, timeout=timeout) as response:
            content_type = response.headers.get('Content-Type', '')
            if 'text/html' not in content_type and 'text/plain' not in content_type:
                return None

            html = response.read().decode('utf-8', errors='ignore')

        # Extract text from HTML
        extractor = TextExtractor()
        extractor.feed(html)
        text = ' '.join(extractor.text_parts)

        # Clean up whitespace
        text = re.sub(r'\s+', ' ', text)

        return text[:max_chars] if text else None

    except Exception:
        return None


def create_deep_search(search_fn: Callable[[str], str],
                       fetch_top_n: int = 5,
                       max_content_per_url: int = 10000,
                       use_js_fallback: bool = True) -> Callable[[str], str]:
    """
    Create a deep search function that fetches full page content.

    Gets search results, then fetches full content from URLs until we have
    fetch_top_n successful pages (not just attempts). Uses ScrapingBee as
    fallback for JavaScript-heavy sites if SCRAPINGBEE_API_KEY is set.

    Args:
        search_fn: Base search function (SerpAPI or Brave)
        fetch_top_n: Target number of successful page fetches (guarantees this many if possible)
        max_content_per_url: Max chars to extract per URL
        use_js_fallback: Whether to use ScrapingBee for JS-heavy sites (default True)

    Returns:
        Function that returns search snippets + full page content
    """
    import re

    has_scrapingbee = bool(os.environ.get("SCRAPINGBEE_API_KEY"))

    def deep_search(query: str) -> str:
        # Get initial search results
        search_results = search_fn(query)

        # Extract URLs from search results
        url_pattern = r'URL: (https?://[^\s]+)'
        urls = re.findall(url_pattern, search_results)

        # Filter out social media (never useful for genealogy)
        skip_domains = ['facebook.com', 'twitter.com', 'instagram.com', 'linkedin.com',
                        'youtube.com', 'tiktok.com', 'pinterest.com']
        good_urls = [u for u in urls if not any(d in u for d in skip_domains)]

        # Fetch content until we have fetch_top_n successes (or exhaust URLs)
        full_content = []
        failed_urls = []
        js_rendered_urls = []  # Track URLs that needed JS rendering

        for url in good_urls:
            if len(full_content) >= fetch_top_n:
                break  # We have enough

            content = None

            # Try normal fetch first
            content = fetch_url_content(url, max_chars=max_content_per_url)

            # If failed and it's a JS-heavy domain, try ScrapingBee
            if (not content or len(content) <= 200) and use_js_fallback and has_scrapingbee:
                if is_js_heavy_domain(url):
                    content = fetch_url_with_js(url, max_chars=max_content_per_url)
                    if content and len(content) > 200:
                        js_rendered_urls.append(url)

            if content and len(content) > 200:  # Only include substantial content
                full_content.append(f"\n== Full Content from {url} ==\n{content}\n")
            else:
                failed_urls.append(url)

        # Combine search results with full content
        if full_content:
            result = search_results + "\n\n== DETAILED PAGE CONTENT ==\n" + "\n".join(full_content)

            # Note stats
            notes = []
            if js_rendered_urls:
                notes.append(f"{len(js_rendered_urls)} pages fetched via JS rendering")
            if failed_urls:
                notes.append(f"{len(failed_urls)} URLs could not be fetched")
                if not has_scrapingbee:
                    # Identify which failed URLs could benefit from JS rendering
                    js_blocked = [u for u in failed_urls if is_js_heavy_domain(u)]
                    if js_blocked:
                        notes.append(f"({len(js_blocked)} need JavaScript: {', '.join(js_blocked[:2])}...)")
            if notes:
                result += f"\n\n[Note: {'; '.join(notes)}]"

            return result

        return search_results

    return deep_search


def create_serpapi_search_with_urls(api_key: str = None,
                                     num_results: int = 10,
                                     timeout: int = 30) -> tuple[Callable[[str], str], Callable[[str], list]]:
    """
    Create SerpAPI search that also returns URLs for further fetching.

    Returns:
        Tuple of (search_fn, get_urls_fn)
    """
    api_key = api_key or os.environ.get("SERPAPI_KEY")
    if not api_key:
        raise ValueError("SerpAPI key required.")

    def search_with_urls(query: str) -> tuple[str, list]:
        """Returns (formatted_results, list_of_urls)"""
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
        except Exception as e:
            raise SearchError(f"SerpAPI error: {e}")

        results = []
        urls = []

        # Knowledge panel
        if "knowledge_graph" in data:
            kg = data["knowledge_graph"]
            results.append("== Knowledge Panel ==")
            for key in ['title', 'description', 'source']:
                if key in kg:
                    val = kg[key] if key != 'source' else kg[key].get('link', '')
                    results.append(f"{key.title()}: {val}")
            results.append("")

        # Organic results
        if "organic_results" in data:
            results.append("== Search Results ==\n")
            for i, item in enumerate(data["organic_results"], 1):
                results.append(f"[{i}] {item.get('title', 'No title')}")
                link = item.get('link', '')
                results.append(f"URL: {link}")
                if link:
                    urls.append(link)
                if "snippet" in item:
                    results.append(f"Snippet: {item['snippet']}")
                results.append("")

        return "\n".join(results), urls

    def search(query: str) -> str:
        text, _ = search_with_urls(query)
        return text

    def get_urls(query: str) -> list:
        _, urls = search_with_urls(query)
        return urls

    return search, get_urls
