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
    needs_premium_proxy,
    JS_HEAVY_DOMAINS,
    PREMIUM_PROXY_DOMAINS
)

# Test URLs - using public pages that don't require login
TEST_URLS = [
    # FindAGrave - public memorial (should work)
    ("https://www.findagrave.com/memorial/7893421", "FindAGrave"),
    # WikiTree - public profile (less protected)
    ("https://www.wikitree.com/wiki/Nickerson-1", "WikiTree"),
    # BillionGraves - public page
    ("https://billiongraves.com/grave/William-Nickerson/5849332", "BillionGraves"),
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
        return

    # Show known domains
    print(f"\nJS-heavy domains: {', '.join(JS_HEAVY_DOMAINS)}")
    print(f"Premium proxy domains: {', '.join(PREMIUM_PROXY_DOMAINS)}")

    # Test fetching
    print("\n--- Fetch Comparison ---")
    for url, name in TEST_URLS:
        print(f"\n{name}: {url[:60]}...")
        print(f"  Needs premium proxy: {needs_premium_proxy(url)}")

        # Try normal fetch
        print("  Normal fetch: ", end="", flush=True)
        content = fetch_url_content(url, max_chars=5000)
        if content and len(content) > 100:
            print(f"{len(content)} chars")
            # Check if it's an error page
            if "incapsula" in content.lower() or "cloudflare" in content.lower():
                print(f"    (blocked by bot protection)")
            else:
                print(f"    Preview: {content[:150].strip()}...")
        else:
            print("FAILED or minimal content")

        # Try JS fetch
        print("  ScrapingBee fetch: ", end="", flush=True)
        content = fetch_url_with_js(url, max_chars=5000)
        if content and len(content) > 100:
            print(f"{len(content)} chars")
            if "incapsula" in content.lower() or "cloudflare" in content.lower():
                print(f"    (still blocked)")
            else:
                print(f"    Preview: {content[:150].strip()}...")
        else:
            print("FAILED")

    print("\n" + "=" * 70)
    print("COST NOTES")
    print("=" * 70)
    print("- Regular JS render: 5 credits")
    print("- Premium proxy render: 10-25 credits")
    print("- Free tier: 1000 credits/month")
    print("- At ~15 credits/protected URL, you get ~66 protected fetches/month")


if __name__ == "__main__":
    main()
