#!/usr/bin/env python3
"""
Test script to compare keyword-based vs AI-driven location classification.

Runs both approaches on the same ancestors and shows the differences.
"""

import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.main import create_app, get_api_status
from src.locations import LocationProcessor


def run_comparison(gedcom_path: str, num_ancestors: int = 3):
    """
    Compare current keyword-based classification vs what AI returns.
    """
    print("=" * 70)
    print("LOCATION CLASSIFICATION COMPARISON TEST")
    print("=" * 70)
    print()

    # Check APIs
    api_status = get_api_status()
    if not api_status['synthesis']['anthropic']:
        print("ERROR: ANTHROPIC_API_KEY required")
        sys.exit(1)

    # Create app
    app = create_app(search_provider="auto", verbose=False)

    # Load GEDCOM
    print(f"Loading: {gedcom_path}")
    stats = app.load_gedcom(gedcom_path)
    print(f"Found {stats['total_individuals']} individuals")
    print()

    # Get sample ancestors - pick ones likely to have interesting locations
    researchable = app.get_researchable()

    # Prefer ancestors from 1600-1750 (colonial era, more documented)
    colonial = [
        ind for ind in researchable
        if ind.get('birth_year') and 1600 < ind['birth_year'] < 1750
    ]

    sample = (colonial or researchable)[:num_ancestors]

    print(f"Testing on {len(sample)} ancestors:")
    for ind in sample:
        print(f"  - {ind['full_name']} ({ind['birth_year'] or '?'}-{ind['death_year'] or '?'})")
    print()

    # Research ancestors
    print("Researching ancestors...")
    print("-" * 40)

    results = app.research_ancestors(
        individuals=sample,
        verbose=False
    )

    print(f"Researched {len(results)} ancestors")
    print()

    # Now compare: AI-provided locations vs keyword-inferred
    print("=" * 70)
    print("COMPARISON: AI-PROVIDED vs KEYWORD-INFERRED LOCATIONS")
    print("=" * 70)
    print()

    for result in results:
        print(f"\n{'='*60}")
        print(f"ANCESTOR: {result['full_name']}")
        print(f"{'='*60}")

        # 1. Show AI-provided locations from synthesis
        ai_locations = result.get('locations', [])
        print(f"\n[AI-PROVIDED LOCATIONS] (from synthesis)")
        if ai_locations:
            for loc in ai_locations:
                print(f"  - {loc.get('name', 'Unknown')}")
                print(f"    Type: {loc.get('type', 'not specified')}")
                print(f"    Description: {loc.get('description', 'none')[:80]}")
        else:
            print("  (none)")

        # 2. Show birth/death places and what keyword matching would assign
        print(f"\n[BIRTH/DEATH PLACES] (keyword-inferred types)")

        birth_place = result.get('birth_place') or result.get('birth_place_discovered')
        death_place = result.get('death_place') or result.get('death_place_discovered')

        processor = LocationProcessor()

        if birth_place:
            inferred_type = processor._infer_location_type(birth_place, "born")
            print(f"  Birth: {birth_place}")
            print(f"    → Keyword inferred type: {inferred_type}")

        if death_place:
            inferred_type = processor._infer_location_type(death_place, "died")
            print(f"  Death: {death_place}")
            print(f"    → Keyword inferred type: {inferred_type}")

        # 3. Show historic events (which might mention locations)
        print(f"\n[HISTORIC EVENTS] (potential location sources)")
        events = result.get('historic_events', [])
        if events:
            for evt in events:
                print(f"  - {evt.get('name', 'Unknown')} ({evt.get('year', '?')})")
                if evt.get('ancestor_role'):
                    print(f"    Role: {evt.get('ancestor_role')[:60]}")
        else:
            print("  (none)")

        # 4. Show notable relatives (might have associated locations)
        print(f"\n[NOTABLE RELATIVES] (potential location connections)")
        relatives = result.get('notable_relatives', [])
        if relatives:
            for rel in relatives:
                in_tree = " [IN TREE]" if rel.get('in_tree') else ""
                print(f"  - {rel.get('name', 'Unknown')} ({rel.get('relationship', '?')}){in_tree}")
                if rel.get('why_notable'):
                    print(f"    Notable: {rel.get('why_notable')[:60]}")
        else:
            print("  (none)")

        # 5. Source URLs (to check what pages we're getting)
        print(f"\n[SOURCE URLS] (pages fetched)")
        urls = result.get('source_urls', [])[:5]
        for url in urls:
            print(f"  - {url[:70]}...")

    # Summary analysis
    print("\n")
    print("=" * 70)
    print("ANALYSIS SUMMARY")
    print("=" * 70)

    total_ai_locations = sum(len(r.get('locations', [])) for r in results)
    total_with_type = sum(
        1 for r in results
        for loc in r.get('locations', [])
        if loc.get('type') and loc.get('type') != 'other'
    )

    # Categories found by AI
    ai_types = {}
    for r in results:
        for loc in r.get('locations', []):
            t = loc.get('type', 'unspecified')
            ai_types[t] = ai_types.get(t, 0) + 1

    print(f"\nAI-provided locations: {total_ai_locations}")
    print(f"With specific type: {total_with_type}")
    print(f"Types found by AI: {ai_types}")

    # What keyword matching would do
    keyword_types = {}
    for r in results:
        for place in [r.get('birth_place'), r.get('death_place')]:
            if place:
                t = processor._infer_location_type(place, "")
                keyword_types[t] = keyword_types.get(t, 0) + 1

    print(f"\nKeyword-inferred types (birth/death only): {keyword_types}")

    print("\n" + "=" * 70)
    print("RECOMMENDATION")
    print("=" * 70)

    # Check if AI is finding types that keywords miss
    ai_specific = set(ai_types.keys()) - {'other', 'unspecified', 'residence'}
    keyword_specific = set(keyword_types.keys()) - {'other', 'residence'}

    ai_only = ai_specific - keyword_specific
    if ai_only:
        print(f"\nAI found types that keywords would miss: {ai_only}")
        print("→ AI-driven classification would capture more.")
    else:
        print("\nBoth approaches found similar types.")
        print("→ Keyword matching may be sufficient for these ancestors.")

    print()
    return results


def main():
    if len(sys.argv) < 2:
        print("Usage: python test_location_classification.py <gedcom_file> [num_ancestors]")
        sys.exit(1)

    gedcom_path = sys.argv[1]
    num = int(sys.argv[2]) if len(sys.argv) > 2 else 3

    if not os.path.exists(gedcom_path):
        print(f"Error: File not found: {gedcom_path}")
        sys.exit(1)

    run_comparison(gedcom_path, num_ancestors=num)


if __name__ == "__main__":
    main()
