#!/usr/bin/env python3
"""
Test script for AI-based place normalization.
Verifies that different formats of the same place get deduplicated.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.locations import LocationProcessor


def test_normalize_place_caching():
    """Test that place normalization uses caching."""
    print("=" * 60)
    print("TEST: Place Normalization Caching")
    print("=" * 60)
    print()

    # Create processor without AI (to test caching fallback)
    processor = LocationProcessor()

    # Normalize same place multiple times
    place = "Chatham, MA"
    result1 = processor.normalize_place(place)
    result2 = processor.normalize_place(place)

    print(f"Input: '{place}'")
    print(f"First normalize: '{result1}'")
    print(f"Second normalize: '{result2}'")
    print(f"Cache hit (same result): {result1 == result2}")

    # Verify it was cached
    if place in processor._normalized_place_cache:
        print(f"✓ PASS: Place was cached")
        return True
    else:
        print(f"✗ FAIL: Place was not cached")
        return False


def test_normalize_place_with_mock_ai():
    """Test that place normalization uses AI when available."""
    print()
    print("=" * 60)
    print("TEST: Place Normalization with Mock AI")
    print("=" * 60)
    print()

    # Mock AI that normalizes places
    def mock_synthesize(prompt):
        # The prompt format is: Normalize this place name to a consistent format: "PLACE"
        # Extract the actual place being normalized (between quotes after the colon)
        import re
        match = re.search(r'Normalize this place name to a consistent format: "([^"]+)"', prompt)
        if match:
            place = match.group(1)
            if place == "Chatham, Barnstable, MA":
                return "Chatham, Massachusetts, USA"
            elif place == "Chatham, Mass":
                return "Chatham, Massachusetts, USA"
            elif place == "London, England":
                return "London, England, United Kingdom"
            elif place == "Sydney, NSW":
                return "Sydney, New South Wales, Australia"
        # Fallback
        return "Unknown, Unknown, Unknown"

    processor = LocationProcessor(synthesize_fn=mock_synthesize)

    # Test various formats
    test_cases = [
        ("Chatham, Barnstable, MA", "Chatham, Massachusetts, USA"),
        ("Chatham, Mass", "Chatham, Massachusetts, USA"),
        ("London, England", "London, England, United Kingdom"),
    ]

    all_pass = True
    for input_place, expected in test_cases:
        result = processor.normalize_place(input_place)
        if result == expected:
            print(f"✓ PASS: '{input_place}' -> '{result}'")
        else:
            print(f"✗ FAIL: '{input_place}' -> '{result}' (expected '{expected}')")
            all_pass = False

    return all_pass


def test_location_deduplication():
    """Test that normalized places result in same location ID."""
    print()
    print("=" * 60)
    print("TEST: Location Deduplication with Normalization")
    print("=" * 60)
    print()

    # Mock AI that normalizes places consistently
    def mock_synthesize(prompt):
        if "Chatham" in prompt:
            return "Chatham, Massachusetts, USA"
        return "Unknown, Unknown, Unknown"

    processor = LocationProcessor(synthesize_fn=mock_synthesize)

    # Add locations with different original formats
    processor._add_location_from_place(
        "Chatham, Barnstable, MA",
        "person1", "John Smith",
        "born_at", 1701, "Born here"
    )

    # This should NOT create a new location - same place, different format
    processor._add_location_from_place(
        "Chatham, Massachusetts, USA",
        "person2", "Jane Smith",
        "died_at", 1763, "Died here"
    )

    num_locations = len(processor.locations)
    print(f"Locations created after adding two Chathams: {num_locations}")

    if num_locations == 1:
        # Check that both connections are on the same location
        location = list(processor.locations.values())[0]
        connections = len(location.ancestor_connections)
        print(f"Connections on single location: {connections}")

        if connections == 2:
            print("✓ PASS: Both formats created same location with 2 connections")
            return True
        else:
            print(f"✗ FAIL: Expected 2 connections, got {connections}")
            return False
    else:
        print(f"✗ FAIL: Expected 1 location, got {num_locations}")
        print("  Location IDs:")
        for loc_id in processor.locations:
            loc = processor.locations[loc_id]
            print(f"    {loc_id}: {loc.original_city}, {loc.original_region}")
        return False


def test_batch_normalization():
    """Test batch normalization efficiency."""
    print()
    print("=" * 60)
    print("TEST: Batch Place Normalization")
    print("=" * 60)
    print()

    # Track how many times AI is called
    ai_calls = [0]

    def mock_synthesize(prompt):
        ai_calls[0] += 1
        if "Normalize these place names" in prompt:
            # Batch request
            return '''{
                "Chatham, MA": "Chatham, Massachusetts, USA",
                "Boston, Mass": "Boston, Massachusetts, USA",
                "London, England": "London, England, United Kingdom"
            }'''
        return "Unknown, Unknown, Unknown"

    processor = LocationProcessor(synthesize_fn=mock_synthesize)

    # Batch normalize
    places = ["Chatham, MA", "Boston, Mass", "London, England"]
    result = processor.normalize_places_batch(places)

    print(f"Batch normalized {len(places)} places")
    print(f"AI calls made: {ai_calls[0]}")
    print(f"Results: {result}")

    # Should only make 1 AI call for batch
    if ai_calls[0] == 1:
        print("✓ PASS: Batch normalization uses single AI call")
        return True
    else:
        print(f"✗ FAIL: Expected 1 AI call, got {ai_calls[0]}")
        return False


def test_extract_with_normalization():
    """Test that extract_locations_from_research normalizes places."""
    print()
    print("=" * 60)
    print("TEST: Extract Locations with Pre-Normalization")
    print("=" * 60)
    print()

    def mock_synthesize(prompt):
        if "Normalize these place names" in prompt:
            return '''{
                "Chatham, Barnstable, MA": "Chatham, Massachusetts, USA",
                "Chatham, Massachusetts": "Chatham, Massachusetts, USA"
            }'''
        if "Chatham" in prompt and "Normalize this place" in prompt:
            return "Chatham, Massachusetts, USA"
        return "Unknown, Unknown, Unknown"

    processor = LocationProcessor(synthesize_fn=mock_synthesize)

    # Create mock research results with same place in different formats
    research_results = [
        {
            "individual_id": "p1",
            "full_name": "John Smith",
            "birth_place": "Chatham, Barnstable, MA",
            "death_place": "Chatham, Massachusetts",  # Same place, different format
            "birth_year": 1701,
            "death_year": 1763
        }
    ]

    processor.extract_locations_from_research(research_results, verbose=True)

    num_locations = len(processor.locations)
    print(f"Locations after extraction: {num_locations}")

    if num_locations == 1:
        location = list(processor.locations.values())[0]
        connections = len(location.ancestor_connections)
        print(f"Connections: {connections}")
        print(f"Location: {location.name} ({location.original_city}, {location.original_region})")

        if connections == 2:
            print("✓ PASS: Same person's birth and death place deduped correctly")
            return True
        else:
            print(f"✗ FAIL: Expected 2 connections, got {connections}")
            return False
    else:
        print(f"✗ FAIL: Expected 1 location, got {num_locations}")
        for loc_id, loc in processor.locations.items():
            print(f"  {loc_id}: {loc.name} @ {loc.original_city}, {loc.original_region}")
        return False


if __name__ == "__main__":
    all_passed = True

    all_passed &= test_normalize_place_caching()
    all_passed &= test_normalize_place_with_mock_ai()
    all_passed &= test_location_deduplication()
    all_passed &= test_batch_normalization()
    all_passed &= test_extract_with_normalization()

    print()
    print("=" * 60)
    print("FINAL RESULT")
    print("=" * 60)
    if all_passed:
        print("ALL TESTS PASSED!")
        sys.exit(0)
    else:
        print("SOME TESTS FAILED")
        sys.exit(1)
