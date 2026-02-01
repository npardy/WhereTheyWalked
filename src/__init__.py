"""Where They Walked - Transform GEDCOM files into enriched family history."""

# Load environment variables from .env file
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root (parent of src/)
_project_root = Path(__file__).parent.parent
_env_file = _project_root / ".env"
if _env_file.exists():
    load_dotenv(_env_file)

from .gedcom_parser import GedcomParser, Individual, Family
from .researcher import (
    AncestorResearcher,
    ResearchResult,
    TimelineValidator,
    TokenTracker,
    create_anthropic_synthesizer,
    get_token_tracker
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
    "create_anthropic_synthesizer",
    # Token tracking
    "TokenTracker",
    "get_token_tracker"
]
