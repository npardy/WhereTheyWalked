"""
Historic Events Processing for Where They Walked

Handles historic events as first-class entities:
- Extract events from research results
- Deduplicate across ancestors
- Enrich each event with dedicated search
- Link ancestors to events with their specific connections
"""

import json
import re
import hashlib
from dataclasses import dataclass, field
from typing import Optional, Callable


@dataclass
class AncestorEventConnection:
    """Connection between an ancestor and a historic event."""
    person_id: str
    person_name: str
    connection_type: str  # participant, witness, victim, activist, soldier, etc.
    connection_details: str  # Specific description of their involvement
    year: Optional[int] = None

    def to_dict(self) -> dict:
        return {
            "person_id": self.person_id,
            "person_name": self.person_name,
            "connection_type": self.connection_type,
            "connection_details": self.connection_details,
            "year": self.year
        }


@dataclass
class HistoricEvent:
    """A historic event that ancestors may be connected to."""
    id: str
    name: str
    event_type: str  # war, trial, migration, religious_movement, political, disaster, etc.

    # Time information
    year: Optional[int] = None
    end_year: Optional[int] = None
    date_range: Optional[str] = None

    # Location
    location: Optional[str] = None
    region: Optional[str] = None
    country: Optional[str] = None

    # Description
    short_description: Optional[str] = None
    full_description: Optional[str] = None
    historical_significance: Optional[str] = None

    # Connections
    ancestor_connections: list = field(default_factory=list)
    related_events: list = field(default_factory=list)  # IDs of related events
    related_locations: list = field(default_factory=list)  # Location IDs

    # Notable people
    notable_figures: list = field(default_factory=list)  # Famous people involved

    # Sources
    source_urls: list = field(default_factory=list)

    # Status
    is_enriched: bool = False

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "event_type": self.event_type,
            "year": self.year,
            "end_year": self.end_year,
            "date_range": self.date_range or (f"{self.year}-{self.end_year}" if self.year and self.end_year else str(self.year) if self.year else None),
            "location": self.location,
            "region": self.region,
            "country": self.country,
            "short_description": self.short_description,
            "full_description": self.full_description,
            "historical_significance": self.historical_significance,
            "ancestor_connections": [c.to_dict() if hasattr(c, 'to_dict') else c for c in self.ancestor_connections],
            "ancestor_count": len(self.ancestor_connections),
            "related_events": self.related_events,
            "related_locations": self.related_locations,
            "notable_figures": self.notable_figures,
            "source_urls": self.source_urls,
            "is_enriched": self.is_enriched
        }


class EventProcessor:
    """
    Process and enrich historic events from ancestor research.

    Similar to LocationProcessor but for events:
    1. Extract events from all research results
    2. Deduplicate by name/date
    3. Enrich each event with dedicated search
    4. Link all connected ancestors
    """

    # Well-known events for better matching
    KNOWN_EVENTS = {
        "flushing remonstrance": {
            "name": "Flushing Remonstrance",
            "year": 1657,
            "event_type": "political",
            "location": "Flushing, New York",
            "significance": "First document in American history demanding religious freedom"
        },
        "salem witch trials": {
            "name": "Salem Witch Trials",
            "year": 1692,
            "end_year": 1693,
            "event_type": "trial",
            "location": "Salem, Massachusetts",
            "significance": "Colonial American witch hunt that executed 20 people"
        },
        "mayflower": {
            "name": "Mayflower Voyage",
            "year": 1620,
            "event_type": "migration",
            "location": "Plymouth, Massachusetts",
            "significance": "Pilgrims' voyage establishing Plymouth Colony"
        },
        "american revolution": {
            "name": "American Revolutionary War",
            "year": 1775,
            "end_year": 1783,
            "event_type": "war",
            "location": "American Colonies",
            "significance": "War for American independence from Britain"
        },
        "civil war": {
            "name": "American Civil War",
            "year": 1861,
            "end_year": 1865,
            "event_type": "war",
            "location": "United States",
            "significance": "War between Union and Confederate states"
        },
        "king philip": {
            "name": "King Philip's War",
            "year": 1675,
            "end_year": 1678,
            "event_type": "war",
            "location": "New England",
            "significance": "Conflict between Native Americans and colonists"
        }
    }

    def __init__(self, search_fn: Callable = None, synthesize_fn: Callable = None):
        self.search_fn = search_fn
        self.synthesize_fn = synthesize_fn
        self.events: dict[str, HistoricEvent] = {}

    def _generate_event_id(self, name: str, year: Optional[int] = None) -> str:
        """Generate a unique ID for an event."""
        key = f"{name.lower()}|{year or ''}"
        return hashlib.md5(key.encode()).hexdigest()[:12]

    def _normalize_event_name(self, name: str) -> str:
        """Normalize event name for matching."""
        return re.sub(r'[^a-z0-9\s]', '', name.lower()).strip()

    def _match_known_event(self, name: str) -> Optional[dict]:
        """Check if event matches a well-known event."""
        normalized = self._normalize_event_name(name)
        for key, info in self.KNOWN_EVENTS.items():
            if key in normalized or normalized in key:
                return info
        return None

    def extract_events_from_research(self, research_results: list) -> dict:
        """
        Extract all historic events from research results.

        Args:
            research_results: List of ResearchResult objects

        Returns:
            Dict of event_id -> HistoricEvent
        """
        for result in research_results:
            # Get events from the research result
            events_data = getattr(result, 'historic_events', []) or []

            for evt in events_data:
                if isinstance(evt, dict):
                    name = evt.get('name', '')
                    if not name:
                        continue

                    year = evt.get('year')
                    event_id = self._generate_event_id(name, year)

                    # Check if we already have this event
                    if event_id in self.events:
                        # Add this ancestor as a connection
                        self._add_ancestor_connection(
                            event_id, result, evt.get('connection', '')
                        )
                    else:
                        # Create new event
                        known = self._match_known_event(name)

                        event = HistoricEvent(
                            id=event_id,
                            name=known['name'] if known else name,
                            event_type=known.get('event_type', evt.get('type', 'other')) if known else evt.get('type', 'other'),
                            year=known.get('year', year) if known else year,
                            end_year=known.get('end_year') if known else evt.get('end_year'),
                            date_range=evt.get('date_range'),
                            location=known.get('location') if known else evt.get('location'),
                            short_description=evt.get('description'),
                            historical_significance=known.get('significance') if known else None
                        )

                        # Add the ancestor connection
                        connection = AncestorEventConnection(
                            person_id=result.individual_id,
                            person_name=result.full_name,
                            connection_type=self._infer_connection_type(evt.get('connection', '')),
                            connection_details=evt.get('connection', ''),
                            year=year
                        )
                        event.ancestor_connections.append(connection)

                        self.events[event_id] = event

        return self.events

    def _add_ancestor_connection(self, event_id: str, result, connection_details: str):
        """Add an ancestor connection to an existing event."""
        event = self.events.get(event_id)
        if not event:
            return

        # Check if this ancestor is already connected
        existing_ids = [c.person_id for c in event.ancestor_connections]
        if result.individual_id in existing_ids:
            return

        connection = AncestorEventConnection(
            person_id=result.individual_id,
            person_name=result.full_name,
            connection_type=self._infer_connection_type(connection_details),
            connection_details=connection_details
        )
        event.ancestor_connections.append(connection)

    def _infer_connection_type(self, details: str) -> str:
        """Infer the type of connection from details text."""
        details_lower = details.lower()

        if any(w in details_lower for w in ['fought', 'soldier', 'military', 'served', 'battle']):
            return 'soldier'
        if any(w in details_lower for w in ['victim', 'accused', 'executed', 'died']):
            return 'victim'
        if any(w in details_lower for w in ['witness', 'testified', 'saw']):
            return 'witness'
        if any(w in details_lower for w in ['signed', 'wrote', 'authored', 'advocated']):
            return 'activist'
        if any(w in details_lower for w in ['led', 'commanded', 'organized']):
            return 'leader'
        if any(w in details_lower for w in ['survived', 'escaped', 'fled']):
            return 'survivor'
        if any(w in details_lower for w in ['born during', 'lived through']):
            return 'contemporary'

        return 'participant'

    def enrich_events(self, verbose: bool = False) -> dict:
        """
        Enrich all events with dedicated searches.

        Returns:
            Stats about enrichment
        """
        if not self.search_fn or not self.synthesize_fn:
            return {"error": "Search and synthesize functions required"}

        stats = {
            "total_events": len(self.events),
            "enriched": 0,
            "by_type": {}
        }

        for event_id, event in self.events.items():
            if event.is_enriched:
                continue

            if verbose:
                print(f"  Enriching event: {event.name}")

            try:
                self._enrich_single_event(event, verbose)
                event.is_enriched = True
                stats["enriched"] += 1

                # Track by type
                etype = event.event_type
                stats["by_type"][etype] = stats["by_type"].get(etype, 0) + 1

            except Exception as e:
                if verbose:
                    print(f"    Error enriching {event.name}: {e}")

        return stats

    def _enrich_single_event(self, event: HistoricEvent, verbose: bool = False):
        """Enrich a single event with search and synthesis."""
        # Build search query
        query_parts = [f'"{event.name}"']
        if event.year:
            query_parts.append(str(event.year))
        if event.location:
            query_parts.append(event.location)
        query_parts.append("history significance")

        query = " ".join(query_parts)

        if verbose:
            print(f"    Searching: {query}")

        # Search
        search_results = self.search_fn(query)

        # Extract URLs for sources
        url_pattern = r'URL: (https?://[^\s]+)'
        urls = re.findall(url_pattern, search_results)
        event.source_urls = urls[:5]

        # Synthesize
        prompt = f"""Analyze these search results about a historic event and extract detailed information.

EVENT: {event.name}
KNOWN DATE: {event.date_range or event.year or 'Unknown'}
KNOWN LOCATION: {event.location or 'Unknown'}

SEARCH RESULTS:
{search_results[:12000]}

Provide a JSON response with enriched event information:

{{
    "full_description": "Detailed 100-200 word description of the event, what happened, and why it matters",
    "historical_significance": "Why this event is historically important (50-100 words)",
    "year": exact start year or null,
    "end_year": exact end year or null (for multi-year events),
    "location": "Primary location",
    "region": "Region/state/province",
    "country": "Country",
    "event_type": "war/trial/migration/religious_movement/political/disaster/economic/social",
    "notable_figures": ["List of famous people involved"],
    "related_events": ["Names of related historical events"],
    "key_facts": ["3-5 key facts about this event"]
}}

Respond with ONLY valid JSON."""

        response = self.synthesize_fn(prompt)

        try:
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                data = json.loads(json_match.group())

                # Apply enriched data
                if data.get('full_description'):
                    event.full_description = data['full_description']
                if data.get('historical_significance'):
                    event.historical_significance = data['historical_significance']
                if data.get('year'):
                    event.year = data['year']
                if data.get('end_year'):
                    event.end_year = data['end_year']
                if data.get('location'):
                    event.location = data['location']
                if data.get('region'):
                    event.region = data['region']
                if data.get('country'):
                    event.country = data['country']
                if data.get('event_type'):
                    event.event_type = data['event_type']
                if data.get('notable_figures'):
                    event.notable_figures = data['notable_figures']
                if data.get('related_events'):
                    event.related_events = data['related_events']

        except json.JSONDecodeError:
            pass

    def get_events_for_ancestor(self, person_id: str) -> list[HistoricEvent]:
        """Get all events connected to a specific ancestor."""
        return [
            event for event in self.events.values()
            if any(c.person_id == person_id for c in event.ancestor_connections)
        ]

    def get_shared_events(self, min_ancestors: int = 2) -> list[HistoricEvent]:
        """Get events connected to multiple ancestors."""
        return [
            event for event in self.events.values()
            if len(event.ancestor_connections) >= min_ancestors
        ]

    def get_events_by_type(self, event_type: str) -> list[HistoricEvent]:
        """Get all events of a specific type."""
        return [
            event for event in self.events.values()
            if event.event_type == event_type
        ]

    def to_dict(self) -> dict:
        """Export all events as a dictionary."""
        return {
            "events": {eid: e.to_dict() for eid, e in self.events.items()},
            "stats": {
                "total_events": len(self.events),
                "by_type": {},
                "enriched": sum(1 for e in self.events.values() if e.is_enriched),
                "shared_events": len(self.get_shared_events())
            }
        }
