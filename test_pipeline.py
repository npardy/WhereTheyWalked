#!/usr/bin/env python3
"""
Test script for Where They Walked pipeline.
Runs real searches and Haiku synthesis on sample ancestors.
"""

import json
import sys
import os

# Add src directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src'))

from gedcom_parser import GedcomParser
from researcher import AncestorResearcher, create_anthropic_synthesizer


def run_test(gedcom_path: str, num_ancestors: int = 5, notable_only: bool = True):
    """
    Test the full pipeline on a sample of ancestors.
    
    Args:
        gedcom_path: Path to GEDCOM file
        num_ancestors: How many to process
        notable_only: If True, prioritize ancestors likely to have rich results
    """
    print(f"Loading GEDCOM: {gedcom_path}")
    parser = GedcomParser()
    data = parser.parse_file(gedcom_path)
    
    stats = data['stats']
    print(f"Found {stats['total_individuals']} individuals, {stats['total_families']} families")
    print(f"Unique surnames: {stats['unique_surnames']}")
    print(f"By century: {stats['by_century']}")
    print()
    
    # Get researchable individuals
    researchable = parser.get_researchable_individuals()
    print(f"Researchable: {len(researchable)}")
    
    # Pick sample - prioritize those with dates (more likely to find good results)
    if notable_only:
        # Pick older ancestors with dates - more likely to be documented
        sample = [ind for ind in researchable if ind.has_dates and ind.birth_year and ind.birth_year < 1800][:num_ancestors]
    else:
        sample = researchable[:num_ancestors]
    
    print(f"Testing on {len(sample)} ancestors:")
    for ind in sample:
        print(f"  - {ind.full_name} ({ind.birth_year or '?'}-{ind.death_year or '?'})")
    print()
    
    # For now, we'll use a placeholder search function
    # In production, this would call a real search API
    def placeholder_search(query: str) -> str:
        print(f"  [Would search: {query}]")
        return f"No results - placeholder search for: {query}"
    
    # Check if we have Anthropic API key
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if api_key:
        print("Anthropic API key found - using real Haiku synthesis")
        synthesize_fn = create_anthropic_synthesizer(api_key)
    else:
        print("No ANTHROPIC_API_KEY - using placeholder synthesis")
        synthesize_fn = lambda prompt: json.dumps({
            "biography": "Placeholder - no API key",
            "confidence": "low"
        })
    
    # Create researcher
    researcher = AncestorResearcher(
        search_fn=placeholder_search,
        synthesize_fn=synthesize_fn
    )
    
    # Process each ancestor
    results = []
    for i, ind in enumerate(sample):
        print(f"\n[{i+1}/{len(sample)}] Researching: {ind.full_name}")
        
        ind_dict = {
            'id': ind.id,
            'full_name': ind.full_name,
            'birth_year': ind.birth_year,
            'death_year': ind.death_year,
            'birth_place': ind.birth_place,
            'death_place': ind.death_place,
            'search_query': ind.search_query,
            'needs_confirmation': ind.needs_confirmation
        }
        
        result = researcher.research_individual(ind_dict, individual_obj=ind, verbose=True)
        results.append(result)
        
        print(f"  Confidence: {result.confidence}")
        if result.biography_short:
            print(f"  Summary: {result.biography_short}")
        if result.locations:
            print(f"  Locations: {len(result.locations)}")
        if result.needs_confirmation:
            print(f"  ⚠ Needs confirmation: {result.confirmation_reason}")
    
    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    
    confidence_counts = {"high": 0, "medium": 0, "low": 0}
    notable_count = 0
    location_count = 0
    
    for r in results:
        confidence_counts[r.confidence] = confidence_counts.get(r.confidence, 0) + 1
        if r.notable:
            notable_count += 1
        location_count += len(r.locations)
    
    print(f"Processed: {len(results)} ancestors")
    print(f"Confidence: {confidence_counts}")
    print(f"Notable ancestors: {notable_count}")
    print(f"Total locations found: {location_count}")
    
    # Save results
    output_path = "test_results.json"
    with open(output_path, "w") as f:
        json.dump([r.to_dict() for r in results], f, indent=2)
    print(f"\nResults saved to: {output_path}")
    
    return results


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_pipeline.py <gedcom_file> [num_ancestors]")
        print("Example: python test_pipeline.py family_tree.ged 5")
        sys.exit(1)
    
    gedcom_path = sys.argv[1]
    num = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    
    run_test(gedcom_path, num_ancestors=num)
