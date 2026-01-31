"""Where They Walked - Transform GEDCOM files into enriched family history."""

from .gedcom_parser import GedcomParser, Individual, Family
from .researcher import AncestorResearcher, ResearchResult, TimelineValidator
from .locations import LocationProcessor, Location, AncestorConnection, create_nominatim_geocoder
from .main import WhereTheyWalked

__version__ = "0.1.0"
__all__ = [
    "GedcomParser",
    "Individual", 
    "Family",
    "AncestorResearcher",
    "ResearchResult",
    "TimelineValidator",
    "LocationProcessor",
    "Location",
    "AncestorConnection",
    "create_nominatim_geocoder",
    "WhereTheyWalked"
]
