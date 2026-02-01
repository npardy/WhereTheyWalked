#!/usr/bin/env python3
"""
Full system test - shows complete results with all features enabled.
Uses combined search, deep search, ScrapingBee fallback, and full synthesis.
"""

import sys
import os
import json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src import (
    create_app, get_api_status,
    TokenTracker, get_token_tracker
)


def print_section(title):
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}\n")


def main():
    print_section("WHERE THEY WALKED - FULL SYSTEM TEST")

    # Show API status
    status = get_api_status()
    print("API Configuration:")
    for key, val in status.items():
        print(f"  {key}: {val}")

    # Create app with combined search
    print("\nInitializing with combined search (SerpAPI + Brave)...")
    app = create_app(search_provider="combined", deep_search=True, verbose=True)

    # Test ancestor - William Nickerson, founder of Chatham
    # Include the search query as GEDCOM parser would build it
    ancestor = {
        "id": "test_001",
        "full_name": "William Nickerson",
        "given_name": "William",
        "surname": "Nickerson",
        "birth_year": 1604,
        "death_year": 1689,
        "birth_place": "Norwich, England",
        "death_place": "Chatham, Massachusetts",
        "search_query": '"William Nickerson" 1604 1689 Norwich England Chatham Massachusetts genealogy history',
    }

    print_section(f"RESEARCHING: {ancestor['full_name']} ({ancestor['birth_year']}-{ancestor['death_year']})")
    print(f"Birth: {ancestor['birth_place']}")
    print(f"Death: {ancestor['death_place']}")

    # Reset token tracker
    tracker = get_token_tracker()
    tracker.reset()

    # Run research
    print("\nSearching and synthesizing...")
    result = app.researcher.research_individual(ancestor, verbose=True)

    # Show results
    print_section("RESEARCH RESULTS")

    print(f"Confidence: {result.confidence}")
    print(f"Notable: {result.notable}")
    if result.notable_reason:
        print(f"  Reason: {result.notable_reason}")

    print(f"\n--- Biography ({len(result.biography or '')} chars) ---")
    if result.biography:
        # Show full biography
        print(result.biography)

    print(f"\n--- Short Bio ---")
    print(result.biography_short or "N/A")

    print(f"\n--- Discovered Dates ---")
    print(f"Birth year: {result.birth_year_discovered or 'Not found'}")
    print(f"Death year: {result.death_year_discovered or 'Not found'}")

    print(f"\n--- Locations ({len(result.locations)}) ---")
    for loc in result.locations:
        if isinstance(loc, dict):
            print(f"\n  {loc.get('name', '?')}")
            print(f"    Type: {loc.get('type', '?')}")
            print(f"    Description: {loc.get('description', '?')}")
            if loc.get('coordinates'):
                print(f"    Coordinates: {loc['coordinates']}")

    print(f"\n--- Historic Events ({len(result.historic_events)}) ---")
    for evt in result.historic_events:
        if isinstance(evt, dict):
            print(f"\n  {evt.get('event', '?')}")
            print(f"    Year: {evt.get('year', '?')}")
            print(f"    Connection: {evt.get('ancestor_connection', '?')}")

    # Show flags
    print(f"\n--- Special Flags ---")
    flags = getattr(result, 'flags', None) or {}
    found_flags = {k: v for k, v in flags.items() if v}
    if found_flags:
        for k, v in found_flags.items():
            print(f"  {k}: {v}")
    else:
        print("  None")

    # Show token usage and costs
    print_section("COST ANALYSIS")

    cost = tracker.get_cost()
    print(f"Tokens used:")
    print(f"  Input:  {tracker.total_input_tokens:,}")
    print(f"  Output: {tracker.total_output_tokens:,}")
    print(f"  Total:  {tracker.total_input_tokens + tracker.total_output_tokens:,}")

    print(f"\nCost for this ancestor (Haiku):")
    print(f"  AI synthesis: ${cost['total_cost']:.4f}")
    print(f"  Search API:   ~$0.01 (SerpAPI) + $0.00025 (Brave)")
    print(f"  Total:        ~${cost['total_cost'] + 0.01:.4f}")

    print(f"\nProjected cost for 500 ancestors:")
    ai_cost_per = cost['total_cost']
    search_cost_per = 0.01 + 0.00025  # Combined search
    total_per = ai_cost_per + search_cost_per
    print(f"  AI synthesis: ${ai_cost_per * 500:.2f}")
    print(f"  Search APIs:  ${search_cost_per * 500:.2f}")
    print(f"  TOTAL:        ${total_per * 500:.2f}")

    # Save full results
    output = {
        "ancestor": ancestor,
        "result": result.to_dict(),
        "cost": cost,
        "tokens": {
            "input": tracker.total_input_tokens,
            "output": tracker.total_output_tokens
        }
    }

    with open("full_system_test_results.json", "w") as f:
        json.dump(output, f, indent=2, default=str)

    print(f"\nFull results saved to: full_system_test_results.json")
    print_section("TEST COMPLETE")


if __name__ == "__main__":
    main()
