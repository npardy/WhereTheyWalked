"""
Where They Walked - Main Application
Transforms GEDCOM files into enriched family history reports.
"""

import json
import os
from pathlib import Path
from datetime import datetime

from .gedcom_parser import GedcomParser
from .researcher import AncestorResearcher, ResearchResult, create_anthropic_synthesizer, get_token_tracker
from .locations import LocationProcessor, create_nominatim_geocoder
from .events import EventProcessor, HistoricEvent
from .search import (
    create_serpapi_search,
    create_brave_search,
    create_auto_search,
    create_mock_search,
    create_deep_search,
    get_available_providers
)


class WhereTheyWalked:
    """Main application for generating family history reports."""
    
    def __init__(self, search_fn=None, synthesize_fn=None, geocode_fn=None):
        """
        Initialize the application.
        
        Args:
            search_fn: Function for web search (query -> results string)
            synthesize_fn: Function for AI synthesis (prompt -> response string)
            geocode_fn: Function for geocoding (address -> (lat, lon) or None)
        """
        self.search_fn = search_fn
        self.synthesize_fn = synthesize_fn
        self.geocode_fn = geocode_fn or create_nominatim_geocoder()
        
        self.parser = GedcomParser()
        self.researcher = AncestorResearcher(
            search_fn=search_fn,
            synthesize_fn=synthesize_fn
        )
        self.location_processor = LocationProcessor(
            search_fn=search_fn,
            synthesize_fn=synthesize_fn,
            geocode_fn=self.geocode_fn
        )
        self.event_processor = EventProcessor(
            search_fn=search_fn,
            synthesize_fn=synthesize_fn
        )

        self.individuals = {}
        self.families = {}
        self.research_results = {}
    
    def load_gedcom(self, filepath: str) -> dict:
        """Load and parse a GEDCOM file."""
        data = self.parser.parse_file(filepath)
        self.individuals = self.parser.individuals
        self.families = self.parser.families
        return data["stats"]
    
    def get_researchable(self, min_year: int = None, max_year: int = None, 
                         limit: int = None) -> list:
        """Get list of individuals worth researching."""
        individuals = self.parser.get_researchable_individuals(
            min_year=min_year, 
            max_year=max_year
        )
        if limit:
            individuals = individuals[:limit]
        return [ind.to_dict() for ind in individuals]
    
    def research_ancestors(self, individuals: list = None, 
                          min_year: int = None, max_year: int = None,
                          limit: int = None,
                          progress_callback=None,
                          verbose: bool = False) -> list[dict]:
        """
        Research ancestors and generate enriched data.
        
        Args:
            individuals: Optional list of individual dicts to research
            min_year: Minimum birth year to include
            max_year: Maximum birth year to include  
            limit: Maximum number to research
            progress_callback: Optional callback(current, total, result)
            verbose: Print progress
            
        Returns:
            List of research result dicts
        """
        if individuals is None:
            individuals = self.get_researchable(
                min_year=min_year,
                max_year=max_year,
                limit=limit
            )
        
        # Get Individual objects for timeline validation
        individual_objects = {ind.id: ind for ind in self.parser.individuals.values()}
        
        results = self.researcher.research_batch(
            individuals,
            individual_objects=individual_objects,
            progress_callback=progress_callback,
            verbose=verbose
        )
        
        # Store results
        for result in results:
            self.research_results[result.individual_id] = result

        # Dedupe notable relatives against the family tree
        self._dedupe_notable_relatives()

        return [r.to_dict() for r in results]

    def _dedupe_notable_relatives(self):
        """
        Check if notable relatives are already in the family tree.
        If so, link to them by ID instead of treating as external notable.

        CURRENT BEHAVIOR:
        - Matches notable relatives by name against tree members
        - Adds `in_tree: True` and `tree_id` to link them
        - Does NOT merge information - just creates the link

        FUTURE ENHANCEMENT (requires careful testing):
        A more advanced version could merge discovered information:

        1. CROSS-REFERENCE MENTIONS: When ancestor A's research mentions
           ancestor B (who is in tree), collect those mentions and compare
           with B's own research results.

        2. INFORMATION MERGING: If A's research reveals new facts about B
           that B's own research didn't find, those could be added to B's
           profile with source attribution.

        3. CONFLICT DETECTION: When A says something about B that conflicts
           with B's own research (different dates, places, etc.), flag for
           manual review rather than auto-merging.

        4. SAFEGUARDS NEEDED:
           - Confidence scoring for merged info
           - Clear source attribution ("discovered via John Bowne's research")
           - Conflict flagging with diff display
           - Rollback capability
           - Name disambiguation (John Winthrop Sr vs Jr)
           - Circular reference prevention

        5. TESTING REQUIRED:
           - Unit tests for name matching edge cases
           - Integration tests with known family trees
           - Manual review of merge quality on real data
           - Performance testing with large trees (500+ individuals)

        For now, linking without merging is safer and still valuable -
        users can manually compare linked profiles.
        """
        # Build a lookup of all individuals by normalized name
        name_to_individual = {}
        for ind in self.parser.individuals.values():
            # Normalize name for matching
            name_lower = ind.full_name.lower().strip()
            name_to_individual[name_lower] = ind

            # Also add without middle names/initials for fuzzy matching
            parts = name_lower.split()
            if len(parts) >= 2:
                short_name = f"{parts[0]} {parts[-1]}"
                if short_name not in name_to_individual:
                    name_to_individual[short_name] = ind

        # Check each research result's notable relatives
        for result in self.research_results.values():
            if not result.notable_relatives:
                continue

            updated_relatives = []
            for rel in result.notable_relatives:
                rel_name = rel.get('name', '').lower().strip()

                # Check if this person is in the tree
                matched_individual = None

                # Try exact match
                if rel_name in name_to_individual:
                    matched_individual = name_to_individual[rel_name]
                else:
                    # Try partial match (first + last name)
                    parts = rel_name.split()
                    if len(parts) >= 2:
                        short_name = f"{parts[0]} {parts[-1]}"
                        if short_name in name_to_individual:
                            matched_individual = name_to_individual[short_name]

                if matched_individual:
                    # This relative is in the tree - link to them
                    rel['in_tree'] = True
                    rel['tree_id'] = matched_individual.id
                    rel['tree_name'] = matched_individual.full_name
                    rel['tree_birth_year'] = matched_individual.birth_year
                    rel['tree_death_year'] = matched_individual.death_year
                else:
                    rel['in_tree'] = False

                updated_relatives.append(rel)

            result.notable_relatives = updated_relatives
    
    def process_locations(self, verbose: bool = False) -> dict:
        """
        Process all locations from research results.
        Extracts, dedupes, enriches with search, and geocodes.
        
        Args:
            verbose: Print progress
            
        Returns:
            Location stats dict
        """
        if not self.research_results:
            return {"error": "No research results. Run research_ancestors() first."}
        
        # Extract locations from research results (normalizes places for deduplication)
        result_dicts = [r.to_dict() for r in self.research_results.values()]
        self.location_processor.extract_locations_from_research(result_dicts, verbose=verbose)

        if verbose:
            print(f"Extracted {len(self.location_processor.locations)} unique locations")
        
        # Enrich and geocode
        self.location_processor.enrich_locations(verbose=verbose)
        
        return self.location_processor.to_dict()["stats"]
    
    def process_events(self, verbose: bool = False, chain_follow: bool = True) -> dict:
        """
        Process all historic events from research results.
        Extracts, dedupes, enriches with search, and links ancestors.

        Args:
            verbose: Print progress
            chain_follow: If True, also search and enrich related events discovered

        Returns:
            Event stats dict
        """
        if not self.research_results:
            return {"error": "No research results. Run research_ancestors() first."}

        # Extract events from research results
        results_list = list(self.research_results.values())
        self.event_processor.extract_events_from_research(results_list)

        if verbose:
            print(f"Extracted {len(self.event_processor.events)} unique historic events")

        # Enrich events with dedicated searches (with chain-following)
        stats = self.event_processor.enrich_events(
            verbose=verbose,
            chain_follow=chain_follow
        )

        return stats

    def cross_link_entities(self, verbose: bool = False) -> dict:
        """
        Cross-link all entities: ancestors, locations, and events.

        This creates bidirectional links between:
        - Events and locations (events that happened at specific locations)
        - Ancestors and events (which ancestors were involved in which events)
        - Ancestors and locations (which ancestors are connected to which locations)

        Should be called after process_locations() and process_events().

        Args:
            verbose: Print progress

        Returns:
            Stats about cross-linking
        """
        stats = {
            "event_location_links": 0,
            "location_event_links": 0,
            "ancestor_event_links": 0,
            "ancestor_location_links": 0
        }

        if verbose:
            print("Cross-linking entities...")

        # 1. Link events to locations
        for event in self.event_processor.events.values():
            if not event.location:
                continue

            event_location = event.location.lower()

            for location in self.location_processor.locations.values():
                # Check if event location matches this location
                loc_matches = (
                    event_location in location.name.lower() or
                    location.name.lower() in event_location or
                    (location.original_city and event_location in location.original_city.lower()) or
                    (location.original_region and event_location in location.original_region.lower())
                )

                if loc_matches:
                    # Add event to location's historic_events
                    event_entry = {
                        "event_id": event.id,
                        "name": event.name,
                        "year": event.year,
                        "type": event.event_type,
                        "description": event.short_description or event.full_description
                    }

                    # Avoid duplicates
                    existing_ids = [e.get("event_id") for e in location.historic_events if isinstance(e, dict)]
                    if event.id not in existing_ids:
                        location.historic_events.append(event_entry)
                        stats["location_event_links"] += 1

                    # Add location to event's related_locations
                    if location.id not in event.related_locations:
                        event.related_locations.append(location.id)
                        stats["event_location_links"] += 1

        # 2. Cross-reference ancestors between events and locations
        for event in self.event_processor.events.values():
            for conn in event.ancestor_connections:
                person_id = conn.person_id

                # Find all locations connected to this ancestor
                ancestor_locations = self.location_processor.get_locations_for_person(person_id)

                for loc in ancestor_locations:
                    # If this location is geographically related to the event,
                    # add the event to the location's ancestor-related events
                    if loc.id not in event.related_locations:
                        # Add weak link if same region
                        if (loc.original_region and event.region and
                            loc.original_region.lower() in event.region.lower()):
                            event.related_locations.append(loc.id)

        # 3. Ensure all ancestor connections are properly linked
        for result in self.research_results.values():
            person_id = result.individual_id

            # Count event links
            person_events = self.event_processor.get_events_for_ancestor(person_id)
            stats["ancestor_event_links"] += len(person_events)

            # Count location links
            person_locations = self.location_processor.get_locations_for_person(person_id)
            stats["ancestor_location_links"] += len(person_locations)

        if verbose:
            print(f"  Event→Location links: {stats['event_location_links']}")
            print(f"  Location→Event links: {stats['location_event_links']}")
            print(f"  Ancestor→Event links: {stats['ancestor_event_links']}")
            print(f"  Ancestor→Location links: {stats['ancestor_location_links']}")

        return stats

    def get_events(self, event_type: str = None) -> list[dict]:
        """
        Get all processed historic events.

        Args:
            event_type: Filter by type (war, trial, political, etc.)
        """
        if event_type:
            events = self.event_processor.get_events_by_type(event_type)
        else:
            events = list(self.event_processor.events.values())

        return [evt.to_dict() for evt in events]

    def get_shared_events(self, min_ancestors: int = 2) -> list[dict]:
        """Get events connected to multiple ancestors."""
        events = self.event_processor.get_shared_events(min_ancestors)
        return [evt.to_dict() for evt in events]

    def get_notable_ancestors(self) -> list[dict]:
        """Get ancestors flagged as notable."""
        return [
            r.to_dict() for r in self.research_results.values()
            if r.notable
        ]
    
    def get_locations(self, location_type: str = None) -> list[dict]:
        """
        Get all processed locations.
        
        Args:
            location_type: Filter by type (cemetery, museum, historic_house, etc.)
        """
        if location_type:
            locations = self.location_processor.get_locations_by_type(location_type)
        else:
            locations = list(self.location_processor.locations.values())
        
        return [loc.to_dict() for loc in locations]
    
    def get_shared_locations(self, min_ancestors: int = 2) -> list[dict]:
        """Get locations connected to multiple ancestors."""
        locations = self.location_processor.get_shared_locations(min_ancestors)
        return [loc.to_dict() for loc in locations]
    
    def get_locations_for_person(self, person_id: str) -> list[dict]:
        """Get all locations connected to a specific person."""
        locations = self.location_processor.get_locations_for_person(person_id)
        return [loc.to_dict() for loc in locations]
    
    def get_locations_by_region(self, region: str) -> list[dict]:
        """Get locations in a region (for trip planning)."""
        locations = self.location_processor.get_locations_by_region(region)
        return [loc.to_dict() for loc in locations]
    
    def get_timeline(self) -> list[dict]:
        """Get timeline of historic events connected to ancestors."""
        events = []
        for result in self.research_results.values():
            for event in result.historic_events:
                event_data = event.copy() if isinstance(event, dict) else event.to_dict()
                event_data["ancestor_name"] = result.full_name
                event_data["ancestor_id"] = result.individual_id
                events.append(event_data)
        
        # Add location historic events
        for loc in self.location_processor.locations.values():
            for event in loc.historic_events:
                event_data = event.copy() if isinstance(event, dict) else event
                event_data["location_name"] = loc.name
                event_data["location_id"] = loc.id
                events.append(event_data)
        
        # Sort by year
        events.sort(key=lambda x: x.get("year") or 9999)
        return events
    
    def get_stats(self) -> dict:
        """Get statistics about the research."""
        results = list(self.research_results.values())
        loc_stats = self.location_processor.to_dict()["stats"] if self.location_processor.locations else {}
        event_stats = self.event_processor.to_dict()["stats"] if self.event_processor.events else {}

        return {
            "ancestors": {
                "total_researched": len(results),
                "notable_count": sum(1 for r in results if r.notable),
                "high_confidence": sum(1 for r in results if r.confidence == "high"),
                "medium_confidence": sum(1 for r in results if r.confidence == "medium"),
                "low_confidence": sum(1 for r in results if r.confidence == "low"),
                "with_museum": sum(1 for r in results if r.has_museum),
                "with_cemetery": sum(1 for r in results if r.has_cemetery),
                "with_historic_site": sum(1 for r in results if r.has_historic_site),
                "mayflower_connections": sum(1 for r in results if r.mayflower_connection),
                "military_service": sum(1 for r in results if r.military_service),
            },
            "locations": loc_stats,
            "events": event_stats,
            "timeline": {
                "total_events": sum(len(r.historic_events) for r in results)
            }
        }
    
    def export_json(self, filepath: str):
        """Export all data to JSON."""
        data = {
            "generated_at": datetime.now().isoformat(),
            "version": "0.1.0",
            "stats": self.get_stats(),
            "ancestors": [r.to_dict() for r in self.research_results.values()],
            "locations": self.location_processor.to_dict(),
            "events": self.event_processor.to_dict(),
            "timeline": self.get_timeline(),
            "notable": self.get_notable_ancestors(),
            "shared_locations": self.get_shared_locations(2),
            "shared_events": self.get_shared_events(2)
        }

        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)

        return filepath
    
    def export_geojson(self, filepath: str):
        """Export locations as GeoJSON for mapping."""
        geojson = self.location_processor.to_geojson()
        
        with open(filepath, 'w') as f:
            json.dump(geojson, f, indent=2)
        
        return filepath
    
    def generate_location_report(self, location_id: str) -> dict:
        """Generate a rich report for a single location."""
        if location_id not in self.location_processor.locations:
            return {"error": f"Location {location_id} not found"}
        
        loc = self.location_processor.locations[location_id]
        
        return {
            "location": loc.to_dict(),
            "ancestor_details": [
                {
                    "connection": conn.to_dict(),
                    "ancestor": self.research_results.get(conn.person_id, {}).to_dict()
                        if conn.person_id in self.research_results else None
                }
                for conn in loc.ancestor_connections
            ]
        }
    
    def generate_trip_plan(self, region: str) -> dict:
        """Generate a trip plan for visiting locations in a region."""
        locations = self.get_locations_by_region(region)
        
        # Sort by type (museums first, then historic sites, then cemeteries)
        type_order = {"museum": 0, "historic_house": 1, "historic_site": 2, "church": 3, "cemetery": 4}
        locations.sort(key=lambda x: type_order.get(x.get("type", ""), 99))
        
        return {
            "region": region,
            "total_locations": len(locations),
            "visitable": [l for l in locations if l.get("is_visitable", True)],
            "locations": locations,
            "total_ancestors_connected": sum(
                len(l.get("ancestor_connections", [])) for l in locations
            )
        }


def create_app(search_provider: str = "auto",
               use_mock: bool = False,
               deep_search: bool = True,
               verbose: bool = False) -> WhereTheyWalked:
    """
    Create a fully-configured WhereTheyWalked application instance.

    This factory function automatically configures the search and synthesis
    functions based on available API keys in environment variables.

    Environment variables:
        ANTHROPIC_API_KEY: Required for AI synthesis (Claude Haiku)
        SERPAPI_KEY: For Google search via SerpAPI
        BRAVE_API_KEY: For Brave Search API

    Args:
        search_provider: Search provider to use:
            - "auto": Automatically select based on available API keys
            - "serpapi": Use SerpAPI (requires SERPAPI_KEY)
            - "brave": Use Brave Search (requires BRAVE_API_KEY)
            - "mock": Use mock search (for testing)
        use_mock: If True, use mock functions for both search and synthesis
        deep_search: If True, fetch full page content from top URLs (more thorough)
        verbose: Print configuration details

    Returns:
        Configured WhereTheyWalked instance

    Raises:
        ValueError: If required API keys are not available

    Example:
        # Auto-configure from environment
        app = create_app()

        # Use specific search provider with deep search
        app = create_app(search_provider="serpapi", deep_search=True)

        # Testing without API calls
        app = create_app(use_mock=True)
    """
    search_fn = None
    synthesize_fn = None

    if use_mock:
        if verbose:
            print("Using mock functions (no real API calls)")
        search_fn = create_mock_search()
        # Use mock synthesize (returns minimal placeholder data)
        from .researcher import mock_synthesize
        synthesize_fn = mock_synthesize
    else:
        # Configure search
        if search_provider == "mock":
            search_fn = create_mock_search()
            if verbose:
                print("Using mock search")
        elif search_provider == "auto":
            search_fn = create_auto_search()
            if search_fn and verbose:
                providers = get_available_providers()
                print(f"Auto-selected search provider: {providers[0] if providers else 'none'}")
        elif search_provider == "serpapi":
            search_fn = create_serpapi_search()
            if verbose:
                print("Using SerpAPI search")
        elif search_provider == "brave":
            search_fn = create_brave_search()
            if verbose:
                print("Using Brave Search")
        else:
            raise ValueError(f"Unknown search provider: {search_provider}")

        # Wrap with deep search if enabled
        if search_fn and deep_search and search_provider != "mock":
            search_fn = create_deep_search(search_fn, fetch_top_n=5)  # Guarantees 5 pages
            if verbose:
                print("Deep search enabled (fetching 5 full pages)")

        if not search_fn:
            if verbose:
                print("Warning: No search API configured. Set SERPAPI_KEY or BRAVE_API_KEY.")

        # Configure synthesis
        anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
        if anthropic_key:
            synthesize_fn = create_anthropic_synthesizer(anthropic_key)
            if verbose:
                print("Using Anthropic Claude Haiku for synthesis")
        else:
            if verbose:
                print("Warning: ANTHROPIC_API_KEY not set. Synthesis disabled.")

    # Create and return app
    return WhereTheyWalked(
        search_fn=search_fn,
        synthesize_fn=synthesize_fn,
        geocode_fn=create_nominatim_geocoder()
    )


def get_api_status() -> dict:
    """
    Check which APIs are configured and available.

    Returns:
        Dict with status of each API
    """
    return {
        "search": {
            "serpapi": bool(os.environ.get("SERPAPI_KEY")),
            "brave": bool(os.environ.get("BRAVE_API_KEY")),
            "available_providers": get_available_providers()
        },
        "synthesis": {
            "anthropic": bool(os.environ.get("ANTHROPIC_API_KEY"))
        },
        "geocoding": {
            "nominatim": True  # Always available (free, rate-limited)
        }
    }


def main():
    """Command line interface."""
    import sys

    if len(sys.argv) < 2:
        print("Usage: python main.py <gedcom_file> [--limit N] [--output FILE] [--research]")
        print("\nOptions:")
        print("  --limit N     Limit number of ancestors to research")
        print("  --output FILE Output file path (default: output.json)")
        print("  --research    Actually run research (requires API keys)")
        print("\nAPI Keys (set as environment variables):")
        print("  ANTHROPIC_API_KEY  Required for AI synthesis")
        print("  SERPAPI_KEY        For Google search via SerpAPI")
        print("  BRAVE_API_KEY      Alternative: Brave Search API")
        sys.exit(1)

    filepath = sys.argv[1]
    limit = None
    output = "output.json"
    do_research = "--research" in sys.argv

    # Parse args
    args = sys.argv[2:]
    for i, arg in enumerate(args):
        if arg == "--limit" and i + 1 < len(args):
            limit = int(args[i + 1])
        elif arg == "--output" and i + 1 < len(args):
            output = args[i + 1]

    # Check API status
    status = get_api_status()
    print("API Status:")
    print(f"  Search: {status['search']['available_providers'] or 'Not configured'}")
    print(f"  Synthesis: {'Configured' if status['synthesis']['anthropic'] else 'Not configured'}")
    print()

    # Initialize app
    if do_research:
        app = create_app(verbose=True)
    else:
        app = WhereTheyWalked()

    # Load GEDCOM
    print(f"Loading {filepath}...")
    stats = app.load_gedcom(filepath)
    print(f"Found {stats['total_individuals']} individuals, {stats['unique_surnames']} surnames")

    # Get researchable
    researchable = app.get_researchable(limit=limit)
    print(f"\n{len(researchable)} researchable individuals")

    # Show sample
    print("\nSample (first 5):")
    for ind in researchable[:5]:
        print(f"  {ind['full_name']} ({ind['birth_year'] or '?'}-{ind['death_year'] or '?'})")
        print(f"    Query: {ind['search_query']}")

    if do_research:
        if not status['synthesis']['anthropic']:
            print("\nError: ANTHROPIC_API_KEY required for research. Exiting.")
            sys.exit(1)

        print(f"\nResearching {len(researchable)} ancestors...")

        def progress(current, total, result):
            print(f"  [{current}/{total}] {result.full_name} - {result.confidence} confidence")

        results = app.research_ancestors(individuals=researchable, progress_callback=progress, verbose=True)

        print(f"\nProcessing locations...")
        loc_stats = app.process_locations(verbose=True)

        print(f"\nProcessing events...")
        event_stats = app.process_events(verbose=True, chain_follow=True)

        print(f"\nCross-linking entities...")
        link_stats = app.cross_link_entities(verbose=True)

        print(f"\nExporting to {output}...")
        app.export_json(output)

        # Summary
        stats = app.get_stats()
        print(f"\n=== Summary ===")
        print(f"Ancestors researched: {stats['ancestors']['total_researched']}")
        print(f"Notable ancestors: {stats['ancestors']['notable_count']}")
        print(f"High confidence: {stats['ancestors']['high_confidence']}")
        print(f"Locations found: {loc_stats.get('total_locations', 0)}")
        print(f"With coordinates: {loc_stats.get('with_coordinates', 0)}")
        print(f"Events found: {event_stats.get('total_events', 0)}")
        print(f"Events enriched: {event_stats.get('enriched', 0)}")
        print(f"Chain-followed events: {event_stats.get('chain_followed', 0)}")
        print(f"Cross-links created: {link_stats.get('event_location_links', 0) + link_stats.get('location_event_links', 0)}")

        # Token usage and cost summary
        tracker = get_token_tracker()
        if tracker.total_input_tokens > 0 or tracker.total_output_tokens > 0:
            tracker.print_summary()


if __name__ == "__main__":
    main()
