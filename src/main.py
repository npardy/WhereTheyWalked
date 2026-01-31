"""
Where They Walked - Main Application
Transforms GEDCOM files into enriched family history reports.
"""

import json
import os
from pathlib import Path
from datetime import datetime

from .gedcom_parser import GedcomParser
from .researcher import AncestorResearcher, ResearchResult
from .locations import LocationProcessor, create_nominatim_geocoder


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
        
        return [r.to_dict() for r in results]
    
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
        
        # Extract locations from research results
        result_dicts = [r.to_dict() for r in self.research_results.values()]
        self.location_processor.extract_locations_from_research(result_dicts)
        
        if verbose:
            print(f"Extracted {len(self.location_processor.locations)} unique locations")
        
        # Enrich and geocode
        self.location_processor.enrich_locations(verbose=verbose)
        
        return self.location_processor.to_dict()["stats"]
    
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
            "timeline": self.get_timeline(),
            "notable": self.get_notable_ancestors(),
            "shared_locations": self.get_shared_locations(2)
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


def main():
    """Command line interface."""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python main.py <gedcom_file> [--limit N] [--output FILE]")
        sys.exit(1)
    
    filepath = sys.argv[1]
    limit = None
    output = "output.json"
    
    # Parse args
    args = sys.argv[2:]
    for i, arg in enumerate(args):
        if arg == "--limit" and i + 1 < len(args):
            limit = int(args[i + 1])
        elif arg == "--output" and i + 1 < len(args):
            output = args[i + 1]
    
    # Initialize app (without search/synthesis for CLI test)
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


if __name__ == "__main__":
    main()
