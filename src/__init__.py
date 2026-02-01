"""Where They Walked - Transform GEDCOM files into enriched family history."""

from .gedcom_parser import GedcomParser, Individual, Family
from .researcher import (
    AncestorResearcher,
    ResearchResult,
    TimelineValidator,
    create_anthropic_synthesizer
)
from .locations import LocationProcessor, Location, AncestorConnection, create_nominatim_geocoder
from .events import EventProcessor, HistoricEvent, AncestorEventConnection
from .search import (
    create_serpapi_search,
    create_brave_search,
    create_auto_search,
    create_mock_search,
    get_available_providers,
    SearchError
)
from .main import WhereTheyWalked, create_app, get_api_status

__version__ = "0.1.0"
__all__ = [
    # Core classes
    "GedcomParser",
    "Individual",
    "Family",
    "AncestorResearcher",
    "ResearchResult",
    "TimelineValidator",
    "LocationProcessor",
    "Location",
    "AncestorConnection",
    "EventProcessor",
    "HistoricEvent",
    "AncestorEventConnection",
    # Main app
    "WhereTheyWalked",
    "create_app",
    "get_api_status",
    # Search providers
    "create_serpapi_search",
    "create_brave_search",
    "create_auto_search",
    "create_mock_search",
    "get_available_providers",
    "SearchError",
    # Other utilities
    "create_nominatim_geocoder",
    "create_anthropic_synthesizer"
]
