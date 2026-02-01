#!/usr/bin/env python3
"""
Compare search quality between Brave and SerpAPI for genealogy queries.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.search import create_brave_search, create_serpapi_search

# Test queries - typical genealogy searches
TEST_QUERIES = [
    '"William Nickerson" Chatham Massachusetts 1700s',
    '"John Bowne" Flushing New York Quaker 1600s',
    '"Nickerson Cemetery" Chatham Cape Cod history',
    '"First Congregational Church" Chatham Massachusetts founded',
    '"Bowne House" Flushing Queens historic',
]

def test_search_provider(name, search_fn, queries):
    """Test a search provider and return results summary."""
    print(f"\n{'='*60}")
    print(f"TESTING: {name}")
    print(f"{'='*60}")

    results = []
    for query in queries:
        print(f"\nQuery: {query[:50]}...")
        try:
            result = search_fn(query)
            # Count rough metrics
            result_len = len(result)
            url_count = result.count("http")
            has_content = result_len > 200 and "No results" not in result

            print(f"  Length: {result_len:,} chars")
            print(f"  URLs found: {url_count}")
            print(f"  Has content: {has_content}")

            # Show snippet
            if has_content:
                # Find first meaningful line
                lines = [l.strip() for l in result.split('\n') if l.strip() and len(l.strip()) > 50]
                if lines:
                    print(f"  Snippet: {lines[0][:100]}...")

            results.append({
                "query": query,
                "length": result_len,
                "urls": url_count,
                "has_content": has_content,
                "raw": result
            })
        except Exception as e:
            print(f"  ERROR: {e}")
            results.append({
                "query": query,
                "length": 0,
                "urls": 0,
                "has_content": False,
                "error": str(e)
            })

    return results


def compare_results(brave_results, serp_results):
    """Compare results between providers."""
    print(f"\n{'='*60}")
    print("COMPARISON SUMMARY")
    print(f"{'='*60}")

    print(f"\n{'Query':<45} {'Brave':>10} {'SerpAPI':>10} {'Winner':>10}")
    print("-" * 75)

    brave_wins = 0
    serp_wins = 0
    ties = 0

    for b, s in zip(brave_results, serp_results):
        query_short = b["query"][:42] + "..." if len(b["query"]) > 45 else b["query"]

        b_score = b["length"] + (b["urls"] * 100) if b["has_content"] else 0
        s_score = s["length"] + (s["urls"] * 100) if s["has_content"] else 0

        if b_score > s_score * 1.1:
            winner = "Brave"
            brave_wins += 1
        elif s_score > b_score * 1.1:
            winner = "SerpAPI"
            serp_wins += 1
        else:
            winner = "Tie"
            ties += 1

        print(f"{query_short:<45} {b['length']:>10,} {s['length']:>10,} {winner:>10}")

    print("-" * 75)
    print(f"\nBrave wins: {brave_wins}, SerpAPI wins: {serp_wins}, Ties: {ties}")

    # Quality comparison on specific content
    print(f"\n{'='*60}")
    print("DETAILED CONTENT COMPARISON")
    print(f"{'='*60}")

    for i, (b, s) in enumerate(zip(brave_results, serp_results)):
        print(f"\n--- Query {i+1}: {b['query'][:60]} ---")

        # Check for key terms that indicate quality genealogy results
        key_terms = ["born", "died", "married", "cemetery", "church", "historic",
                     "founded", "built", "Quaker", "ancestor", "genealogy"]

        b_terms = sum(1 for t in key_terms if t.lower() in b.get("raw", "").lower())
        s_terms = sum(1 for t in key_terms if t.lower() in s.get("raw", "").lower())

        print(f"  Brave - genealogy terms found: {b_terms}")
        print(f"  SerpAPI - genealogy terms found: {s_terms}")


def main():
    print("Search Provider Comparison Test")
    print("Testing Brave vs SerpAPI for genealogy queries\n")

    # Create search functions
    try:
        brave_search = create_brave_search()
        print("✓ Brave API initialized")
    except Exception as e:
        print(f"✗ Brave API failed: {e}")
        brave_search = None

    try:
        serp_search = create_serpapi_search()
        print("✓ SerpAPI initialized")
    except Exception as e:
        print(f"✗ SerpAPI failed: {e}")
        serp_search = None

    if not brave_search or not serp_search:
        print("\nBoth APIs required for comparison. Exiting.")
        sys.exit(1)

    # Run tests
    brave_results = test_search_provider("Brave Search", brave_search, TEST_QUERIES)
    serp_results = test_search_provider("SerpAPI (Google)", serp_search, TEST_QUERIES)

    # Compare
    compare_results(brave_results, serp_results)

    print(f"\n{'='*60}")
    print("COST COMPARISON")
    print(f"{'='*60}")
    print(f"Queries run: {len(TEST_QUERIES)}")
    print(f"Brave cost:  ${len(TEST_QUERIES) * 0.00025:.4f}")
    print(f"SerpAPI cost: ${len(TEST_QUERIES) * 0.01:.4f}")
    print(f"SerpAPI is {0.01/0.00025:.0f}x more expensive")


if __name__ == "__main__":
    main()
