# Future Development Ideas

This file tracks planned enhancements and ideas discussed during development.
Each item includes context on why it would be valuable.

---

## High Priority

### 1. Parallel Processing for Ancestor Research
**Status:** Planned
**Complexity:** Moderate

Currently, ancestors are researched sequentially. For large trees (500+ individuals),
this is slow. Could use `asyncio` or `concurrent.futures` with controlled concurrency
(10-20 simultaneous requests) to stay within API rate limits.

**Rate limits to respect:**
- SerpAPI: Varies by plan
- Brave Search: 2,000/month free tier
- Anthropic: ~1000 req/min
- Nominatim geocoding: 1 request/second (strict)

**Implementation notes:**
- Process all ancestors in parallel (batch of N)
- Then process all locations in parallel
- Then process all events in parallel

---

### 2. AI-Driven Location Type Classification
**Status:** Needs Investigation
**Complexity:** Low-Medium

Currently, location types are inferred using keyword matching in `_infer_location_type()`:
- "cemetery", "burial", "graveyard" → cemetery
- "church", "chapel" → church
- etc.

This could miss locations the AI identifies that don't fit keywords. Options:
1. Add "other" category (simple fix)
2. Let AI classify in synthesis prompt (more flexible)
3. Hybrid: keyword match first, AI fallback

**Files affected:** `src/locations.py`

---

### 3. Ancestor Lineage Deep Search
**Status:** Idea
**Complexity:** Medium

When researching William Nickerson (1701-1763), we found pages about him specifically.
But there are RICHER pages about his ancestor William Nickerson (1604-1689) with:
- Land disputes with Native Americans
- Religious controversy ("scoffer & jeerer" fines)
- Immigration details (arrived Boston 1637)
- Occupation (weaver)

Could enhance by:
1. Following parent/ancestor links in search results
2. Searching for notable ancestors mentioned in results
3. Aggregating family history across generations

---

## Medium Priority

### 4. Notable Relatives Information Merging
**Status:** Documented in code (src/main.py `_dedupe_notable_relatives`)
**Complexity:** High (requires careful testing)

When ancestor A's research mentions ancestor B (who is in tree), we could:
1. Cross-reference mentions between profiles
2. Merge discovered information with attribution
3. Flag conflicts for manual review

**Safeguards needed:**
- Confidence scoring
- Source attribution ("discovered via John Bowne's research")
- Conflict flagging with diff display
- Rollback capability
- Name disambiguation (Sr vs Jr)

---

### 5. Expanded Deep Search (More Pages)
**Status:** Idea
**Complexity:** Low

Currently fetching top 3 pages. Some ancestors have 10+ quality sources.
Could make this configurable or adaptive based on result quality.

**Trade-off:** More API calls, higher cost, but richer data.

---

### 6. Historic Site Discovery from Ancestor Pages
**Status:** Needs Investigation
**Complexity:** Medium

The sibertancestry.org page mentions specific places:
- "Norwich, Norfolk, England" (origin)
- "Boston shop"
- "Monomoit land" (disputed land)

These could be extracted and added to locations even if not
explicitly formatted as location data.

---

## Lower Priority

### 7. GeoJSON Timeline Animation
**Status:** Idea
**Complexity:** Medium

Export locations with year data for animated map showing
family migration over centuries.

### 8. Report Generation (PDF/HTML)
**Status:** Not started
**Complexity:** Medium

Generate formatted reports from JSON data for printing or sharing.

### 9. Cemetery/FindAGrave Integration
**Status:** Idea
**Complexity:** Medium

Direct API integration with FindAGrave for burial location details.

### 10. Mayflower/DAR Lineage Verification
**Status:** Idea
**Complexity:** High

Cross-reference with official lineage databases.

---

## Notes

- Always test thoroughly before implementing merging/deduplication logic
- Rate limiting is critical for parallel processing
- AI classification should have human-reviewable confidence scores
