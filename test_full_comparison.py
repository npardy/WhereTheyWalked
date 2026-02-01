#!/usr/bin/env python3
"""
Comprehensive comparison of Brave vs SerpAPI across all search types:
1. Ancestor searches
2. Location searches (cemetery, church)
3. Event searches
Plus full synthesis comparison.
"""

import sys
import os
import json
import time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.researcher import AncestorResearcher, create_anthropic_synthesizer, get_token_tracker
from src.search import create_brave_search, create_serpapi_search

# Test queries for different search types
SEARCH_TESTS = {
    "ancestor": '"William Nickerson" Chatham Massachusetts 1600s founder genealogy',
    "cemetery": '"Nickerson Cemetery" Chatham Cape Cod history burials',
    "church": '"First Congregational Church" Chatham Massachusetts history founded',
    "event": '"King Philip\'s War" Cape Cod Massachusetts 1675 history',
}

# Test ancestor for full synthesis
TEST_ANCESTOR = {
    "id": "test_001",
    "full_name": "William Nickerson",
    "given_name": "William",
    "surname": "Nickerson",
    "birth_year": 1604,
    "death_year": 1689,
    "birth_place": "Norwich, England",
    "death_place": "Chatham, Massachusetts",
    "search_query": '"William Nickerson" Chatham Massachusetts 1600s founder genealogy'
}


def test_raw_searches(serp_search, brave_search):
    """Compare raw search results for each query type."""
    results = {}

    for search_type, query in SEARCH_TESTS.items():
        print(f"\n{'='*70}")
        print(f"SEARCH TYPE: {search_type.upper()}")
        print(f"Query: {query}")
        print(f"{'='*70}")

        # SerpAPI
        print(f"\n--- SerpAPI Results ---")
        try:
            serp_result = serp_search(query)
            print(serp_result[:2000])
            if len(serp_result) > 2000:
                print(f"... [{len(serp_result) - 2000} more chars]")
            serp_len = len(serp_result)
        except Exception as e:
            print(f"ERROR: {e}")
            serp_result = ""
            serp_len = 0

        time.sleep(2)  # Avoid rate limits

        # Brave
        print(f"\n--- Brave Results ---")
        try:
            brave_result = brave_search(query)
            print(brave_result[:2000])
            if len(brave_result) > 2000:
                print(f"... [{len(brave_result) - 2000} more chars]")
            brave_len = len(brave_result)
        except Exception as e:
            print(f"ERROR: {e}")
            brave_result = ""
            brave_len = 0

        results[search_type] = {
            "serp_len": serp_len,
            "brave_len": brave_len,
            "serp_result": serp_result,
            "brave_result": brave_result
        }

        time.sleep(2)

    return results


def test_full_synthesis(search_fn, search_name, synthesize_fn, ancestor):
    """Run full synthesis and return detailed results."""
    print(f"\n{'='*70}")
    print(f"FULL SYNTHESIS WITH: {search_name}")
    print(f"{'='*70}")

    researcher = AncestorResearcher(
        search_fn=search_fn,
        synthesize_fn=synthesize_fn
    )

    result = researcher.research_individual(ancestor, verbose=True)

    print(f"\n--- Biography ---")
    print(result.biography or "No biography generated")

    print(f"\n--- Short Bio ---")
    print(result.biography_short or "N/A")

    print(f"\n--- Locations ({len(result.locations)}) ---")
    for loc in result.locations:
        if isinstance(loc, dict):
            print(f"  • {loc.get('name', '?')}")
            print(f"    Type: {loc.get('type', '?')}")
            print(f"    Desc: {loc.get('description', '?')[:80]}")

    print(f"\n--- Historic Events ({len(result.historic_events)}) ---")
    for evt in result.historic_events:
        if isinstance(evt, dict):
            print(f"  • {evt.get('event', '?')}")
            print(f"    Year: {evt.get('year', '?')}")
            print(f"    Connection: {evt.get('ancestor_connection', '?')[:80] if evt.get('ancestor_connection') else '?'}")

    print(f"\n--- Flags ---")
    flags = getattr(result, 'flags', None)
    if flags:
        for k, v in flags.items():
            if v:
                print(f"  • {k}: {v}")
    else:
        print("  (no flags)")

    return result


def main():
    print("=" * 70)
    print("COMPREHENSIVE SEARCH PROVIDER COMPARISON")
    print("Brave vs SerpAPI - All Search Types + Full Synthesis")
    print("=" * 70)

    # Initialize search providers
    try:
        serp_search = create_serpapi_search()
        print("✓ SerpAPI initialized")
    except Exception as e:
        print(f"✗ SerpAPI failed: {e}")
        return

    try:
        brave_search = create_brave_search()
        print("✓ Brave initialized")
    except Exception as e:
        print(f"✗ Brave failed: {e}")
        return

    synthesize = create_anthropic_synthesizer()
    print("✓ Anthropic synthesizer initialized")

    tracker = get_token_tracker()

    # Part 1: Raw search comparison
    print("\n" + "#" * 70)
    print("# PART 1: RAW SEARCH RESULTS COMPARISON")
    print("#" * 70)

    search_results = test_raw_searches(serp_search, brave_search)

    # Summary table
    print(f"\n{'='*70}")
    print("RAW SEARCH SUMMARY")
    print(f"{'='*70}")
    print(f"{'Search Type':<20} {'SerpAPI (chars)':<20} {'Brave (chars)':<20}")
    print("-" * 60)
    for search_type, data in search_results.items():
        print(f"{search_type:<20} {data['serp_len']:<20} {data['brave_len']:<20}")

    # Part 2: Full synthesis comparison
    print("\n" + "#" * 70)
    print("# PART 2: FULL SYNTHESIS COMPARISON")
    print("#" * 70)

    tracker.reset()
    serp_synthesis = test_full_synthesis(serp_search, "SerpAPI", synthesize, TEST_ANCESTOR)
    serp_cost = tracker.get_cost()
    serp_tokens = tracker.total_input_tokens + tracker.total_output_tokens

    print("\nWaiting 5 seconds before Brave synthesis...")
    time.sleep(5)

    tracker.reset()
    brave_synthesis = test_full_synthesis(brave_search, "Brave", synthesize, TEST_ANCESTOR)
    brave_cost = tracker.get_cost()
    brave_tokens = tracker.total_input_tokens + tracker.total_output_tokens

    # Final comparison
    print("\n" + "=" * 70)
    print("FINAL COMPARISON")
    print("=" * 70)

    print(f"\n{'Metric':<35} {'SerpAPI':<20} {'Brave':<20}")
    print("-" * 75)
    print(f"{'Confidence':<35} {serp_synthesis.confidence:<20} {brave_synthesis.confidence:<20}")
    print(f"{'Notable':<35} {str(serp_synthesis.notable):<20} {str(brave_synthesis.notable):<20}")
    print(f"{'Biography length':<35} {len(serp_synthesis.biography or ''):<20} {len(brave_synthesis.biography or ''):<20}")
    print(f"{'Locations found':<35} {len(serp_synthesis.locations):<20} {len(brave_synthesis.locations):<20}")
    print(f"{'Events found':<35} {len(serp_synthesis.historic_events):<20} {len(brave_synthesis.historic_events):<20}")
    print(f"{'AI tokens used':<35} {serp_tokens:<20} {brave_tokens:<20}")
    print(f"{'AI cost (Haiku)':<35} ${serp_cost['total_cost']:<19.4f} ${brave_cost['total_cost']:<19.4f}")

    # Cost projection
    print(f"\n{'='*70}")
    print("COST PROJECTION FOR 500 ANCESTORS")
    print(f"{'='*70}")

    serp_search_cost = 500 * 0.01  # $0.01 per search
    brave_search_cost = 500 * 0.00025  # $0.00025 per search
    ai_cost_per = (serp_cost['total_cost'] + brave_cost['total_cost']) / 2

    print(f"\nSerpAPI path:")
    print(f"  Search: 500 × $0.01 = ${serp_search_cost:.2f}")
    print(f"  AI: 500 × ${ai_cost_per:.4f} = ${500 * ai_cost_per:.2f}")
    print(f"  TOTAL: ${serp_search_cost + 500 * ai_cost_per:.2f}")

    print(f"\nBrave path:")
    print(f"  Search: 500 × $0.00025 = ${brave_search_cost:.2f}")
    print(f"  AI: 500 × ${ai_cost_per:.4f} = ${500 * ai_cost_per:.2f}")
    print(f"  TOTAL: ${brave_search_cost + 500 * ai_cost_per:.2f}")

    # Save full results
    output = {
        "search_results": {k: {"serp_len": v["serp_len"], "brave_len": v["brave_len"]}
                          for k, v in search_results.items()},
        "serp_synthesis": serp_synthesis.to_dict(),
        "brave_synthesis": brave_synthesis.to_dict(),
        "costs": {
            "serp_ai": serp_cost,
            "brave_ai": brave_cost
        }
    }

    with open("full_comparison_results.json", "w") as f:
        json.dump(output, f, indent=2, default=str)

    print(f"\nFull results saved to: full_comparison_results.json")


if __name__ == "__main__":
    main()
