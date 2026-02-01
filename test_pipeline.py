#!/usr/bin/env python3
"""
Test script for Where They Walked pipeline.
Runs real searches and Haiku synthesis on sample ancestors.

Usage:
    python test_pipeline.py <gedcom_file> [num_ancestors] [--mock]

Environment variables:
    ANTHROPIC_API_KEY  - Required for AI synthesis (Claude Haiku)
    SERPAPI_KEY        - For Google search via SerpAPI
    BRAVE_API_KEY      - For Brave Search API

Examples:
    # Full test with real APIs
    python test_pipeline.py family.ged 5

    # Mock mode (no API calls)
    python test_pipeline.py family.ged 5 --mock
"""

import json
import sys
import os

# Add project root to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.main import create_app, get_api_status, WhereTheyWalked
from src.search import create_auto_search, create_mock_search, get_available_providers
from src.researcher import create_anthropic_synthesizer
from src.gedcom_parser import GedcomParser


def run_test(gedcom_path: str, num_ancestors: int = 5, use_mock: bool = False):
    """
    Test the full pipeline on a sample of ancestors.

    Args:
        gedcom_path: Path to GEDCOM file
        num_ancestors: How many to process
        use_mock: If True, use mock APIs (no real calls)
    """
    print("=" * 60)
    print("WHERE THEY WALKED - Pipeline Test")
    print("=" * 60)
    print()

    # Check API status
    api_status = get_api_status()
    print("API Configuration:")
    print(f"  Search providers: {api_status['search']['available_providers'] or 'None configured'}")
    print(f"  Synthesis (Anthropic): {'Configured' if api_status['synthesis']['anthropic'] else 'Not configured'}")
    print(f"  Geocoding (Nominatim): Always available")
    print()

    if use_mock:
        print("Running in MOCK MODE - no real API calls")
        print()

    # Create app with appropriate configuration
    if use_mock:
        app = create_app(use_mock=True, verbose=True)
    else:
        # Check if we have the required APIs
        if not api_status['synthesis']['anthropic']:
            print("WARNING: ANTHROPIC_API_KEY not set. Synthesis will be limited.")
            print("Set ANTHROPIC_API_KEY environment variable for full functionality.")
            print()

        if not api_status['search']['available_providers']:
            print("WARNING: No search API configured.")
            print("Set SERPAPI_KEY or BRAVE_API_KEY for real search results.")
            print()

        app = create_app(search_provider="auto", verbose=True)

    print()

    # Load GEDCOM
    print(f"Loading GEDCOM: {gedcom_path}")
    stats = app.load_gedcom(gedcom_path)
    print(f"Found {stats['total_individuals']} individuals, {stats['total_families']} families")
    print(f"Unique surnames: {stats['unique_surnames']}")
    print(f"By century: {stats['by_century']}")
    print()

    # Get researchable individuals
    researchable = app.get_researchable()
    print(f"Researchable individuals: {len(researchable)}")

    # Pick older ancestors with dates - more likely to be documented
    sample_with_dates = [
        ind for ind in researchable
        if ind.get('birth_year') and ind['birth_year'] < 1850
    ]

    if sample_with_dates:
        sample = sample_with_dates[:num_ancestors]
    else:
        sample = researchable[:num_ancestors]

    print(f"Testing on {len(sample)} ancestors:")
    for ind in sample:
        print(f"  - {ind['full_name']} ({ind['birth_year'] or '?'}-{ind['death_year'] or '?'})")
    print()

    # Research ancestors
    print("Researching ancestors...")
    print("-" * 40)

    def progress_callback(current, total, result):
        status = "Notable" if result.notable else f"{result.confidence} confidence"
        confirmation = " [Needs confirmation]" if result.needs_confirmation else ""
        print(f"[{current}/{total}] {result.full_name}: {status}{confirmation}")

    results = app.research_ancestors(
        individuals=sample,
        progress_callback=progress_callback,
        verbose=False
    )

    print()

    # Process locations
    print("Processing locations...")
    print("-" * 40)
    loc_stats = app.process_locations(verbose=True)
    print()

    # Summary
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)

    stats = app.get_stats()
    ancestors = stats['ancestors']

    print(f"\nAncestors Researched: {ancestors['total_researched']}")
    print(f"  High confidence:    {ancestors['high_confidence']}")
    print(f"  Medium confidence:  {ancestors['medium_confidence']}")
    print(f"  Low confidence:     {ancestors['low_confidence']}")
    print(f"  Notable:            {ancestors['notable_count']}")
    print(f"  Military service:   {ancestors['military_service']}")
    print(f"  Mayflower:          {ancestors['mayflower_connections']}")

    if loc_stats:
        print(f"\nLocations:")
        print(f"  Total found:        {loc_stats.get('total_locations', 0)}")
        print(f"  With coordinates:   {loc_stats.get('with_coordinates', 0)}")
        print(f"  Shared locations:   {loc_stats.get('shared_locations', 0)}")
        if loc_stats.get('by_type'):
            print(f"  By type:            {loc_stats['by_type']}")

    # Show notable ancestors
    notable = app.get_notable_ancestors()
    if notable:
        print(f"\nNotable Ancestors:")
        for n in notable[:5]:
            print(f"  - {n['full_name']}: {n.get('notable_reason', 'Notable')}")

    # Show shared locations
    shared = app.get_shared_locations(min_ancestors=2)
    if shared:
        print(f"\nShared Locations (multiple ancestors):")
        for loc in shared[:5]:
            names = [c['person_name'] for c in loc['ancestor_connections']]
            print(f"  - {loc['name']}: {', '.join(names)}")

    # Export results
    output_json = "test_results.json"
    output_geojson = "test_locations.geojson"

    app.export_json(output_json)
    print(f"\nFull results saved to: {output_json}")

    # Only export GeoJSON if we have locations with coordinates
    if loc_stats.get('with_coordinates', 0) > 0:
        app.export_geojson(output_geojson)
        print(f"GeoJSON (for maps) saved to: {output_geojson}")

    print()
    return results


def main():
    """CLI entry point."""
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    gedcom_path = sys.argv[1]
    num = int(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[2].isdigit() else 5
    use_mock = "--mock" in sys.argv

    if not os.path.exists(gedcom_path):
        print(f"Error: File not found: {gedcom_path}")
        sys.exit(1)

    run_test(gedcom_path, num_ancestors=num, use_mock=use_mock)


if __name__ == "__main__":
    main()
