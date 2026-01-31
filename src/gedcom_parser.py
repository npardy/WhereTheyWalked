"""
GEDCOM Parser for Where They Walked
Extracts individuals from GEDCOM files with names, dates, places, and relationships.
"""

import re
from dataclasses import dataclass, field
from typing import Optional
from pathlib import Path
import json


@dataclass
class Event:
    """Birth, death, or other life event."""
    event_type: str
    date: Optional[str] = None
    place: Optional[str] = None
    
    def to_dict(self):
        return {
            "type": self.event_type,
            "date": self.date,
            "place": self.place
        }


@dataclass 
class Individual:
    """A person in the family tree."""
    id: str
    given_name: Optional[str] = None
    surname: Optional[str] = None
    sex: Optional[str] = None
    birth: Optional[Event] = None
    death: Optional[Event] = None
    family_child: Optional[str] = None  # Family ID where this person is a child
    family_spouse: list = field(default_factory=list)  # Family IDs where this person is a spouse
    
    # These get populated by GedcomParser.enrich_family_context()
    _father: Optional['Individual'] = field(default=None, repr=False)
    _mother: Optional['Individual'] = field(default=None, repr=False)
    _spouses: list = field(default_factory=list, repr=False)
    _children: list = field(default_factory=list, repr=False)
    
    @property
    def full_name(self) -> str:
        parts = []
        if self.given_name:
            parts.append(self.given_name)
        if self.surname:
            parts.append(self.surname)
        return " ".join(parts) if parts else "Unknown"
    
    @property
    def birth_year(self) -> Optional[int]:
        if self.birth and self.birth.date:
            match = re.search(r'\b(\d{4})\b', self.birth.date)
            if match:
                return int(match.group(1))
        return None
    
    @property
    def death_year(self) -> Optional[int]:
        if self.death and self.death.date:
            match = re.search(r'\b(\d{4})\b', self.death.date)
            if match:
                return int(match.group(1))
        return None
    
    @property
    def birth_place(self) -> Optional[str]:
        if self.birth:
            return self.birth.place
        return None
    
    @property
    def death_place(self) -> Optional[str]:
        if self.death:
            return self.death.place
        return None
    
    @property
    def has_dates(self) -> bool:
        """Check if this person has any dates."""
        return self.birth_year is not None or self.death_year is not None
    
    def _has_searchable_family_context(self) -> bool:
        """Check if this person has family members with enough info to help search."""
        # Check spouses
        for spouse in self._spouses:
            if spouse.surname and spouse.surname != "_____":
                return True
        # Check parents
        if self._father and self._father.surname and self._father.surname != "_____":
            return True
        if self._mother and self._mother.surname and self._mother.surname != "_____":
            return True
        # Check children
        for child in self._children:
            if child.surname and child.surname != "_____":
                return True
        return False
    
    def estimate_birth_year(self) -> tuple[Optional[int], Optional[str]]:
        """
        Estimate birth year from family relationships.
        Returns (estimated_year, explanation) or (None, None).
        """
        estimates = []
        
        # From spouse's birth year (assume similar age, +/- 10 years)
        for spouse in self._spouses:
            if spouse.birth_year:
                estimates.append((spouse.birth_year, f"spouse {spouse.full_name} born {spouse.birth_year}"))
        
        # From children's birth years (assume parent born ~20-35 years before first child)
        child_years = [c.birth_year for c in self._children if c.birth_year]
        if child_years:
            earliest_child = min(child_years)
            est = earliest_child - 27  # Assume average age of 27 at first child
            estimates.append((est, f"first child born {earliest_child}"))
        
        # From parent's birth year (assume child born ~25-35 years after parent)
        if self._father and self._father.birth_year:
            est = self._father.birth_year + 30
            estimates.append((est, f"father {self._father.full_name} born {self._father.birth_year}"))
        if self._mother and self._mother.birth_year:
            est = self._mother.birth_year + 28
            estimates.append((est, f"mother {self._mother.full_name} born {self._mother.birth_year}"))
        
        if estimates:
            # Average the estimates
            avg_year = sum(e[0] for e in estimates) // len(estimates)
            explanations = [e[1] for e in estimates]
            return (avg_year, "; ".join(explanations))
        
        return (None, None)
    
    def get_family_context_for_search(self) -> tuple[list[str], bool]:
        """
        Get additional search terms from family relationships.
        Returns (list of context terms, needs_confirmation flag).
        """
        context = []
        needs_confirmation = False
        
        # If we have no dates, we need family context and should flag for confirmation
        if not self.has_dates:
            needs_confirmation = True
            
            # Add spouse names
            for spouse in self._spouses:
                if spouse.full_name != "Unknown":
                    context.append(f'"{spouse.full_name}"')
            
            # Add parent names (especially useful for disambiguation)
            if self._father and self._father.full_name != "Unknown":
                context.append(f'son of "{self._father.full_name}"' if self.sex == 'M' else f'child of "{self._father.full_name}"')
            
            # Add location from relations if we don't have our own
            if not self.birth_place and not self.death_place:
                for spouse in self._spouses:
                    if spouse.birth_place:
                        # Extract region
                        parts = spouse.birth_place.split(",")
                        if len(parts) >= 2:
                            context.append(parts[-2].strip())
                        break
        
        return (context, needs_confirmation)
    
    @property
    def search_query(self) -> str:
        """Generate a search query for this person."""
        parts = []
        
        # Name - handle first-name-only case
        if self.surname and self.surname != "_____":
            parts.append(f'"{self.full_name}"')
        else:
            # First name only - must rely on family context
            parts.append(f'"{self.given_name}"')
        
        if self.birth_year:
            parts.append(str(self.birth_year))
        if self.death_year:
            parts.append(str(self.death_year))
        
        # Add primary location
        place = self.birth_place or self.death_place
        if place:
            place_parts = [p.strip() for p in place.split(",")]
            if len(place_parts) >= 2:
                parts.append(place_parts[0])  # Town/city
                parts.append(place_parts[-2] if len(place_parts) > 2 else place_parts[-1])  # Region/country
        
        # If no dates OR no surname, add family context
        if not self.has_dates or not self.surname or self.surname == "_____":
            family_context, _ = self.get_family_context_for_search()
            parts.extend(family_context)
        
        return " ".join(parts)
    
    @property
    def needs_confirmation(self) -> bool:
        """Check if search results for this person need manual confirmation."""
        _, needs_conf = self.get_family_context_for_search()
        return needs_conf
    
    def to_dict(self):
        estimated_year, estimated_from = self.estimate_birth_year() if not self.birth_year else (None, None)
        
        return {
            "id": self.id,
            "given_name": self.given_name,
            "surname": self.surname,
            "full_name": self.full_name,
            "sex": self.sex,
            "birth": self.birth.to_dict() if self.birth else None,
            "death": self.death.to_dict() if self.death else None,
            "birth_year": self.birth_year,
            "death_year": self.death_year,
            "birth_year_estimated": estimated_year,
            "birth_year_estimated_from": estimated_from,
            "birth_place": self.birth_place,
            "death_place": self.death_place,
            "search_query": self.search_query,
            "needs_confirmation": self.needs_confirmation,
            "family_child": self.family_child,
            "family_spouse": self.family_spouse,
            # Include family names for reference
            "father_name": self._father.full_name if self._father else None,
            "mother_name": self._mother.full_name if self._mother else None,
            "spouse_names": [s.full_name for s in self._spouses],
            "children_names": [c.full_name for c in self._children]
        }


@dataclass
class Family:
    """A family unit (marriage/partnership)."""
    id: str
    husband_id: Optional[str] = None
    wife_id: Optional[str] = None
    children_ids: list = field(default_factory=list)
    marriage_date: Optional[str] = None
    marriage_place: Optional[str] = None
    
    def to_dict(self):
        return {
            "id": self.id,
            "husband_id": self.husband_id,
            "wife_id": self.wife_id,
            "children_ids": self.children_ids,
            "marriage_date": self.marriage_date,
            "marriage_place": self.marriage_place
        }


class GedcomParser:
    """Parse GEDCOM files into structured data."""
    
    def __init__(self):
        self.individuals: dict[str, Individual] = {}
        self.families: dict[str, Family] = {}
    
    def parse_file(self, filepath: str) -> dict:
        """Parse a GEDCOM file and return structured data."""
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        return self.parse(content)
    
    def parse(self, content: str) -> dict:
        """Parse GEDCOM content string."""
        lines = content.strip().split('\n')
        
        current_individual = None
        current_family = None
        current_event = None
        current_name_level = None
        
        for line in lines:
            # Parse line: "LEVEL [TAG|ID] [VALUE]"
            match = re.match(r'^(\d+)\s+(@\S+@|\S+)\s*(.*)?$', line.strip())
            if not match:
                continue
                
            level = int(match.group(1))
            tag_or_id = match.group(2)
            value = match.group(3) or ""
            value = value.strip()
            
            # Level 0: New record
            if level == 0:
                current_individual = None
                current_family = None
                current_event = None
                
                if value == "INDI":
                    ind_id = tag_or_id
                    current_individual = Individual(id=ind_id)
                    self.individuals[ind_id] = current_individual
                elif value == "FAM":
                    fam_id = tag_or_id
                    current_family = Family(id=fam_id)
                    self.families[fam_id] = current_family
            
            # Individual tags
            elif current_individual:
                if level == 1:
                    current_event = None
                    current_name_level = None
                    
                    if tag_or_id == "NAME":
                        # Parse name: "Given /Surname/"
                        name_match = re.match(r'^([^/]*)/([^/]*)/', value)
                        if name_match:
                            current_individual.given_name = name_match.group(1).strip() or None
                            current_individual.surname = name_match.group(2).strip() or None
                        current_name_level = 1
                    elif tag_or_id == "SEX":
                        current_individual.sex = value
                    elif tag_or_id == "BIRT":
                        current_event = Event(event_type="birth")
                        current_individual.birth = current_event
                    elif tag_or_id == "DEAT":
                        current_event = Event(event_type="death")
                        current_individual.death = current_event
                    elif tag_or_id == "FAMC":
                        current_individual.family_child = value
                    elif tag_or_id == "FAMS":
                        current_individual.family_spouse.append(value)
                
                elif level == 2:
                    if current_name_level == 1:
                        if tag_or_id == "GIVN":
                            current_individual.given_name = value
                        elif tag_or_id == "SURN":
                            current_individual.surname = value
                    elif current_event:
                        if tag_or_id == "DATE":
                            current_event.date = value
                        elif tag_or_id == "PLAC":
                            current_event.place = value
            
            # Family tags
            elif current_family:
                if level == 1:
                    current_event = None
                    
                    if tag_or_id == "HUSB":
                        current_family.husband_id = value
                    elif tag_or_id == "WIFE":
                        current_family.wife_id = value
                    elif tag_or_id == "CHIL":
                        current_family.children_ids.append(value)
                    elif tag_or_id == "MARR":
                        current_event = "marriage"
                
                elif level == 2 and current_event == "marriage":
                    if tag_or_id == "DATE":
                        current_family.marriage_date = value
                    elif tag_or_id == "PLAC":
                        current_family.marriage_place = value
        
        # Enrich individuals with family relationships
        self.enrich_family_context()
        
        return self.to_dict()
    
    def to_dict(self) -> dict:
        """Export parsed data as dictionary."""
        return {
            "individuals": {k: v.to_dict() for k, v in self.individuals.items()},
            "families": {k: v.to_dict() for k, v in self.families.items()},
            "stats": self.get_stats()
        }
    
    def enrich_family_context(self):
        """Populate family relationships for all individuals."""
        for ind in self.individuals.values():
            # Find parents
            if ind.family_child:
                family = self.families.get(ind.family_child)
                if family:
                    if family.husband_id:
                        ind._father = self.individuals.get(family.husband_id)
                    if family.wife_id:
                        ind._mother = self.individuals.get(family.wife_id)
            
            # Find spouses and children
            for fam_id in ind.family_spouse:
                family = self.families.get(fam_id)
                if family:
                    # Find spouse
                    if ind.sex == 'M' and family.wife_id:
                        spouse = self.individuals.get(family.wife_id)
                        if spouse:
                            ind._spouses.append(spouse)
                    elif ind.sex == 'F' and family.husband_id:
                        spouse = self.individuals.get(family.husband_id)
                        if spouse:
                            ind._spouses.append(spouse)
                    else:
                        # Sex unknown, try both
                        if family.wife_id and family.wife_id != ind.id:
                            spouse = self.individuals.get(family.wife_id)
                            if spouse:
                                ind._spouses.append(spouse)
                        if family.husband_id and family.husband_id != ind.id:
                            spouse = self.individuals.get(family.husband_id)
                            if spouse:
                                ind._spouses.append(spouse)
                    
                    # Find children
                    for child_id in family.children_ids:
                        child = self.individuals.get(child_id)
                        if child:
                            ind._children.append(child)
    
    def get_stats(self) -> dict:
        """Get statistics about the parsed data."""
        individuals = list(self.individuals.values())
        
        # Count by century
        centuries = {}
        for ind in individuals:
            year = ind.birth_year
            if year:
                century = (year // 100) + 1
                centuries[century] = centuries.get(century, 0) + 1
        
        # Unique surnames
        surnames = set()
        for ind in individuals:
            if ind.surname:
                surnames.add(ind.surname)
        
        # Places
        places = set()
        for ind in individuals:
            if ind.birth_place:
                places.add(ind.birth_place)
            if ind.death_place:
                places.add(ind.death_place)
        
        return {
            "total_individuals": len(individuals),
            "total_families": len(self.families),
            "unique_surnames": len(surnames),
            "surnames": sorted(surnames),
            "unique_places": len(places),
            "by_century": centuries
        }
    
    def get_researchable_individuals(self, min_year: int = None, max_year: int = None, 
                                       require_dates: bool = False) -> list[Individual]:
        """
        Get individuals worth researching.
        
        Args:
            min_year: Minimum birth year to include
            max_year: Maximum birth year to include
            require_dates: If True, only include people with dates. 
                          If False, include anyone searchable (surname OR family context).
        """
        results = []
        for ind in self.individuals.values():
            # Check if this person is searchable
            has_surname = ind.surname and ind.surname != "_____"
            has_family_context = ind._has_searchable_family_context()
            
            if not has_surname and not has_family_context:
                # No surname and no family to reference - can't search
                continue
            
            # Must have a given name at minimum
            if not ind.given_name:
                continue
            
            # If requiring dates, filter out those without
            if require_dates and not ind.has_dates:
                continue
            
            # Filter by year range if specified (use estimated year if no actual year)
            if min_year or max_year:
                year = ind.birth_year or ind.death_year
                if not year:
                    # Try estimated year
                    est_year, _ = ind.estimate_birth_year()
                    year = est_year
                
                if year:
                    if min_year and year < min_year:
                        continue
                    if max_year and year > max_year:
                        continue
                elif require_dates:
                    # No year at all and we're filtering by year, skip
                    continue
            
            results.append(ind)
        
        # Sort by birth year (actual or estimated), unknowns at end
        def sort_key(x):
            year = x.birth_year or x.death_year
            if not year:
                est, _ = x.estimate_birth_year()
                year = est
            return year or 9999
        
        results.sort(key=sort_key)
        return results


def main():
    """Test the parser with a GEDCOM file."""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python gedcom_parser.py <gedcom_file>")
        sys.exit(1)
    
    filepath = sys.argv[1]
    parser = GedcomParser()
    data = parser.parse_file(filepath)
    
    print(f"\n=== GEDCOM Parse Results ===")
    print(f"Total individuals: {data['stats']['total_individuals']}")
    print(f"Total families: {data['stats']['total_families']}")
    print(f"Unique surnames: {data['stats']['unique_surnames']}")
    print(f"\nBy century: {data['stats']['by_century']}")
    
    # Show first 10 researchable individuals
    researchable = parser.get_researchable_individuals()
    print(f"\n=== Researchable Individuals ({len(researchable)} total) ===")
    for ind in researchable[:10]:
        print(f"  {ind.full_name} ({ind.birth_year or '?'}-{ind.death_year or '?'}) - {ind.birth_place or ind.death_place or 'Unknown'}")
        print(f"    Search: {ind.search_query}")


if __name__ == "__main__":
    main()
