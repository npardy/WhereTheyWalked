"""
Location Processing for Where They Walked
Extracts locations from research results, dedupes, enriches with search,
and builds location-centric view of family history.
"""

import json
import re
import hashlib
from dataclasses import dataclass, field
from typing import Optional, Callable
from collections import defaultdict


@dataclass
class AncestorConnection:
    """A connection between an ancestor and a location."""
    person_id: str
    person_name: str
    relationship: str  # born_at, died_at, buried_at, married_at, lived_at, event_at
    year: Optional[int] = None
    event_description: Optional[str] = None
    
    def to_dict(self):
        return {
            "person_id": self.person_id,
            "person_name": self.person_name,
            "relationship": self.relationship,
            "year": self.year,
            "event_description": self.event_description
        }


@dataclass
class Location:
    """A location with rich context and family connections."""
    id: str
    name: str
    type: str  # cemetery, church, museum, historic_house, town, residence, other
    
    # Original reference (from GEDCOM/research)
    original_name: str = ""
    original_city: str = ""
    original_region: str = ""
    original_country: str = ""
    
    # Current status
    status: str = "unknown"  # exists, destroyed, moved, rebuilt, private, unknown
    status_details: Optional[str] = None
    
    # If moved, where to (chain-followable)
    moved_to: Optional[dict] = None  # {name, city, region, year, details}
    
    # Current visitable location (may differ from original if moved)
    current_name: Optional[str] = None
    current_address: Optional[str] = None
    coordinates: Optional[tuple] = None
    is_visitable: bool = True
    visit_notes: Optional[str] = None
    visitor_tips: Optional[str] = None
    
    # Rich content - the story of this place
    history: Optional[str] = None
    historic_events: list = field(default_factory=list)
    notable_connections: list = field(default_factory=list)  # Famous people, events, facts
    related_sites: list = field(default_factory=list)  # {name, relationship, note}
    
    # Family connections
    ancestor_connections: list[AncestorConnection] = field(default_factory=list)
    
    # Metadata
    source_urls: list = field(default_factory=list)
    confidence: str = "low"  # low, medium, high
    needs_verification: bool = False
    
    # Chain tracking (for moved locations)
    relocation_chain: list = field(default_factory=list)  # [{name, year, reason}, ...]
    final_destination: Optional[str] = None  # Where you can actually visit today
    
    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "original_name": self.original_name,
            "original_city": self.original_city,
            "original_region": self.original_region,
            "original_country": self.original_country,
            "status": self.status,
            "status_details": self.status_details,
            "moved_to": self.moved_to,
            "relocation_chain": self.relocation_chain,
            "final_destination": self.final_destination,
            "current_name": self.current_name,
            "current_address": self.current_address,
            "coordinates": list(self.coordinates) if self.coordinates else None,
            "is_visitable": self.is_visitable,
            "visit_notes": self.visit_notes,
            "visitor_tips": self.visitor_tips,
            "history": self.history,
            "historic_events": self.historic_events,
            "notable_connections": self.notable_connections,
            "related_sites": self.related_sites,
            "ancestor_connections": [c.to_dict() for c in self.ancestor_connections],
            "source_urls": self.source_urls,
            "confidence": self.confidence,
            "needs_verification": self.needs_verification
        }
    
    def add_connection(self, person_id: str, person_name: str, relationship: str,
                       year: int = None, event_description: str = None):
        """Add an ancestor connection, avoiding duplicates."""
        # Check for existing connection
        for conn in self.ancestor_connections:
            if conn.person_id == person_id and conn.relationship == relationship:
                return  # Already exists
        
        self.ancestor_connections.append(AncestorConnection(
            person_id=person_id,
            person_name=person_name,
            relationship=relationship,
            year=year,
            event_description=event_description
        ))


# Location types that need rich search vs just geocoding
SEARCHABLE_TYPES = {"cemetery", "church", "museum", "historic_house", "historic_site"}
GEOCODE_ONLY_TYPES = {"town", "city", "county", "region", "country", "residence"}


class LocationProcessor:
    """Process and enrich locations from research results."""
    
    def __init__(self, search_fn: Callable = None, 
                 synthesize_fn: Callable = None,
                 geocode_fn: Callable = None):
        """
        Initialize processor.
        
        Args:
            search_fn: Function(query) -> search results text
            synthesize_fn: Function(prompt) -> AI response
            geocode_fn: Function(address) -> (lat, lon) or None
        """
        self.search_fn = search_fn
        self.synthesize_fn = synthesize_fn
        self.geocode_fn = geocode_fn
        self.locations: dict[str, Location] = {}
    
    def _generate_location_id(self, name: str, city: str, region: str) -> str:
        """Generate consistent ID for deduplication."""
        key = f"{name.lower().strip()}|{city.lower().strip()}|{region.lower().strip()}"
        return hashlib.md5(key.encode()).hexdigest()[:12]
    
    def _normalize_location_name(self, name: str) -> str:
        """Normalize location name for matching."""
        name = name.lower().strip()
        # Remove common variations
        name = re.sub(r'\bcem(etery)?\b', 'cemetery', name)
        name = re.sub(r'\bch(urch)?\b', 'church', name)
        name = re.sub(r'\bgraveyard\b', 'cemetery', name)
        name = re.sub(r'\bburial ground\b', 'cemetery', name)
        name = re.sub(r'\s+', ' ', name)
        return name
    
    def _infer_location_type(self, name: str, context: str = "") -> str:
        """Infer location type from name and context."""
        name_lower = name.lower()
        context_lower = context.lower()
        
        if any(word in name_lower for word in ['cemetery', 'burial', 'graveyard', 'grave']):
            return "cemetery"
        if any(word in name_lower for word in ['church', 'chapel', 'cathedral', 'meeting house']):
            return "church"
        if any(word in name_lower for word in ['museum', 'historic site', 'monument']):
            return "museum"
        if any(word in name_lower for word in ['house', 'manor', 'estate', 'homestead']):
            return "historic_house"
        if 'buried' in context_lower or 'interred' in context_lower:
            return "cemetery"
        if 'married' in context_lower or 'wedding' in context_lower:
            return "church"
        if 'born' in context_lower or 'lived' in context_lower:
            return "residence"
        
        return "other"
    
    def _parse_place_string(self, place: str) -> dict:
        """Parse a place string into components."""
        if not place:
            return {"name": "", "city": "", "region": "", "country": ""}
        
        parts = [p.strip() for p in place.split(",")]
        
        result = {"name": "", "city": "", "region": "", "country": ""}
        
        if len(parts) == 1:
            result["city"] = parts[0]
        elif len(parts) == 2:
            result["city"] = parts[0]
            result["country"] = parts[1]
        elif len(parts) == 3:
            result["city"] = parts[0]
            result["region"] = parts[1]
            result["country"] = parts[2]
        elif len(parts) >= 4:
            result["name"] = parts[0]
            result["city"] = parts[1]
            result["region"] = parts[-2]
            result["country"] = parts[-1]
        
        return result
    
    def extract_locations_from_research(self, research_results: list) -> None:
        """
        Extract and dedupe locations from research results.
        
        Args:
            research_results: List of ResearchResult objects/dicts
        """
        for result in research_results:
            if isinstance(result, dict):
                result_dict = result
            else:
                result_dict = result.to_dict()
            
            person_id = result_dict.get("individual_id", "")
            person_name = result_dict.get("full_name", "")
            
            # Extract from birth place
            birth_place = result_dict.get("birth_place") or result_dict.get("birth_place_discovered")
            if birth_place:
                self._add_location_from_place(
                    birth_place, person_id, person_name, "born_at",
                    result_dict.get("birth_year"), f"Born here"
                )
            
            # Extract from death place
            death_place = result_dict.get("death_place") or result_dict.get("death_place_discovered")
            if death_place:
                self._add_location_from_place(
                    death_place, person_id, person_name, "died_at",
                    result_dict.get("death_year"), f"Died here"
                )
            
            # Extract from locations array (from synthesis)
            for loc in result_dict.get("locations", []):
                if isinstance(loc, dict):
                    name = loc.get("name", "")
                    loc_type = loc.get("type", "other")
                    address = loc.get("address", "")
                    description = loc.get("description", "")
                    coords = loc.get("coordinates")
                    
                    if name:
                        self._add_location(
                            name=name,
                            city="",  # Will be parsed from name/address
                            region="",
                            country="",
                            loc_type=loc_type,
                            person_id=person_id,
                            person_name=person_name,
                            relationship="event_at",
                            year=None,
                            event_description=description,
                            coordinates=tuple(coords) if coords else None,
                            address=address
                        )
            
            # Add source URLs to relevant locations
            source_urls = result_dict.get("source_urls", [])
            # Locations from this person's research may benefit from these URLs
    
    def _add_location_from_place(self, place: str, person_id: str, person_name: str,
                                  relationship: str, year: int = None,
                                  event_description: str = None) -> None:
        """Add location from a place string."""
        parsed = self._parse_place_string(place)
        loc_type = self._infer_location_type(place, relationship)
        
        self._add_location(
            name=parsed["name"] or parsed["city"],
            city=parsed["city"],
            region=parsed["region"],
            country=parsed["country"],
            loc_type=loc_type,
            person_id=person_id,
            person_name=person_name,
            relationship=relationship,
            year=year,
            event_description=event_description
        )
    
    def _add_location(self, name: str, city: str, region: str, country: str,
                      loc_type: str, person_id: str, person_name: str,
                      relationship: str, year: int = None,
                      event_description: str = None,
                      coordinates: tuple = None,
                      address: str = None) -> None:
        """Add or update a location with an ancestor connection."""
        # Generate ID for deduplication
        loc_id = self._generate_location_id(name or city, city, region)
        
        if loc_id in self.locations:
            # Add connection to existing location
            self.locations[loc_id].add_connection(
                person_id, person_name, relationship, year, event_description
            )
            # Update coordinates if we have them and location doesn't
            if coordinates and not self.locations[loc_id].coordinates:
                self.locations[loc_id].coordinates = coordinates
        else:
            # Create new location
            loc = Location(
                id=loc_id,
                name=name or city,
                type=loc_type,
                original_name=name,
                original_city=city,
                original_region=region,
                original_country=country,
                current_address=address,
                coordinates=coordinates
            )
            loc.add_connection(person_id, person_name, relationship, year, event_description)
            self.locations[loc_id] = loc
    
    def enrich_locations(self, verbose: bool = False) -> None:
        """
        Enrich locations with search and geocoding.
        Only searches for types that benefit from rich data.
        """
        for loc_id, location in self.locations.items():
            if verbose:
                print(f"Processing: {location.name} ({location.type})")
            
            # Determine if we need rich search or just geocoding
            if location.type in SEARCHABLE_TYPES:
                self._enrich_with_search(location, verbose)
            
            # Geocode if we don't have coordinates
            if not location.coordinates and self.geocode_fn:
                self._geocode_location(location, verbose)
    
    def _enrich_with_search(self, location: Location, verbose: bool = False,
                             _depth: int = 0, _max_depth: int = 5,
                             _visited: set = None) -> None:
        """
        Enrich a location with search and synthesis.
        Follows relocation chains (moved_to) and related sites up to _max_depth.

        Args:
            location: Location to enrich
            verbose: Print progress
            _depth: Current recursion depth
            _max_depth: Max recursion depth for chain-following
            _visited: Set of already-visited location IDs to prevent cycles
        """
        if not self.search_fn or not self.synthesize_fn:
            return

        # Track visited locations to prevent cycles
        if _visited is None:
            _visited = set()

        if location.id in _visited:
            return
        _visited.add(location.id)

        # Prevent infinite loops
        if _depth >= _max_depth:
            if verbose:
                print(f"  Max depth reached for {location.name}")
            location.needs_verification = True
            return

        # Build search query
        query_parts = [f'"{location.name}"']
        if location.original_city:
            query_parts.append(location.original_city)
        if location.original_region:
            query_parts.append(location.original_region)

        # Add type-specific terms
        if location.type == "cemetery":
            query_parts.append("cemetery history findagrave")
        elif location.type == "church":
            query_parts.append("church history parish")
        elif location.type == "museum":
            query_parts.append("museum historic site visiting")
        elif location.type == "historic_house":
            query_parts.append("historic house tours visiting")

        query = " ".join(query_parts)

        if verbose:
            print(f"  Searching: {query[:60]}...")

        # Search
        search_results = self.search_fn(query)

        if not search_results or len(search_results) < 50:
            location.needs_verification = True
            return

        # Extract URLs
        urls = re.findall(r'https?://[^\s\])<>"]+', search_results)
        location.source_urls = list(set(urls))[:5]

        # Synthesize
        synthesis = self._synthesize_location(location, search_results)
        self._apply_location_synthesis(location, synthesis)
        
        # If location was moved, follow the chain
        if location.status == "moved" and location.moved_to:
            moved_info = location.moved_to
            moved_to_name = moved_info.get("name")
            
            if moved_to_name and moved_to_name.lower() != location.name.lower():
                if verbose:
                    print(f"  → Following relocation: {location.name} → {moved_to_name}")
                
                # Track the chain
                location.relocation_chain.append({
                    "from": location.name,
                    "to": moved_to_name,
                    "year": moved_info.get("year"),
                    "details": moved_info.get("details")
                })
                
                # Create a temporary location to search the destination
                dest_location = Location(
                    id=self._generate_location_id(
                        moved_to_name, 
                        moved_info.get("city", location.original_city),
                        moved_info.get("region", location.original_region)
                    ),
                    name=moved_to_name,
                    type=location.type,
                    original_name=moved_to_name,
                    original_city=moved_info.get("city") or location.original_city,
                    original_region=moved_info.get("region") or location.original_region,
                    original_country=location.original_country
                )
                
                # Recursively enrich the destination
                self._enrich_with_search(dest_location, verbose, _depth + 1, _max_depth)
                
                # Copy final visitable info back to original location
                if dest_location.status == "exists":
                    # Destination exists - this is where to visit
                    location.final_destination = dest_location.name
                    location.current_name = dest_location.current_name or dest_location.name
                    location.current_address = dest_location.current_address
                    location.coordinates = dest_location.coordinates
                    location.is_visitable = dest_location.is_visitable
                    if dest_location.visit_notes:
                        location.visit_notes = f"Originally at {location.name}. Now: {dest_location.visit_notes}"
                    
                elif dest_location.status == "moved" and dest_location.relocation_chain:
                    # Destination also moved - extend chain
                    location.relocation_chain.extend(dest_location.relocation_chain)
                    location.final_destination = dest_location.final_destination
                    location.current_name = dest_location.current_name
                    location.current_address = dest_location.current_address
                    location.coordinates = dest_location.coordinates
                    location.is_visitable = dest_location.is_visitable
                    location.visit_notes = dest_location.visit_notes
                    
                else:
                    # Destination unknown/destroyed - note it
                    location.final_destination = moved_to_name
                    location.needs_verification = True
                    if verbose:
                        print(f"  → Destination {moved_to_name} status: {dest_location.status}")

        # Chain-follow related sites if they're significant historic locations
        if location.related_sites and _depth < _max_depth - 1:
            self._enrich_related_sites(location, verbose, _depth, _max_depth, _visited)

    def _enrich_related_sites(self, location: Location, verbose: bool,
                               _depth: int, _max_depth: int, _visited: set) -> None:
        """
        Chain-follow and enrich significant related sites discovered during location search.

        Only follows sites that are:
        - Historic houses, museums, churches, or cemeteries
        - Not already in our location database
        - Have a meaningful relationship to the original location
        """
        if not location.related_sites:
            return

        # Relationship types that indicate a site worth following
        significant_relationships = [
            'original location', 'sister church', 'founder also built', 'same founder',
            'related historic site', 'nearby historic site', 'memorial', 'museum',
            'historic home', 'burial site', 'meeting house', 'headquarters'
        ]

        for site_info in location.related_sites:
            if not isinstance(site_info, dict):
                continue

            site_name = site_info.get('name', '').strip()
            relationship = site_info.get('relationship', '').lower()

            if not site_name:
                continue

            # Check if this is a significant relationship worth following
            is_significant = any(sig in relationship for sig in significant_relationships)

            # Also check if the name suggests a historic location
            name_lower = site_name.lower()
            is_historic_type = any(t in name_lower for t in [
                'house', 'museum', 'church', 'meeting house', 'cemetery',
                'historic', 'memorial', 'monument', 'site'
            ])

            if not (is_significant or is_historic_type):
                continue

            # Generate ID to check if we already have this location
            related_id = self._generate_location_id(site_name, location.original_city, location.original_region)

            # Skip if already in our database or visited
            if related_id in self.locations or related_id in _visited:
                # But add a cross-reference
                if related_id in self.locations:
                    existing = self.locations[related_id]
                    if location.id not in [r.get('id') for r in existing.related_sites if isinstance(r, dict)]:
                        existing.related_sites.append({
                            'name': location.name,
                            'relationship': 'related to ' + relationship,
                            'note': f'Discovered from {location.name}'
                        })
                continue

            if verbose:
                print(f"  → Following related site: {site_name}")

            # Infer type from name
            related_type = self._infer_location_type(site_name, relationship)

            # Create new location for related site
            related_location = Location(
                id=related_id,
                name=site_name,
                type=related_type,
                original_name=site_name,
                original_city=location.original_city,
                original_region=location.original_region,
                original_country=location.original_country
            )

            # Add cross-reference back to original location
            related_location.related_sites.append({
                'name': location.name,
                'relationship': 'discovered from',
                'note': f'Related: {relationship}'
            })

            # Add to our locations database
            self.locations[related_id] = related_location

            # Recursively enrich (at increased depth)
            self._enrich_with_search(
                related_location, verbose, _depth + 1, _max_depth, _visited
            )

            # Geocode if needed
            if not related_location.coordinates and self.geocode_fn:
                self._geocode_location(related_location, verbose)

    def _synthesize_location(self, location: Location, search_results: str) -> dict:
        """Synthesize location data from search results."""
        prompt = f"""Analyze these search results about a historic location and extract ALL contextually relevant information.

LOCATION:
Name: {location.name}
Type: {location.type}
City: {location.original_city}
Region: {location.original_region}
Country: {location.original_country}

SEARCH RESULTS:
{search_results[:6000]}

Based on ONLY the search results above, provide a JSON response:

{{
    "status": "exists" or "destroyed" or "moved" or "rebuilt" or "private" or "unknown",
    "status_details": "Brief explanation of current status",
    
    "moved_to": {{
        "name": "Specific name of place THIS location's contents/remains were moved to",
        "city": "City if known",
        "region": "State/region if known", 
        "year": year moved or null,
        "details": "What was moved and why"
    }} or null (ONLY if this specific location was relocated somewhere else),
    
    "current_name": "Current name if location still exists but renamed, else null",
    "current_address": "Current street address if found, else null",
    "coordinates": [lat, lon] or null,
    
    "is_visitable": true/false,
    "visit_notes": "Hours, tours, access info, what to expect when visiting",
    
    "history": "2-4 sentence history of this place itself - founding, major events, significance",
    
    "notable_connections": [
        "Other famous people buried/married/connected here",
        "Important historical events that happened at this location",
        "Architectural or cultural significance",
        "Any surprising or compelling facts a visitor would want to know"
    ],
    
    "related_sites": [
        {{
            "name": "Name of related site",
            "relationship": "How it connects (e.g. 'original location', 'sister church', 'founder also built')",
            "note": "Why a visitor might care"
        }}
    ],
    
    "historic_events": [
        {{
            "year": year or null,
            "event": "What happened here"
        }}
    ],
    
    "visitor_tips": "Practical advice - best time to visit, what to look for, nearby parking, combined with other sites",
    
    "confidence": "low/medium/high based on how much info was found"
}}

IMPORTANT GUIDELINES:
1. For "moved_to": Only include if search results specifically say THIS location's contents were physically relocated. Don't include other locations that are merely mentioned nearby.

2. For "notable_connections": Include ANY compelling facts that make this location more interesting to visit. Famous people connected to it, historical events, architectural features, etc.

3. For "related_sites": Include sites that are meaningfully connected - not just geographically nearby, but historically or thematically linked. A visitor researching their ancestor here might also want to visit these.

4. For "history": Focus on what makes this place significant. Don't just say "it's a cemetery" - say what kind, when founded, notable features.

5. For "visitor_tips": Be practical. If it's a cemetery, mention if graves are hard to find. If it's a church, mention if tours are available.

Respond with ONLY valid JSON, no other text."""

        response = self.synthesize_fn(prompt)
        
        try:
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass
        
        return {}
    
    def _apply_location_synthesis(self, location: Location, synthesis: dict) -> None:
        """Apply synthesized data to location."""
        if not synthesis:
            return
        
        location.status = synthesis.get("status", "unknown")
        location.status_details = synthesis.get("status_details")
        location.moved_to = synthesis.get("moved_to")
        location.current_name = synthesis.get("current_name")
        location.current_address = synthesis.get("current_address")
        
        coords = synthesis.get("coordinates")
        if coords and isinstance(coords, list) and len(coords) == 2:
            location.coordinates = tuple(coords)
        
        location.is_visitable = synthesis.get("is_visitable", True)
        location.visit_notes = synthesis.get("visit_notes")
        location.visitor_tips = synthesis.get("visitor_tips")
        location.history = synthesis.get("history")
        location.historic_events = synthesis.get("historic_events", [])
        location.notable_connections = synthesis.get("notable_connections", [])
        location.related_sites = synthesis.get("related_sites", [])
        location.confidence = synthesis.get("confidence", "low")
    
    def _geocode_location(self, location: Location, verbose: bool = False) -> None:
        """Geocode a location using fallback strategies."""
        if not self.geocode_fn:
            return
        
        # Try strategies in order
        strategies = []
        
        # 1. Current address if we have it
        if location.current_address:
            strategies.append(location.current_address)
        
        # 2. Full name + city + region
        if location.name and location.original_city:
            strategies.append(f"{location.name}, {location.original_city}, {location.original_region or ''}")
        
        # 3. City + region + country
        if location.original_city:
            parts = [location.original_city]
            if location.original_region:
                parts.append(location.original_region)
            if location.original_country:
                parts.append(location.original_country)
            strategies.append(", ".join(parts))
        
        # 4. Just the name (for well-known places)
        if location.name:
            strategies.append(location.name)
        
        for strategy in strategies:
            if not strategy or not strategy.strip():
                continue
            
            if verbose:
                print(f"  Geocoding: {strategy[:50]}...")
            
            result = self.geocode_fn(strategy.strip())
            if result:
                location.coordinates = result
                if verbose:
                    print(f"  → ({result[0]:.6f}, {result[1]:.6f})")
                return
        
        # All strategies failed
        location.needs_verification = True
        if verbose:
            print(f"  → Geocoding failed")
    
    def get_locations_by_type(self, loc_type: str) -> list[Location]:
        """Get all locations of a specific type."""
        return [loc for loc in self.locations.values() if loc.type == loc_type]
    
    def get_locations_for_person(self, person_id: str) -> list[Location]:
        """Get all locations connected to a person."""
        result = []
        for loc in self.locations.values():
            for conn in loc.ancestor_connections:
                if conn.person_id == person_id:
                    result.append(loc)
                    break
        return result
    
    def get_locations_by_region(self, region: str) -> list[Location]:
        """Get all locations in a region (for trip planning)."""
        region_lower = region.lower()
        return [
            loc for loc in self.locations.values()
            if region_lower in (loc.original_region or "").lower()
            or region_lower in (loc.original_country or "").lower()
            or region_lower in (loc.original_city or "").lower()
        ]
    
    def get_shared_locations(self, min_ancestors: int = 2) -> list[Location]:
        """Get locations with multiple ancestor connections."""
        return [
            loc for loc in self.locations.values()
            if len(loc.ancestor_connections) >= min_ancestors
        ]
    
    def to_dict(self) -> dict:
        """Export all locations as dict."""
        return {
            "locations": {loc_id: loc.to_dict() for loc_id, loc in self.locations.items()},
            "stats": {
                "total_locations": len(self.locations),
                "by_type": self._count_by_type(),
                "by_status": self._count_by_status(),
                "with_coordinates": sum(1 for loc in self.locations.values() if loc.coordinates),
                "needs_verification": sum(1 for loc in self.locations.values() if loc.needs_verification),
                "shared_locations": len(self.get_shared_locations(2))
            }
        }
    
    def _count_by_type(self) -> dict:
        """Count locations by type."""
        counts = defaultdict(int)
        for loc in self.locations.values():
            counts[loc.type] += 1
        return dict(counts)
    
    def _count_by_status(self) -> dict:
        """Count locations by status."""
        counts = defaultdict(int)
        for loc in self.locations.values():
            counts[loc.status] += 1
        return dict(counts)
    
    def to_geojson(self) -> dict:
        """Export locations as GeoJSON for mapping."""
        features = []
        
        for loc in self.locations.values():
            if not loc.coordinates:
                continue
            
            # Build popup content
            connections_text = "\n".join([
                f"• {c.person_name} ({c.relationship.replace('_', ' ')}, {c.year or 'date unknown'})"
                for c in loc.ancestor_connections
            ])
            
            feature = {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [loc.coordinates[1], loc.coordinates[0]]  # GeoJSON is [lon, lat]
                },
                "properties": {
                    "id": loc.id,
                    "name": loc.current_name or loc.name,
                    "type": loc.type,
                    "status": loc.status,
                    "is_visitable": loc.is_visitable,
                    "visit_notes": loc.visit_notes,
                    "history": loc.history,
                    "ancestor_count": len(loc.ancestor_connections),
                    "ancestors": connections_text,
                    "address": loc.current_address
                }
            }
            features.append(feature)
        
        return {
            "type": "FeatureCollection",
            "features": features
        }


def create_nominatim_geocoder(user_agent: str = "where-they-walked"):
    """Create a geocoding function using Nominatim (free, 1 req/sec)."""
    from geopy.geocoders import Nominatim
    from geopy.exc import GeocoderTimedOut, GeocoderUnavailable
    import time
    
    geolocator = Nominatim(user_agent=user_agent)
    last_request_time = [0]  # Mutable for closure
    
    def geocode(address: str) -> Optional[tuple]:
        # Rate limit: 1 request per second
        elapsed = time.time() - last_request_time[0]
        if elapsed < 1.1:
            time.sleep(1.1 - elapsed)
        
        last_request_time[0] = time.time()
        
        try:
            result = geolocator.geocode(address, timeout=10)
            if result:
                return (result.latitude, result.longitude)
        except (GeocoderTimedOut, GeocoderUnavailable):
            pass
        
        return None
    
    return geocode
