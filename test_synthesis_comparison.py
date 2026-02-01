#!/usr/bin/env python3
"""
Compare full synthesis quality between Brave and SerpAPI.
Runs the same ancestor through both pipelines and compares results.
"""

import sys
import os
import json
import time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.researcher import AncestorResearcher, create_anthropic_synthesizer, get_token_tracker
from src.search import create_brave_search, create_serpapi_search

# Test ancestor - William Nickerson from Chatham
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


def run_research(search_name, search_fn, synthesize_fn, ancestor):
    """Run research pipeline and return results."""
    print(f"\n{'='*60}")
    print(f"RESEARCHING WITH: {search_name}")
    print(f"{'='*60}")

    researcher = AncestorResearcher(
        search_fn=search_fn,
        synthesize_fn=synthesize_fn
    )

    result = researcher.research_individual(ancestor, verbose=True)
    return result


def print_result_summary(name, result):
    """Print a summary of research results."""
    print(f"\n{'='*60}")
    print(f"RESULTS: {name}")
    print(f"{'='*60}")

    print(f"\nConfidence: {result.confidence}")
    print(f"Notable: {result.notable} - {result.notable_reason or 'N/A'}")

    print(f"\n--- Dates ---")
    print(f"Birth discovered: {result.birth_year_discovered}")
    print(f"Death discovered: {result.death_year_discovered}")

    print(f"\n--- Biography ({len(result.biography or '')} chars) ---")
    if result.biography:
        # Show first 500 chars
        print(result.biography[:500])
        if len(result.biography) > 500:
            print("...")

    print(f"\n--- Short Bio ---")
    print(result.biography_short or "N/A")

    print(f"\n--- Locations Found ({len(result.locations)}) ---")
    for loc in result.locations[:5]:
        if isinstance(loc, dict):
            print(f"  - {loc.get('name', 'Unknown')}: {loc.get('description', '')[:60]}")

    print(f"\n--- Historic Events ({len(result.historic_events)}) ---")
    for event in result.historic_events[:5]:
        if isinstance(event, dict):
            print(f"  - {event.get('event', 'Unknown')[:60]}")

    print(f"\n--- Flags ---")
    if result.flags:
        for key, val in result.flags.items():
            if val:
                print(f"  - {key}: {val}")


def main():
    print("=" * 60)
    print("SYNTHESIS QUALITY COMPARISON")
    print("Comparing Brave vs SerpAPI for full ancestor research")
    print("=" * 60)

    # Initialize
    synthesize = create_anthropic_synthesizer()
    tracker = get_token_tracker()
    tracker.reset()  # Start fresh

    # Test with SerpAPI first
    try:
        serp_search = create_serpapi_search()
        print("\n✓ SerpAPI initialized")

        serp_result = run_research("SerpAPI (Google)", serp_search, synthesize, TEST_ANCESTOR)
        serp_tokens = tracker.total_input_tokens + tracker.total_output_tokens

    except Exception as e:
        print(f"\n✗ SerpAPI failed: {e}")
        serp_result = None
        serp_tokens = 0

    # Reset tracker for Brave
    serp_cost = tracker.get_cost()
    tracker.reset()

    # Wait to avoid rate limits
    print("\nWaiting 3 seconds before Brave test...")
    time.sleep(3)

    # Test with Brave
    try:
        brave_search = create_brave_search()
        print("\n✓ Brave initialized")

        brave_result = run_research("Brave Search", brave_search, synthesize, TEST_ANCESTOR)
        brave_tokens = tracker.total_input_tokens + tracker.total_output_tokens

    except Exception as e:
        print(f"\n✗ Brave failed: {e}")
        brave_result = None
        brave_tokens = 0

    brave_cost = tracker.get_cost()

    # Print summaries
    if serp_result:
        print_result_summary("SerpAPI", serp_result)

    if brave_result:
        print_result_summary("Brave", brave_result)

    # Comparison
    print(f"\n{'='*60}")
    print("SIDE-BY-SIDE COMPARISON")
    print(f"{'='*60}")

    if serp_result and brave_result:
        print(f"\n{'Metric':<30} {'SerpAPI':<25} {'Brave':<25}")
        print("-" * 80)
        print(f"{'Confidence':<30} {serp_result.confidence:<25} {brave_result.confidence:<25}")
        print(f"{'Notable':<30} {str(serp_result.notable):<25} {str(brave_result.notable):<25}")
        print(f"{'Biography length':<30} {len(serp_result.biography or ''):<25} {len(brave_result.biography or ''):<25}")
        print(f"{'Locations found':<30} {len(serp_result.locations):<25} {len(brave_result.locations):<25}")
        print(f"{'Events found':<30} {len(serp_result.historic_events):<25} {len(brave_result.historic_events):<25}")
        print(f"{'AI tokens used':<30} {serp_tokens:<25} {brave_tokens:<25}")

        # Quality indicators
        serp_flags = sum(1 for v in (serp_result.flags or {}).values() if v)
        brave_flags = sum(1 for v in (brave_result.flags or {}).values() if v)
        print(f"{'Flags triggered':<30} {serp_flags:<25} {brave_flags:<25}")

    print(f"\n{'='*60}")
    print("COST COMPARISON (for this single ancestor)")
    print(f"{'='*60}")
    print(f"SerpAPI search cost: ~$0.01")
    print(f"Brave search cost:   ~$0.00025")
    print(f"AI cost (Haiku):     ~${(serp_cost['total_cost'] + brave_cost['total_cost'])/2:.4f} per ancestor")

    # Save full results for inspection
    output = {
        "ancestor": TEST_ANCESTOR,
        "serpapi_result": serp_result.to_dict() if serp_result else None,
        "brave_result": brave_result.to_dict() if brave_result else None
    }

    with open("synthesis_comparison_results.json", "w") as f:
        json.dump(output, f, indent=2, default=str)

    print(f"\nFull results saved to: synthesis_comparison_results.json")


if __name__ == "__main__":
    main()
