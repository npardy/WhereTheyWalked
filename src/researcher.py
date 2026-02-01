"""
Ancestor Research Pipeline for Where They Walked
Searches for information about individuals and synthesizes biographical summaries.
Includes timeline validation against family relationships.
"""

import json
import time
import re
import os
from dataclasses import dataclass, field
from typing import Optional, Callable
from pathlib import Path


@dataclass
class TimelineValidation:
    """Results of validating discovered dates against family timeline."""
    is_valid: bool = True
    conflicts: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    
    # Expected ranges based on family
    expected_birth_min: Optional[int] = None
    expected_birth_max: Optional[int] = None
    expected_death_min: Optional[int] = None
    expected_death_max: Optional[int] = None
    
    def to_dict(self):
        return {
            "is_valid": self.is_valid,
            "conflicts": self.conflicts,
            "warnings": self.warnings,
            "expected_birth_range": [self.expected_birth_min, self.expected_birth_max] 
                if self.expected_birth_min else None,
            "expected_death_range": [self.expected_death_min, self.expected_death_max]
                if self.expected_death_min else None
        }


@dataclass
class ResearchResult:
    """Research results for an individual."""
    individual_id: str
    full_name: str
    
    # Original data from GEDCOM
    birth_year: Optional[int] = None
    death_year: Optional[int] = None
    birth_place: Optional[str] = None
    death_place: Optional[str] = None
    search_query: str = ""
    
    # Discovered data from search
    birth_year_discovered: Optional[int] = None
    death_year_discovered: Optional[int] = None
    birth_place_discovered: Optional[str] = None
    death_place_discovered: Optional[str] = None
    discovered_from: Optional[str] = None  # Source of discovered data
    
    # Raw search results
    raw_search_results: str = ""
    source_urls: list[str] = field(default_factory=list)
    
    # Synthesized content
    biography: Optional[str] = None
    biography_short: Optional[str] = None
    notable: bool = False
    notable_reason: Optional[str] = None
    confidence: str = "low"  # low, medium, high
    
    # Extracted data
    locations: list = field(default_factory=list)
    historic_events: list = field(default_factory=list)
    occupation: Optional[str] = None
    migration_path: list = field(default_factory=list)  # List of {place, year_arrived, year_left, reason, location_type}
    
    # Notable family connections (e.g., stepfather = John Winthrop)
    notable_relatives: list = field(default_factory=list)  # [{name, relationship, why_notable}]

    # Flags
    has_museum: bool = False
    has_cemetery: bool = False
    has_historic_site: bool = False
    pioneer_settler: bool = False  # Mayflower, First Fleet, Voortrekkers, etc.
    military_service: bool = False
    noble_or_royal: bool = False
    immigrant_pioneer: bool = False

    # Validation
    needs_confirmation: bool = False
    confirmation_reason: Optional[str] = None
    timeline_validation: Optional[TimelineValidation] = None
    
    def to_dict(self):
        return {
            "individual_id": self.individual_id,
            "full_name": self.full_name,
            "birth_year": self.birth_year,
            "death_year": self.death_year,
            "birth_place": self.birth_place,
            "death_place": self.death_place,
            "birth_year_discovered": self.birth_year_discovered,
            "death_year_discovered": self.death_year_discovered,
            "birth_place_discovered": self.birth_place_discovered,
            "death_place_discovered": self.death_place_discovered,
            "discovered_from": self.discovered_from,
            "search_query": self.search_query,
            "biography": self.biography,
            "biography_short": self.biography_short,
            "notable": self.notable,
            "notable_reason": self.notable_reason,
            "confidence": self.confidence,
            "locations": self.locations,
            "historic_events": self.historic_events,
            "occupation": self.occupation,
            "migration_path": self.migration_path,
            "notable_relatives": self.notable_relatives,
            "has_museum": self.has_museum,
            "has_cemetery": self.has_cemetery,
            "has_historic_site": self.has_historic_site,
            "pioneer_settler": self.pioneer_settler,
            "military_service": self.military_service,
            "noble_or_royal": self.noble_or_royal,
            "immigrant_pioneer": self.immigrant_pioneer,
            "needs_confirmation": self.needs_confirmation,
            "confirmation_reason": self.confirmation_reason,
            "timeline_validation": self.timeline_validation.to_dict() if self.timeline_validation else None,
            "source_urls": self.source_urls
        }


class TimelineValidator:
    """Validates discovered dates against family relationships."""
    
    # Reasonable ranges
    MIN_PARENT_AGE = 15  # Minimum age to have a child
    MAX_PARENT_AGE = 55  # Maximum age to have a child (generous for historical data)
    MAX_SPOUSE_AGE_DIFF = 25  # Maximum age difference between spouses
    MAX_LIFESPAN = 110  # Maximum reasonable lifespan
    MIN_MARRIAGE_AGE = 12  # Historical marriages could be young
    
    def validate(self, individual, birth_discovered: int = None, death_discovered: int = None) -> TimelineValidation:
        """
        Validate discovered dates against family timeline.
        
        Args:
            individual: Individual object with family relationships populated
            birth_discovered: Discovered birth year from search
            death_discovered: Discovered death year from search
            
        Returns:
            TimelineValidation with results
        """
        validation = TimelineValidation()
        
        # Calculate expected ranges from family
        self._calculate_expected_ranges(individual, validation)
        
        # If we have discovered dates, validate them
        if birth_discovered:
            self._validate_birth(birth_discovered, validation, individual)
        
        if death_discovered:
            self._validate_death(death_discovered, birth_discovered, validation, individual)
        
        # Check birth before death
        if birth_discovered and death_discovered:
            if death_discovered < birth_discovered:
                validation.is_valid = False
                validation.conflicts.append(
                    f"Death year ({death_discovered}) is before birth year ({birth_discovered})"
                )
            elif death_discovered - birth_discovered > self.MAX_LIFESPAN:
                validation.is_valid = False
                validation.conflicts.append(
                    f"Lifespan of {death_discovered - birth_discovered} years exceeds maximum reasonable age"
                )
        
        return validation
    
    def _calculate_expected_ranges(self, individual, validation: TimelineValidation):
        """Calculate expected birth/death year ranges from family."""
        birth_mins = []
        birth_maxs = []
        
        # From father's birth year
        if individual._father and individual._father.birth_year:
            father_birth = individual._father.birth_year
            birth_mins.append(father_birth + self.MIN_PARENT_AGE)
            birth_maxs.append(father_birth + self.MAX_PARENT_AGE)
        
        # From mother's birth year
        if individual._mother and individual._mother.birth_year:
            mother_birth = individual._mother.birth_year
            birth_mins.append(mother_birth + self.MIN_PARENT_AGE)
            birth_maxs.append(mother_birth + self.MAX_PARENT_AGE)
        
        # From spouse's birth year
        for spouse in individual._spouses:
            if spouse.birth_year:
                birth_mins.append(spouse.birth_year - self.MAX_SPOUSE_AGE_DIFF)
                birth_maxs.append(spouse.birth_year + self.MAX_SPOUSE_AGE_DIFF)
        
        # From children's birth years (must be born before children)
        child_births = [c.birth_year for c in individual._children if c.birth_year]
        if child_births:
            earliest_child = min(child_births)
            birth_maxs.append(earliest_child - self.MIN_PARENT_AGE)
            # Also: must not die before children are born (usually)
            validation.expected_death_min = earliest_child - 1  # Could die during pregnancy
        
        # Set expected ranges
        if birth_mins:
            validation.expected_birth_min = max(birth_mins)
        if birth_maxs:
            validation.expected_birth_max = min(birth_maxs)
    
    def _validate_birth(self, birth: int, validation: TimelineValidation, individual):
        """Validate birth year against expected range."""
        if validation.expected_birth_min and birth < validation.expected_birth_min:
            validation.is_valid = False
            validation.conflicts.append(
                f"Birth year {birth} is too early (expected after {validation.expected_birth_min} based on parents)"
            )
        
        if validation.expected_birth_max and birth > validation.expected_birth_max:
            validation.is_valid = False
            validation.conflicts.append(
                f"Birth year {birth} is too late (expected before {validation.expected_birth_max} based on children/family)"
            )
        
        # Check against spouse
        for spouse in individual._spouses:
            if spouse.birth_year:
                diff = abs(birth - spouse.birth_year)
                if diff > self.MAX_SPOUSE_AGE_DIFF:
                    validation.warnings.append(
                        f"Large age difference with spouse {spouse.full_name}: {diff} years"
                    )
    
    def _validate_death(self, death: int, birth: int, validation: TimelineValidation, individual):
        """Validate death year."""
        # Must not die before children are born (with some allowance)
        child_births = [c.birth_year for c in individual._children if c.birth_year]
        if child_births:
            latest_child = max(child_births)
            if death < latest_child:
                # This could be valid (died before child born, posthumous birth)
                # but flag as warning
                validation.warnings.append(
                    f"Died ({death}) before child born ({latest_child}) - verify if correct"
                )
        
        # Check lifespan is reasonable
        if birth:
            lifespan = death - birth
            if lifespan < 0:
                validation.is_valid = False
                validation.conflicts.append(f"Negative lifespan: died before born")
            elif lifespan > self.MAX_LIFESPAN:
                validation.is_valid = False
                validation.conflicts.append(f"Unreasonable lifespan: {lifespan} years")


class AncestorResearcher:
    """Research ancestors using web search and AI synthesis."""
    
    def __init__(self, search_fn: Callable = None, synthesize_fn: Callable = None):
        """
        Initialize researcher.
        
        Args:
            search_fn: Function that takes a query string and returns search results text
            synthesize_fn: Function that takes a prompt and returns AI response
        """
        self.search_fn = search_fn
        self.synthesize_fn = synthesize_fn
        self.validator = TimelineValidator()
    
    def research_individual(self, individual: dict, individual_obj=None, verbose: bool = False) -> ResearchResult:
        """
        Research a single individual.
        
        Args:
            individual: Dict with individual data from GEDCOM parser
            individual_obj: Optional Individual object (for family relationships)
            verbose: Print progress
            
        Returns:
            ResearchResult with all findings
        """
        result = ResearchResult(
            individual_id=individual["id"],
            full_name=individual["full_name"],
            birth_year=individual.get("birth_year"),
            death_year=individual.get("death_year"),
            birth_place=individual.get("birth_place"),
            death_place=individual.get("death_place"),
            search_query=individual.get("search_query", ""),
            needs_confirmation=individual.get("needs_confirmation", False)
        )
        
        # Track if we were missing dates initially
        was_missing_dates = not result.birth_year and not result.death_year
        
        if individual.get("needs_confirmation"):
            result.confirmation_reason = "No dates in source data, searched using family context"
        
        if verbose:
            print(f"Researching: {result.full_name} ({result.birth_year or '?'}-{result.death_year or '?'})")
        
        # Step 1: First search for information
        if self.search_fn:
            search_results = self.search_fn(result.search_query)
            result.raw_search_results = search_results
            
            # Extract URLs from search results if present
            urls = re.findall(r'https?://[^\s\])<>"]+', search_results)
            result.source_urls = list(set(urls))[:10]
        
        # Step 2: Synthesize biography and extract data (including dates)
        if self.synthesize_fn and result.raw_search_results:
            synthesis = self._synthesize_research(result)
            self._apply_synthesis(result, synthesis)
        
        # Step 3: Validate discovered dates against family timeline
        if individual_obj and (result.birth_year_discovered or result.death_year_discovered):
            validation = self.validator.validate(
                individual_obj,
                birth_discovered=result.birth_year_discovered,
                death_discovered=result.death_year_discovered
            )
            result.timeline_validation = validation
            
            if not validation.is_valid:
                result.needs_confirmation = True
                result.confirmation_reason = f"Timeline conflicts: {'; '.join(validation.conflicts)}"
            elif validation.warnings:
                result.needs_confirmation = True
                result.confirmation_reason = f"Timeline warnings: {'; '.join(validation.warnings)}"
        
        # Step 4: TWO-PASS SEARCH - If we were missing dates and found valid ones, re-search
        if was_missing_dates and self.search_fn and self.synthesize_fn:
            # Check if we found valid dates
            dates_valid = True
            if result.timeline_validation and not result.timeline_validation.is_valid:
                dates_valid = False
            
            if dates_valid and (result.birth_year_discovered or result.death_year_discovered):
                # Build a better query with discovered dates
                refined_query = self._build_refined_query(result)
                
                if verbose:
                    print(f"  Re-searching with dates: {refined_query}")
                
                # Second search with actual dates
                refined_results = self.search_fn(refined_query)
                
                # Only use refined results if we got something back
                if refined_results and len(refined_results) > 100:
                    result.raw_search_results = refined_results
                    result.search_query = refined_query  # Update to show refined query
                    
                    # Extract new URLs
                    urls = re.findall(r'https?://[^\s\])<>"]+', refined_results)
                    result.source_urls = list(set(urls))[:10]
                    
                    # Re-synthesize with better results
                    synthesis = self._synthesize_research(result)
                    self._apply_synthesis(result, synthesis)
        
        return result
    
    def _build_refined_query(self, result: ResearchResult) -> str:
        """Build a refined search query using discovered dates."""
        parts = [f'"{result.full_name}"']
        
        # Use discovered dates if available, fall back to original
        birth = result.birth_year_discovered or result.birth_year
        death = result.death_year_discovered or result.death_year
        
        if birth:
            parts.append(str(birth))
        if death:
            parts.append(str(death))
        
        # Add location
        place = result.birth_place_discovered or result.birth_place or \
                result.death_place_discovered or result.death_place
        if place:
            place_parts = [p.strip() for p in place.split(",")]
            if len(place_parts) >= 2:
                parts.append(place_parts[0])  # Town/city
                # Add region/state
                if len(place_parts) > 2:
                    parts.append(place_parts[-2])
        
        return " ".join(parts)
    
    def _synthesize_research(self, result: ResearchResult) -> dict:
        """Use AI to synthesize search results into structured data."""

        prompt = f"""Analyze these search results about an ancestor and extract ALL available structured information.
Be thorough - extract every mention of historic events, notable people, and significant facts.

ANCESTOR:
Name: {result.full_name}
Birth: {result.birth_year or 'Unknown'} in {result.birth_place or 'Unknown'}
Death: {result.death_year or 'Unknown'} in {result.death_place or 'Unknown'}

SEARCH RESULTS:
{result.raw_search_results[:20000]}

Based on ONLY the search results above (do not make up information), provide a comprehensive JSON response.

CRITICAL INSTRUCTIONS:
1. Extract ALL historic events mentioned, even indirectly (wars, trials, migrations, political movements)
2. Extract ALL notable relatives or connections to famous people (parents, stepparents, spouses, in-laws)
3. Look for contributions to history (religious freedom, founding documents, military service)
4. Identify specific roles they played (signed documents, advocated for causes, testified at trials)
5. NORMALIZE ALL PLACE NAMES to consistent format: "City, State/Province (full name), Country"
   - Use full state/province names (Massachusetts, not MA; Ontario, not ON)
   - Always include country
   - Examples: "Chatham, Massachusetts, USA" not "Chatham, Barnstable, MA"
   - Examples: "London, England, UK" not "London"

{{
    "birth_year_discovered": year or null,
    "death_year_discovered": year or null,
    "birth_place_discovered": "City, State/Province, Country" or null,
    "death_place_discovered": "City, State/Province, Country" or null,
    "discovered_from": "source URL" or null,

    "biography": "200-400 word detailed biographical summary. Include ALL specific facts: roles, achievements, family connections, historical involvement. Be comprehensive.",
    "biography_short": "2-3 sentence summary highlighting their most significant contribution or connection.",

    "notable": true/false (mark true if: connected to famous people, involved in historic events, mentioned in history books, has museum/memorial, signed historic documents, or played any significant role in local/national/world history),
    "notable_reason": "Specific explanation: what they did, who they knew, why they matter",

    "confidence": "low/medium/high",
    "occupation": "occupation if mentioned",

    "migration_path": [
        {{
            "place": "City, State/Province, Country (normalized format)",
            "year_arrived": year or null,
            "year_left": year or null,
            "reason": "Why they moved here or left (immigration, religious freedom, land, marriage, death, etc.)",
            "location_type": "origin/immigration_port/settlement/residence/final_residence"
        }}
    ],

    "notable_relatives": [
        {{
            "name": "Full name of notable relative",
            "relationship": "father/mother/stepfather/spouse/father-in-law/etc",
            "why_notable": "Why this person is historically significant (Governor, signer, founder, etc.)"
        }}
    ],

    "historic_events": [
        {{
            "name": "Official name of event (e.g., 'Salem Witch Trials', 'Irish Famine', 'Thirty Years War', 'French Revolution')",
            "year": start year,
            "end_year": end year if multi-year event,
            "date_range": "e.g., 1657" or "1692-1693",
            "event_type": "political/religious/war/trial/migration/economic/natural_disaster/epidemic",
            "description": "What the event was about",
            "ancestor_role": "What specifically this ancestor did (signed, advocated, fought, testified, etc.)",
            "connection_type": "participant/leader/victim/witness/survivor/signatory/advocate/military/bystander (how they were connected)",
            "historical_significance": "Why this event matters in history"
        }}
    ],

    "locations": [
        {{
            "name": "Specific place name (e.g., 'Old First Church', 'Nickerson Cemetery')",
            "normalized_place": "City, State/Province, Country (e.g., 'Chatham, Massachusetts, USA')",
            "type": "birthplace/deathplace/burial_site/cemetery/church/meeting_house/museum/historic_house/historic_site/memorial/settlement/colony/port/courthouse/battlefield/farm/mill/trading_post/immigration_point/residence/other",
            "address": "Street address if found",
            "description": "Why this location is significant to this ancestor",
            "year": year associated with this location or null,
            "importance": "high/medium/low (high = museum, memorial, major historic site; medium = documented location with history; low = just a residence or town)",
            "should_enrich": true/false (true if this location has historical significance worth researching further)
        }}
    ],

    "contributions": [
        "List of specific contributions to history (e.g., 'Advocated for religious freedom', 'Served in local government', 'Founded a business/church/school')"
    ],

    "flags": {{
        "has_museum": true/false,
        "has_cemetery": true/false,
        "has_historic_site": true/false,
        "pioneer_settler": true/false (early settler, colonist, or founding migration - e.g., Mayflower, First Fleet to Australia, Voortrekkers, etc.),
        "military_service": true/false,
        "signed_historic_document": true/false,
        "founded_settlement": true/false,
        "religious_leader": true/false,
        "political_figure": true/false,
        "noble_or_royal": true/false (any aristocratic, noble, or royal lineage),
        "immigrant_pioneer": true/false (significant immigration story)
    }}
}}

IMPORTANT: Be thorough! Extract any historical significance - wars, migrations, religious persecution, revolutions, famines, colonial events, noble lineages, or connections to famous events or people. This works for ancestors from ANY country.

Respond with ONLY valid JSON."""

        response = self.synthesize_fn(prompt)
        
        # Parse JSON from response
        try:
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass
        
        return {}
    
    def _apply_synthesis(self, result: ResearchResult, synthesis: dict):
        """Apply synthesized data to result object."""
        if not synthesis:
            return
        
        # Discovered dates
        result.birth_year_discovered = synthesis.get("birth_year_discovered")
        result.death_year_discovered = synthesis.get("death_year_discovered")
        result.birth_place_discovered = synthesis.get("birth_place_discovered")
        result.death_place_discovered = synthesis.get("death_place_discovered")
        result.discovered_from = synthesis.get("discovered_from")
        
        # If we discovered dates we didn't have, flag for confirmation
        if (result.birth_year_discovered and not result.birth_year) or \
           (result.death_year_discovered and not result.death_year):
            result.needs_confirmation = True
            if not result.confirmation_reason:
                result.confirmation_reason = f"Dates discovered from search results ({result.discovered_from})"
        
        # Biography and metadata
        result.biography = synthesis.get("biography")
        result.biography_short = synthesis.get("biography_short")
        result.notable = synthesis.get("notable", False)
        result.notable_reason = synthesis.get("notable_reason")
        result.confidence = synthesis.get("confidence", "low")
        result.occupation = synthesis.get("occupation")
        result.migration_path = synthesis.get("migration_path", [])
        result.locations = synthesis.get("locations", [])
        result.historic_events = synthesis.get("historic_events", [])

        # Notable family connections
        result.notable_relatives = synthesis.get("notable_relatives", [])

        # If notable relatives found, ensure notable flag is set
        if result.notable_relatives and not result.notable:
            result.notable = True
            relatives_summary = ", ".join([
                f"{r.get('relationship')}: {r.get('name')}"
                for r in result.notable_relatives[:2]
            ])
            result.notable_reason = result.notable_reason or f"Connected to notable figures ({relatives_summary})"

        flags = synthesis.get("flags", {})
        result.has_museum = flags.get("has_museum", False)
        result.has_cemetery = flags.get("has_cemetery", False)
        result.has_historic_site = flags.get("has_historic_site", False)
        result.pioneer_settler = flags.get("pioneer_settler", False)
        result.military_service = flags.get("military_service", False)
        result.noble_or_royal = flags.get("noble_or_royal", False)
        result.immigrant_pioneer = flags.get("immigrant_pioneer", False)

        # Additional flags from enhanced extraction
        if flags.get("signed_historic_document") or flags.get("founded_settlement"):
            result.notable = True
    
    def research_batch(self, individuals: list[dict], 
                       individual_objects: dict = None,
                       progress_callback: Callable = None,
                       delay_seconds: float = 1.0,
                       verbose: bool = False) -> list[ResearchResult]:
        """
        Research multiple individuals.
        
        Args:
            individuals: List of individual dicts from GEDCOM parser
            individual_objects: Dict mapping ID to Individual objects (for validation)
            progress_callback: Optional callback(current, total, result)
            delay_seconds: Delay between searches to avoid rate limiting
            verbose: Print progress
            
        Returns:
            List of ResearchResult objects
        """
        results = []
        total = len(individuals)
        
        for i, individual in enumerate(individuals):
            # Get the Individual object for family validation if available
            ind_obj = None
            if individual_objects:
                ind_obj = individual_objects.get(individual["id"])
            
            result = self.research_individual(individual, individual_obj=ind_obj, verbose=verbose)
            results.append(result)
            
            if progress_callback:
                progress_callback(i + 1, total, result)
            
            if i < total - 1 and delay_seconds > 0:
                time.sleep(delay_seconds)
        
        return results


class TokenTracker:
    """Track token usage and estimate costs across API calls."""

    # Pricing per million tokens (as of 2024)
    PRICING = {
        "claude-3-5-haiku-latest": {"input": 1.00, "output": 5.00},
        "claude-3-5-sonnet-latest": {"input": 3.00, "output": 15.00},
        "claude-3-opus-latest": {"input": 15.00, "output": 75.00},
    }

    def __init__(self):
        self.calls = []  # List of {model, input_tokens, output_tokens, prompt_type}
        self.total_input_tokens = 0
        self.total_output_tokens = 0

    def record(self, model: str, input_tokens: int, output_tokens: int, prompt_type: str = "unknown"):
        """Record a single API call."""
        self.calls.append({
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "prompt_type": prompt_type
        })
        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens

    def get_cost(self, model: str = "claude-3-5-haiku-latest") -> dict:
        """Calculate cost for a specific model."""
        pricing = self.PRICING.get(model, self.PRICING["claude-3-5-haiku-latest"])
        input_cost = (self.total_input_tokens / 1_000_000) * pricing["input"]
        output_cost = (self.total_output_tokens / 1_000_000) * pricing["output"]
        return {
            "model": model,
            "input_tokens": self.total_input_tokens,
            "output_tokens": self.total_output_tokens,
            "total_tokens": self.total_input_tokens + self.total_output_tokens,
            "input_cost": round(input_cost, 4),
            "output_cost": round(output_cost, 4),
            "total_cost": round(input_cost + output_cost, 4)
        }

    def get_cost_comparison(self) -> dict:
        """Compare costs across different models."""
        return {model: self.get_cost(model) for model in self.PRICING}

    def get_breakdown_by_type(self) -> dict:
        """Get token usage broken down by prompt type."""
        breakdown = {}
        for call in self.calls:
            ptype = call["prompt_type"]
            if ptype not in breakdown:
                breakdown[ptype] = {"calls": 0, "input_tokens": 0, "output_tokens": 0}
            breakdown[ptype]["calls"] += 1
            breakdown[ptype]["input_tokens"] += call["input_tokens"]
            breakdown[ptype]["output_tokens"] += call["output_tokens"]
        return breakdown

    def print_summary(self):
        """Print a formatted summary of usage and costs."""
        print("\n" + "=" * 60)
        print("TOKEN USAGE SUMMARY")
        print("=" * 60)
        print(f"Total API calls: {len(self.calls)}")
        print(f"Total input tokens: {self.total_input_tokens:,}")
        print(f"Total output tokens: {self.total_output_tokens:,}")
        print(f"Total tokens: {self.total_input_tokens + self.total_output_tokens:,}")

        print("\n--- Cost by Model ---")
        for model, cost in self.get_cost_comparison().items():
            model_short = model.replace("claude-3-5-", "").replace("-latest", "")
            print(f"  {model_short:12} ${cost['total_cost']:.4f} (in: ${cost['input_cost']:.4f}, out: ${cost['output_cost']:.4f})")

        breakdown = self.get_breakdown_by_type()
        if breakdown:
            print("\n--- Breakdown by Type ---")
            for ptype, stats in breakdown.items():
                print(f"  {ptype}: {stats['calls']} calls, {stats['input_tokens']:,} in / {stats['output_tokens']:,} out")

    def reset(self):
        """Reset all tracking."""
        self.calls = []
        self.total_input_tokens = 0
        self.total_output_tokens = 0


# Global tracker instance
_token_tracker = TokenTracker()


def get_token_tracker() -> TokenTracker:
    """Get the global token tracker instance."""
    return _token_tracker


def create_anthropic_synthesizer(api_key: str = None, model: str = "claude-3-5-haiku-latest",
                                  track_tokens: bool = True):
    """Create a synthesis function using Anthropic's Claude API.

    Args:
        api_key: Anthropic API key (defaults to ANTHROPIC_API_KEY env var)
        model: Model to use (default: claude-3-5-haiku-latest)
        track_tokens: Whether to track token usage for cost estimation

    Returns:
        Synthesis function and optionally updates global token tracker
    """
    import anthropic

    api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    client = anthropic.Anthropic(api_key=api_key)

    def _detect_prompt_type(prompt: str) -> str:
        """Auto-detect prompt type from content for tracking."""
        prompt_lower = prompt.lower()[:200]  # Check first 200 chars
        if "normalize this place" in prompt_lower or "normalize these place" in prompt_lower:
            return "place_normalization"
        elif "location" in prompt_lower and "enrich" in prompt_lower:
            return "location_enrichment"
        elif "historic event" in prompt_lower:
            return "event_enrichment"
        elif "classify" in prompt_lower:
            return "classification"
        else:
            return "ancestor_synthesis"

    def synthesize(prompt: str) -> str:
        response = client.messages.create(
            model=model,
            max_tokens=4000,
            messages=[{"role": "user", "content": prompt}]
        )

        # Track token usage with auto-detected type
        if track_tokens:
            input_tokens = response.usage.input_tokens
            output_tokens = response.usage.output_tokens
            prompt_type = _detect_prompt_type(prompt)
            _token_tracker.record(model, input_tokens, output_tokens, prompt_type)

        return response.content[0].text

    return synthesize


# For testing without API calls
def mock_search(query: str) -> str:
    """Mock search function for testing."""
    return f"[Mock search results for: {query}]\nNo results found in mock mode."


def mock_synthesize(prompt: str) -> str:
    """Mock synthesis function for testing."""
    return json.dumps({
        "birth_year_discovered": None,
        "death_year_discovered": None,
        "discovered_from": None,
        "biography": "Limited information available for this individual.",
        "biography_short": "Historical records for this person are limited.",
        "notable": False,
        "notable_reason": None,
        "confidence": "low",
        "occupation": None,
        "migration_path": [],
        "locations": [],
        "historic_events": [],
        "flags": {
            "has_museum": False,
            "has_cemetery": False,
            "has_historic_site": False,
            "pioneer_settler": False,
            "military_service": False,
            "noble_or_royal": False,
            "immigrant_pioneer": False
        }
    })
