#!/usr/bin/env python3
"""
Test ScrapingBee integration for JavaScript-heavy sites.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.search import (
    fetch_url_content,
    fetch_url_with_js,
    is_js_heavy_domain,
    JS_HEAVY_DOMAINS
)

# Test URLs - known JS-heavy genealogy sites
TEST_URLS = [
    "https://www.geni.com/people/William-Nickerson/6000000001960055617",
    "https://www.familysearch.org/tree/person/details/LZBV-ZN1",
    "https://www.findagrave.com/memorial/7893421",
]


def main():
    print("=" * 70)
    print("SCRAPINGBEE INTEGRATION TEST")
    print("=" * 70)

    # Check API key
    api_key = os.environ.get("SCRAPINGBEE_API_KEY")
    if api_key:
        print(f"ScrapingBee API key: {api_key[:8]}...{api_key[-4:]}")
    else:
        print("No SCRAPINGBEE_API_KEY set - JS rendering will be skipped")

    # Show known JS-heavy domains
    print(f"\nJS-heavy domains we handle: {', '.join(JS_HEAVY_DOMAINS)}")

    # Test domain detection
    print("\n--- Domain Detection ---")
    for url in TEST_URLS:
        is_js = is_js_heavy_domain(url)
        print(f"  {url[:50]}... -> JS-heavy: {is_js}")

    # Test fetching
    print("\n--- Fetch Comparison ---")
    for url in TEST_URLS[:2]:  # Only test first 2 to conserve API credits
        print(f"\nURL: {url[:60]}...")

        # Try normal fetch
        print("  Normal fetch: ", end="")
        content = fetch_url_content(url, max_chars=5000)
        if content:
            print(f"{len(content)} chars")
            # Show first 200 chars
            print(f"    Preview: {content[:200]}...")
        else:
            print("FAILED (likely needs JavaScript)")

        # Try JS fetch (if API key available)
        if api_key:
            print("  ScrapingBee fetch: ", end="")
            content = fetch_url_with_js(url, max_chars=5000)
            if content:
                print(f"{len(content)} chars")
                # Show first 200 chars
                print(f"    Preview: {content[:200]}...")
            else:
                print("FAILED")
        else:
            print("  ScrapingBee fetch: SKIPPED (no API key)")

    print("\n" + "=" * 70)
    print("INTEGRATION SUMMARY")
    print("=" * 70)
    if api_key:
        print("ScrapingBee is configured and ready for JS-heavy sites")
        print("Deep search will automatically use it for: " + ", ".join(JS_HEAVY_DOMAINS))
    else:
        print("To enable JS rendering, set SCRAPINGBEE_API_KEY environment variable")
        print("Get a free API key at: https://www.scrapingbee.com/")
        print("Free tier: 1000 credits/month")


if __name__ == "__main__":
    main()
