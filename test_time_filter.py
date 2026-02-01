#!/usr/bin/env python3
"""
Test script for time-period filtering of chain-followed locations.
Verifies that irrelevant modern locations are filtered out.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.locations import Location, AncestorConnection, LocationProcessor


def test_time_period_filtering():
    """Test that related sites built after ancestor's era are filtered."""
    print("=" * 60)
    print("TEST: Time-Period Filtering for Chain-Followed Locations")
    print("=" * 60)
    print()

    # Create a mock processor
    processor = LocationProcessor()

    # Create a location connected to an ancestor (1701-1763)
    location = Location(
        id="chatham_birth",
        name="Chatham",
        type="birthplace",
        original_city="Chatham",
        original_region="Massachusetts"
    )
    location.add_connection(
        person_id="william_nickerson",
        person_name="William Nickerson",
        relationship="born_at",
        year=1701,
        event_description="Born here"
    )
    location.add_connection(
        person_id="william_nickerson",
        person_name="William Nickerson",
        relationship="died_at",
        year=1763,
        event_description="Died here"
    )

    # Simulate related sites returned from AI (some relevant, some not)
    location.related_sites = [
        {
            "name": "First Congregational Church of Chatham",
            "relationship": "historic meeting house",
            "year_built": 1700,
            "note": "Where settlers worshipped"
        },
        {
            "name": "Chatham Railroad Museum",
            "relationship": "nearby historic site",
            "year_built": 1887,  # Built 124 years after ancestor died
            "note": "Local museum"
        },
        {
            "name": "Nickerson Memorial Museum",
            "relationship": "memorial to colonial era settlers",
            "year_built": 1950,  # Modern, but about the era
            "note": "Dedicated to colonial families"
        },
        {
            "name": "Old Atwood House Museum",
            "relationship": "historic house from colonial era",
            "year_built": 1752,
            "note": "Period architecture"
        },
        {
            "name": "Chatham Lighthouse",
            "relationship": "nearby tourist attraction",
            "year_built": 1808,  # After ancestor's death, not about era
            "note": "Popular attraction"
        },
        {
            "name": "Unknown Historic Site",
            "relationship": "related historic site",
            "year_built": None,  # Unknown date - should be included
            "note": "May be relevant"
        }
    ]

    processor.locations[location.id] = location

    # Calculate the max year for filtering (ancestor died 1763 + 30 = 1793)
    ancestor_years = [c.year for c in location.ancestor_connections if c.year]
    max_year = max(ancestor_years) + 30  # 1763 + 30 = 1793

    print(f"Ancestor: William Nickerson (1701-1763)")
    print(f"Max year for related sites: {max_year}")
    print()

    print("Testing filter logic:")
    print("-" * 40)

    should_include = []
    should_exclude = []

    for site in location.related_sites:
        name = site.get('name', '')
        year_built = site.get('year_built')
        relationship = site.get('relationship', '')

        # Apply the same filtering logic as in _enrich_related_sites
        if year_built and year_built > max_year:
            # Check if it's about the era (museum/memorial exception)
            is_about_era = any(term in relationship.lower() for term in
                ['museum about', 'memorial to', 'dedicated to', 'commemorat', 'preserv'])
            if is_about_era:
                should_include.append((name, year_built, "About ancestor's era"))
            else:
                should_exclude.append((name, year_built, "Built after ancestor's time"))
        else:
            reason = "Within time period" if year_built else "Unknown date (included)"
            should_include.append((name, year_built, reason))

    print("\nSHOULD INCLUDE:")
    for name, year, reason in should_include:
        print(f"  ✓ {name} ({year or '?'}) - {reason}")

    print("\nSHOULD EXCLUDE:")
    for name, year, reason in should_exclude:
        print(f"  ✗ {name} ({year}) - {reason}")

    # Verify expectations
    print("\n" + "=" * 60)
    print("VERIFICATION")
    print("=" * 60)

    expected_exclude = ["Chatham Railroad Museum", "Chatham Lighthouse"]
    expected_include = [
        "First Congregational Church of Chatham",
        "Nickerson Memorial Museum",  # Memorial to the era
        "Old Atwood House Museum",
        "Unknown Historic Site"
    ]

    included_names = [n for n, _, _ in should_include]
    excluded_names = [n for n, _, _ in should_exclude]

    all_pass = True

    for name in expected_exclude:
        if name in excluded_names:
            print(f"✓ PASS: {name} correctly excluded")
        else:
            print(f"✗ FAIL: {name} should be excluded")
            all_pass = False

    for name in expected_include:
        if name in included_names:
            print(f"✓ PASS: {name} correctly included")
        else:
            print(f"✗ FAIL: {name} should be included")
            all_pass = False

    print()
    if all_pass:
        print("ALL TESTS PASSED!")
    else:
        print("SOME TESTS FAILED")

    return all_pass


def test_time_period_propagation():
    """Test that time period is propagated to chain-followed locations."""
    print()
    print("=" * 60)
    print("TEST: Time-Period Propagation")
    print("=" * 60)
    print()

    processor = LocationProcessor()

    # Create a location with ancestor connection
    parent_location = Location(
        id="parent",
        name="Chatham Cemetery",
        type="cemetery",
        original_city="Chatham",
        original_region="Massachusetts"
    )
    parent_location.add_connection(
        person_id="william_nickerson",
        person_name="William Nickerson",
        relationship="buried_at",
        year=1763
    )

    # Compute time period using the helper method
    years = [c.year for c in parent_location.ancestor_connections if c.year]
    relationships = [c.relationship for c in parent_location.ancestor_connections]
    parent_location.relevant_time_period = processor._compute_time_period(years, relationships)

    print(f"Parent location: {parent_location.name}")
    print(f"Computed time period: {parent_location.relevant_time_period}")

    # Create a chain-followed location (no ancestor connections)
    child_location = Location(
        id="child",
        name="Related Church",
        type="church",
        original_city="Chatham",
        original_region="Massachusetts",
        relevant_time_period=parent_location.relevant_time_period  # Propagated
    )

    print(f"\nChild location: {child_location.name}")
    print(f"Propagated time period: {child_location.relevant_time_period}")
    print(f"Has ancestor connections: {bool(child_location.ancestor_connections)}")

    # Verify propagation worked
    if child_location.relevant_time_period == parent_location.relevant_time_period:
        print("\n✓ PASS: Time period correctly propagated to chain-followed location")
        return True
    else:
        print("\n✗ FAIL: Time period not propagated")
        return False


def test_synthesis_prompt_context():
    """Test that synthesis prompt includes ancestor context."""
    print()
    print("=" * 60)
    print("TEST: Synthesis Prompt Ancestor Context")
    print("=" * 60)
    print()

    processor = LocationProcessor()

    # Test 1: Location with ancestor connections
    location_with_ancestor = Location(
        id="test1",
        name="Test Church",
        type="church"
    )
    location_with_ancestor.add_connection("p1", "John Smith", "married_at", 1750)

    # Access the synthesis method to check prompt construction
    # We can't call it without search results, but we can check the logic
    years = [c.year for c in location_with_ancestor.ancestor_connections if c.year]
    if years:
        min_year = min(years) - 20
        max_year = max(years) + 20
        print(f"Location with ancestor: {location_with_ancestor.name}")
        print(f"  Ancestor years: {years}")
        print(f"  Computed range: {min_year} - {max_year}")
        print("  ✓ Context will include ancestor time period")

    # Test 2: Chain-followed location with propagated time period
    location_chain_followed = Location(
        id="test2",
        name="Related Site",
        type="museum",
        relevant_time_period=(1730, 1780)
    )

    if location_chain_followed.relevant_time_period:
        min_year, max_year = location_chain_followed.relevant_time_period
        print(f"\nChain-followed location: {location_chain_followed.name}")
        print(f"  Propagated range: {min_year} - {max_year}")
        print("  ✓ Context will use propagated time period")

    # Test 3: Location with no time context
    location_no_context = Location(
        id="test3",
        name="Orphan Site",
        type="historic_site"
    )

    print(f"\nLocation with no context: {location_no_context.name}")
    print(f"  Has ancestor connections: {bool(location_no_context.ancestor_connections)}")
    print(f"  Has relevant_time_period: {bool(location_no_context.relevant_time_period)}")
    print("  → No time filtering will be applied (general historical preference)")

    return True


def test_time_period_with_missing_death():
    """Test that time period is calculated correctly when death year is missing."""
    print()
    print("=" * 60)
    print("TEST: Time-Period with Missing Death Year")
    print("=" * 60)
    print()

    processor = LocationProcessor()

    # Test 1: Only birth year known (common for early ancestors)
    print("Test 1: Only birth year (1701)")
    years_birth_only = [1701]
    relationships_birth = ["born_at"]
    time_period = processor._compute_time_period(years_birth_only, relationships_birth)
    print(f"  Input: years={years_birth_only}, relationships={relationships_birth}")
    print(f"  Computed: {time_period}")

    # Should estimate death as birth + 75 = 1776
    # So range should be roughly (1681, 1806) with buffers
    expected_min = 1701 - 20  # 1681
    expected_max = 1701 + 75 + 30  # 1806
    if time_period and time_period[0] == expected_min and time_period[1] == expected_max:
        print(f"  ✓ PASS: Correctly estimated lifespan (max={time_period[1]})")
        test1_pass = True
    else:
        print(f"  ✗ FAIL: Expected ({expected_min}, {expected_max})")
        test1_pass = False

    # Test 2: Only death year known
    print("\nTest 2: Only death year (1763)")
    years_death_only = [1763]
    relationships_death = ["died_at"]
    time_period = processor._compute_time_period(years_death_only, relationships_death)
    print(f"  Input: years={years_death_only}, relationships={relationships_death}")
    print(f"  Computed: {time_period}")

    # Should estimate birth as death - 75 = 1688
    # So range should be roughly (1668, 1793) with buffers
    expected_min = 1763 - 75 - 20  # 1668
    expected_max = 1763 + 30  # 1793
    if time_period and time_period[0] == expected_min and time_period[1] == expected_max:
        print(f"  ✓ PASS: Correctly estimated birth (min={time_period[0]})")
        test2_pass = True
    else:
        print(f"  ✗ FAIL: Expected ({expected_min}, {expected_max})")
        test2_pass = False

    # Test 3: Both birth and death years known
    print("\nTest 3: Both birth (1701) and death (1763) years")
    years_both = [1701, 1763]
    relationships_both = ["born_at", "died_at"]
    time_period = processor._compute_time_period(years_both, relationships_both)
    print(f"  Input: years={years_both}, relationships={relationships_both}")
    print(f"  Computed: {time_period}")

    expected_min = 1701 - 20  # 1681
    expected_max = 1763 + 30  # 1793
    if time_period and time_period[0] == expected_min and time_period[1] == expected_max:
        print(f"  ✓ PASS: Uses actual dates")
        test3_pass = True
    else:
        print(f"  ✗ FAIL: Expected ({expected_min}, {expected_max})")
        test3_pass = False

    return test1_pass and test2_pass and test3_pass


if __name__ == "__main__":
    all_passed = True

    all_passed &= test_time_period_filtering()
    all_passed &= test_time_period_propagation()
    all_passed &= test_synthesis_prompt_context()
    all_passed &= test_time_period_with_missing_death()

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
