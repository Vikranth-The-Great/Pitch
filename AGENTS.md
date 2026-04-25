# AGENTS.md — WanderWise AI Rebuild

> **Blueprint for AI coding agents working on the WanderWise itinerary generator.**
> All planning documents live in `docs/`. Implementation follows the phase order in `PLAN.md`.

---

## 1. Project Overview

WanderWise is a travel itinerary generator that takes a user's trip parameters — city, dates,
number of people, budget, theme, and travel type — and produces a structured day-by-day plan
including a hotel recommendation, attractions, and meal stops.

### The core problem with the current implementation

The existing system uses a **hand-written heuristic algorithm** to rank and schedule places. It is
rigid, produces mediocre itineraries, ignores `travel_type`, handles meals poorly, and performs
redundant Google API calls that waste quota and add latency.

### The solution

Replace the ranking and scheduling brain with **OpenAI GPT-4o**. Google Maps APIs remain the
data source for live place discovery, photos, hours, and travel times. OpenAI becomes the
intelligence layer that:

- Selects and ranks the best places for the given trip profile.
- Constructs a coherent, human-quality day schedule.
- Writes a short natural-language justification for every recommendation.
- Handles breakfast, lunch, and dinner intelligently across all days.

The result is a system where Google Maps provides **accurate, live data** and OpenAI provides
**intelligent, contextual planning**.

---

## 2. Business Requirements

### Functional requirements

| # | Requirement |
|---|-------------|
| 1 | Accept trip parameters: city, start date, number of days, number of people, theme, travel type, budget tier, total budget. |
| 2 | Fetch live places (attractions, hotels, restaurants) from Google Maps. |
| 3 | Use OpenAI to select, rank, and schedule places into a day-by-day itinerary. |
| 4 | Respect user budget: hotel cost + activity cost must not exceed total_budget. |
| 5 | Avoid duplicate attractions across days. |
| 6 | Insert breakfast, lunch, and dinner on each day when feasible. |
| 7 | Return structured JSON via FastAPI POST endpoint. |
| 8 | Expose a working demo frontend (existing static/index.html is acceptable). |
| 9 | Include a CLI runner for local testing. |

### Constraints

- OpenAI must be called **once per day** of the trip (not once per place). This keeps token usage and latency reasonable.
- Google Place Details must be fetched **only once per place** (fix the current double-fetch bug).
- If any external API call fails, the system must degrade gracefully — return partial results, not a 500 error.
- All API keys must be read from `.env`. No hardcoded keys anywhere.

### Out of scope for this rebuild

- Multi-city itineraries.
- Real-time flight or hotel booking.
- User authentication or persistent user data.

---

## 3. Technical Stack

| Layer | Technology |
|-------|-----------|
| Language | Python 3.11+ |
| API Framework | FastAPI |
| ASGI Server | Uvicorn |
| HTTP Client | `httpx` (async) — replace current `requests` |
| AI Provider | OpenAI Python SDK (`openai>=1.0`) |
| Maps Provider | Google Maps (Places Text Search, Place Details, Distance Matrix) |
| Data Validation | Pydantic v2 |
| Config | `python-dotenv` |
| Testing | `pytest`, `pytest-asyncio`, FastAPI `TestClient` |
| Frontend | Existing `static/index.html` (minimal changes only) |

### New environment variables required

```env
GOOGLE_MAPS_API_KEY=your_google_maps_key
OPENAI_API_KEY=your_openai_key
```

---

## 4. System Architecture

```
User Request
    │
    ▼
FastAPI  (app.py)
    │
    ├─► Google Maps Provider  (providers/google_maps.py)
    │       • fetch_places()          — text search, ONE detail fetch per place
    │       • fetch_travel_time()     — distance matrix
    │       • build_image_url()       — photo reference → URL
    │
    ├─► AI Planner            (core/ai_planner.py)   ← NEW FILE
    │       • plan_day()              — calls OpenAI once per day
    │       • build_system_prompt()   — constructs context-rich prompt
    │       • parse_ai_response()     — extracts structured JSON from GPT reply
    │
    ├─► Budget Guard          (core/budget.py)        ← NEW FILE
    │       • reserve_hotel_budget()
    │       • allocate_daily_budget()
    │       • check_within_budget()
    │
    └─► Schemas               (models/schemas.py)
            • ItineraryRequest
            • ItineraryResponse
            • DayPlan, ItineraryEntry, HotelResponse, SummaryResponse
```

### Data flow per request

```
1. Validate request via Pydantic.
2. Fetch hotel candidates from Google Maps → pick best by rating + location centrality.
3. Reserve hotel cost from total budget.
4. Fetch attractions (20) and restaurants (15) from Google Maps — ONE detail call per place.
5. For each day:
   a. Filter out already-visited attraction IDs.
   b. Call OpenAI once with: place list, user preferences, remaining budget, day number, travel type.
   c. OpenAI returns a structured JSON schedule for that day (attractions + meals + times).
   d. Validate and post-process the AI response.
   e. Mark chosen attractions as visited.
6. Assemble ItineraryResponse and return.
```

---

## 5. Key Files and Their Roles

| File | Role |
|------|------|
| `app.py` | FastAPI app, CORS, static mount, orchestration of providers + AI planner |
| `main.py` | CLI entry point — reuses `build_itinerary()` from app.py |
| `providers/google_maps.py` | All Google Maps API calls (fix double-fetch here) |
| `core/ai_planner.py` | **NEW** — OpenAI integration, prompt building, response parsing |
| `core/budget.py` | **NEW** — All budget math extracted into one place |
| `core/filter.py` | Keep hotel selection logic (`rank_hotels`). Remove attraction ranking (OpenAI handles it). |
| `core/optimizer.py` | **DELETE or stub out** — OpenAI replaces the greedy optimizer |
| `models/schemas.py` | Pydantic models — add `ai_justification` field to `ItineraryEntry` |
| `static/index.html` | Existing frontend — update only if needed for new fields |
| `tests/` | Update tests to mock OpenAI alongside Google Maps |
| `docs/` | All planning documents go here |

---

## 6. Implementation Strategy

Follow `PLAN.md` strictly, one phase at a time. Do not skip phases.

### Phase order summary

1. Fix Google Maps provider (eliminate double-fetch, add error handling).
2. Build the AI Planner module (`core/ai_planner.py`).
3. Build the Budget Guard module (`core/budget.py`).
4. Refactor `app.py` orchestration to use AI Planner + Budget Guard.
5. Update schemas for new fields (`ai_justification`, meal entries).
6. Update and run the full test suite.
7. Verify end-to-end with a real API call.

### OpenAI prompt design (critical)

The prompt sent to OpenAI for each day must include:

- Trip context: city, theme, travel_type, num_people, budget_tier.
- Day context: day number, date, remaining budget for the day.
- Available places: a compact JSON list of candidates with name, rating, types, opening_hours summary, estimated cost, coordinates.
- Already-visited attraction IDs (to prevent duplicates).
- Explicit instruction to return **only valid JSON** matching a defined schema.

The response schema OpenAI must return:

```json
{
  "schedule": [
    {
      "place_id": "...",
      "location_name": "...",
      "category": "Attraction | Restaurant | Hotel",
      "meal_type": "Breakfast | Lunch | Dinner | null",
      "arrival_time": "HH:MM",
      "departure_time": "HH:MM",
      "cost": 0,
      "ai_justification": "One sentence explaining why this was chosen."
    }
  ],
  "day_summary": "One sentence overview of the day."
}
```

Use OpenAI's `response_format: { type: "json_object" }` to enforce JSON output.

### Error handling rules

- If OpenAI returns malformed JSON → log the error, return an empty schedule for that day with a warning message.
- If a Google Maps call fails → log the error, skip that place, continue.
- If budget is exhausted → stop scheduling further days, return what was built with `within_budget: false`.
- Never raise an unhandled exception to the user. Always return a valid (possibly partial) `ItineraryResponse`.

---

## 7. Coding Standards

- **Keep every function under 40 lines.** Extract helpers aggressively.
- **No hardcoded strings** for API endpoints, model names, or prompt text. Use module-level constants.
- **Single responsibility** — one module, one job. The AI planner does not touch budgets. The budget module does not call APIs.
- **No double API calls.** `fetch_places` must be the only place that calls `fetch_place_details`. `app.py` must not call `_merge_place_details` on top of already-enriched places.
- **Use `httpx` instead of `requests`** for consistency with FastAPI's async model.
- **Use Pydantic v2 `model_validate`** not deprecated `parse_obj`.
- **All secrets from `.env` only.** Load once at startup, not at import time inside every function.
- **Type hints on every function signature.**
- **Do not over-engineer the frontend.** The existing `static/index.html` is acceptable. Add new fields (justification, day summary) to the rendered output only.
- Planning and working documents must be stored in the `docs/` directory. Do not duplicate them at the repository root.

---

## 8. Testing Standards

- Every new module (`ai_planner.py`, `budget.py`) must have a corresponding test file.
- OpenAI calls must be **mocked** in tests — never hit the real API in automated tests.
- Google Maps calls must remain mocked as they currently are.
- The `test_api.py` integration test must continue to pass with the new orchestration.
- New tests required:
  - `tests/test_ai_planner.py` — mock OpenAI, verify prompt construction and response parsing.
  - `tests/test_budget.py` — verify hotel reservation, daily allocation, and within-budget check.

---

## 9. Acceptance Criteria

The rebuild is complete when:

- `POST /api/generate-itinerary` returns a valid `ItineraryResponse` with at least one day scheduled.
- The itinerary includes at least one meal entry per day.
- No attraction appears on more than one day.
- Total cost does not exceed `total_budget`.
- `ai_justification` is populated on every `ItineraryEntry`.
- `pytest tests/ -q` passes with all tests green.
- The demo frontend renders the full response including justifications.
- No Google API call is made more than once per place per request.
