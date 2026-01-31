# Where They Walked

Transform GEDCOM family tree files into enriched family history reports with:
- Biographical summaries for each ancestor
- Discovered dates validated against family timeline
- Historic site locations (museums, cemeteries, landmarks)
- Timeline of historic events connected to your ancestors
- Flags for notable ancestors (Mayflower connections, military service, etc.)

## Features

### Smart GEDCOM Parsing
- Extracts all individuals with names, dates, places, relationships
- Builds family context (parents, spouses, children)
- Generates optimized search queries using family relationships
- Handles individuals missing dates by using family context

### Research Pipeline
- Searches for each ancestor using web search
- AI synthesis extracts biographical data from search results
- **Discovers dates** from search results when missing from GEDCOM
- Extracts locations (museums, cemeteries, historic sites)
- Identifies connections to historic events

### Timeline Validation
Every discovered date is validated against family relationships:
- Parent birth years (must be born after parents were 15+)
- Children birth years (must be born before children)
- Spouse ages (reasonable age difference)
- Lifespan (reasonable length)

If validation fails, results are flagged for manual confirmation.

## Installation

```bash
pip install -r requirements.txt
```

## Usage

### Basic Usage

```python
from src import WhereTheyWalked

# Initialize with your search and synthesis functions
app = WhereTheyWalked(
    search_fn=your_search_function,      # query -> search results text
    synthesize_fn=your_synthesis_function # prompt -> AI response
)

# Load a GEDCOM file
stats = app.load_gedcom("family_tree.ged")
print(f"Found {stats['total_individuals']} individuals")

# Research all ancestors
results = app.research_ancestors(verbose=True)

# Export to JSON
app.export_json("output.json")
```

### Using with Anthropic API

```python
from src import WhereTheyWalked
from src.researcher import create_anthropic_synthesizer
import os

# Set your API key
os.environ["ANTHROPIC_API_KEY"] = "your-key-here"

# Create synthesis function using Claude Haiku
synthesize = create_anthropic_synthesizer()

# You'll need to provide your own search function
# For example, using a search API or web scraping
def search(query):
    # Your search implementation here
    pass

app = WhereTheyWalked(
    search_fn=search,
    synthesize_fn=synthesize
)
```

### Just Parse a GEDCOM

```python
from src import GedcomParser

parser = GedcomParser()
data = parser.parse_file("family_tree.ged")

# Get all researchable individuals
individuals = parser.get_researchable_individuals()

for ind in individuals:
    print(f"{ind.full_name} ({ind.birth_year}-{ind.death_year})")
    print(f"  Search query: {ind.search_query}")
    print(f"  Father: {ind._father.full_name if ind._father else 'Unknown'}")
    print(f"  Needs confirmation: {ind.needs_confirmation}")
```

### Validate Discovered Dates

```python
from src.researcher import TimelineValidator

validator = TimelineValidator()

# individual_obj is an Individual with family relationships populated
result = validator.validate(
    individual_obj,
    birth_discovered=1608,
    death_discovered=1630
)

print(f"Valid: {result.is_valid}")
print(f"Expected birth range: {result.expected_birth_min}-{result.expected_birth_max}")
print(f"Conflicts: {result.conflicts}")
print(f"Warnings: {result.warnings}")
```

## Output Format

### Research Result

```json
{
  "individual_id": "@I123@",
  "full_name": "John Bowne",
  "birth_year": 1627,
  "death_year": 1695,
  "birth_year_discovered": null,
  "death_year_discovered": null,
  "biography": "John Bowne was an early American Quaker...",
  "biography_short": "Pioneer of religious freedom in colonial America.",
  "notable": true,
  "notable_reason": "Established precedent for First Amendment",
  "confidence": "high",
  "locations": [
    {
      "name": "Bowne House",
      "type": "museum",
      "address": "37-01 Bowne Street, Flushing, NY",
      "coordinates": [40.762860, -73.824933],
      "description": "Historic home, now a museum"
    }
  ],
  "historic_events": [
    {
      "name": "Flushing Remonstrance",
      "year": 1657,
      "description": "Petition for religious freedom",
      "connection": "Signed and hosted Quaker meetings"
    }
  ],
  "has_museum": true,
  "needs_confirmation": false,
  "timeline_validation": {
    "is_valid": true,
    "conflicts": [],
    "warnings": []
  }
}
```

## Confirmation Flags

Results are flagged for confirmation when:

1. **No dates in GEDCOM** - Searched using family context only
2. **Dates discovered from search** - New information not in original data
3. **Timeline conflicts** - Discovered dates don't match family relationships
4. **Timeline warnings** - Dates are valid but unusual (e.g., died before child born)

## Project Structure

```
where-they-walked/
├── src/
│   ├── __init__.py
│   ├── gedcom_parser.py   # GEDCOM parsing, family context
│   ├── researcher.py      # Search, synthesis, validation
│   └── main.py            # Main application
├── requirements.txt
└── README.md
```

## License

MIT
