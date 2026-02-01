#!/usr/bin/env python3
"""
Show full search results side-by-side for quality comparison.
"""

import sys
import os
import time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.search import create_brave_search, create_serpapi_search

# Single test query - a typical genealogy search
QUERY = '"William Nickerson" Chatham Massachusetts 1700s genealogy'

def main():
    print("=" * 80)
    print("SEARCH QUALITY COMPARISON")
    print("=" * 80)
    print(f"\nQuery: {QUERY}\n")

    # SerpAPI first (more reliable)
    print("=" * 80)
    print("SERPAPI (Google) RESULTS:")
    print("=" * 80)
    try:
        serp = create_serpapi_search()
        serp_result = serp(QUERY)
        print(serp_result)
    except Exception as e:
        print(f"Error: {e}")
        serp_result = ""

    print("\n" + "=" * 80)
    print("BRAVE SEARCH RESULTS:")
    print("=" * 80)

    # Wait a bit to avoid rate limiting
    time.sleep(2)

    try:
        brave = create_brave_search()
        brave_result = brave(QUERY)
        print(brave_result)
    except Exception as e:
        print(f"Error: {e}")
        brave_result = ""

    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"SerpAPI length: {len(serp_result):,} chars")
    print(f"Brave length:   {len(brave_result):,} chars")


if __name__ == "__main__":
    main()
