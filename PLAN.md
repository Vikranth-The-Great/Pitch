# PLAN.md — WanderWise AI Rebuild Execution Plan

> **Master execution plan. AI coding agents must follow phases in order. Never skip a phase.**
> Read `AGENTS.md` before starting. Present this plan to the user and wait for approval before implementing.

---

## Project Summary

Replace WanderWise's broken rule-based optimizer with an OpenAI-powered planning engine.
Google Maps continues to supply live place data. OpenAI becomes the intelligence layer that
constructs coherent, human-quality itineraries per day.

**Two new API keys required:** `GOOGLE_MAPS_API_KEY` (existing) and `OPENAI_API_KEY` (new).

---

## Execution Rules

1. Implement one phase at a time. Run the tests for that phase before moving to the next.
2. If a phase's tests fail, fix the issue before proceeding.
3. Never implement Phase N+1 while Phase N is broken.
4. Log every OpenAI prompt and response to the console during development (remove before final demo).
5. Keep all planning documents in `docs/`. Do not create duplicate files at the repository root.

---

## Phase 1 — Environment and Dependency Upgrade

### Objective
Bring the project environment up to date and add the OpenAI SDK. Fix the `.env` configuration.

### Tasks

- [ ] Add `openai>=1.0` and `httpx` to `requirements.txt`. Remove bare `requests` (replaced by `httpx`).
- [ ] Update `.env.example` to include both keys:
  ```
  GOOGLE_MAPS_API_KEY=your_google_maps_key_here
  OPENAI_API_KEY=your_openai_key_here
  ```
- [ ] Add `OPENAI_API_KEY` loading to `app.py` startup (alongside the existing Google key).
- [ ] Confirm the virtual environment can be created cleanly:
  ```bash
  python -m venv .venv
  source .venv/bin/activate   # Windows: .venv\Scripts\activate
  pip install -r requirements.txt
  ```
- [ ] Run `uvicorn app:app --reload --port 8000` and verify `GET /health` returns `{"status": "ok"}`.

### Tests

```bash
curl http://localhost:8000/health
# Expected: {"status":"ok"}
```

### Success Criteria

- `requirements.txt` contains `openai`, `httpx`, `fastapi`, `uvicorn`, `pydantic`, `python-dotenv`, `pytest`, `pytest-asyncio`.
- Server starts without import errors.
- `/health` returns 200.

---

## Phase 2 — Fix the Google Maps Provider

### Objective
Eliminate the double-fetch bug. Each place must call `fetch_place_details` exactly once.
Add proper error handling so a failed API call does not crash the whole request.

### Tasks

- [ ] Open `providers/google_maps.py`.
- [ ] In `fetch_places()`, confirm it already calls `fetch_place_details()` for each result. It does — this is the **only** place that should call it.
- [ ] Open `app.py`. Find `_merge_place_details()`. **Remove all calls to this function.** The places returned by `fetch_places()` are already fully enriched.
- [ ] Delete the `_merge_place_details()` function from `app.py`.
- [ ] Wrap `fetch_place_details()` in a try/except. On failure, log the error and return a minimal dict with just `place_id` and `name`.
- [ ] Wrap `fetch_places()` in a try/except. On failure, log the error and return an empty list.
- [ ] Wrap `fetch_travel_time()` — it already has a fallback, but ensure it never raises.
- [ ] Replace `import requests` with `import httpx` in the provider file. Update `_request_json()` to use `httpx.get()`.
- [ ] Verify the provider still works by hitting `POST /api/generate-itinerary` with a real key and a simple city like `Mysuru`. Confirm the response contains places.

### Tests

- [ ] Run existing `tests/test_api.py` — it must still pass (provider calls are mocked there).
- [ ] Manually confirm no duplicate API calls appear in server logs.

### Success Criteria

- `_merge_place_details` no longer exists in `app.py`.
- Each place triggers exactly one `fetch_place_details` call per request.
- `requests` is no longer imported anywhere; `httpx` is used instead.
- All existing provider-level tests pass.

---

## Phase 3 — Build the Budget Guard Module

### Objective
Extract all budget arithmetic into a single, testable module: `core/budget.py`.

### Tasks

- [ ] Create `core/budget.py`.
- [ ] Implement these functions:

  ```python
  def reserve_hotel_budget(cost_per_night: int, num_days: int) -> int:
      """Returns total hotel cost for the trip."""

  def allocate_daily_budget(
      total_budget: int,
      hotel_total: int,
      accumulated_activity_cost: int,
      num_days: int,
      current_day_index: int,
  ) -> int:
      """Returns the budget available for the current day's activities."""

  def check_within_budget(total_cost: int, budget_limit: int) -> bool:
      """Returns True if total_cost <= budget_limit."""
  ```

- [ ] Import and use these functions in `app.py` — remove all inline budget arithmetic from `build_itinerary()`.
- [ ] Create `tests/test_budget.py` with the following cases:
  - Hotel total is `cost_per_night * num_days`.
  - Daily budget decreases correctly as activity cost accumulates.
  - Daily budget never goes negative (return 0 if overspent).
  - `check_within_budget` returns True/False correctly.

### Tests

```bash
pytest tests/test_budget.py -v
```

### Success Criteria

- `core/budget.py` exists and is importable.
- All budget test cases pass.
- `app.py` no longer contains inline budget math — it calls `budget.py` functions.

---

## Phase 4 — Build the AI Planner Module

### Objective
Create `core/ai_planner.py`. This is the most important new module. It replaces the entire
`core/optimizer.py` greedy scheduler with an OpenAI-powered planner.

### Tasks

- [ ] Create `core/ai_planner.py`.
- [ ] Implement `build_system_prompt(trip_context: dict) -> str`:
  - Receives: city, theme, travel_type, num_people, budget_tier.
  - Returns a system prompt that tells GPT-4o its role and the exact JSON schema it must return.
  - The schema it must return per day:
    ```json
    {
      "schedule": [
        {
          "place_id": "string",
          "location_name": "string",
          "category": "Attraction | Restaurant",
          "meal_type": "Breakfast | Lunch | Dinner | null",
          "arrival_time": "HH:MM",
          "departure_time": "HH:MM",
          "cost": 0,
          "ai_justification": "string"
        }
      ],
      "day_summary": "string"
    }
    ```

- [ ] Implement `build_user_prompt(day_context: dict, places: list, visited_ids: set) -> str`:
  - Receives: day number, date, remaining_budget, available places (compact list), visited_ids.
  - Formats places as a concise JSON snippet (name, rating, types, estimated cost, coords).
  - Instructs the model to avoid any place_id in `visited_ids`.
  - Instructs the model to insert Breakfast (~08:00), Lunch (~13:00), Dinner (~19:00) using restaurant candidates.
  - Instructs the model to stay within `remaining_budget`.
  - Instructs the model to start at 08:00 and end by 21:00.
  - Instructs the model to return ONLY the JSON object, no prose.

- [ ] Implement `plan_day(system_prompt: str, user_prompt: str, openai_client) -> dict`:
  - Calls `openai_client.chat.completions.create(...)` with:
    - `model="gpt-4o"`
    - `response_format={"type": "json_object"}`
    - `max_tokens=2000`
  - Parses the JSON response.
  - Returns the parsed dict on success.
  - On any exception (API error, JSON parse error), logs the error and returns `{"schedule": [], "day_summary": "Could not plan this day."}`.

- [ ] Implement `parse_ai_response(raw: dict) -> list[dict]`:
  - Validates that `raw["schedule"]` is a list.
  - Returns the schedule list, or `[]` on invalid structure.

- [ ] Add module-level constant: `OPENAI_MODEL = "gpt-4o"`.

### Tests

- [ ] Create `tests/test_ai_planner.py`.
- [ ] Mock `openai_client.chat.completions.create` using `unittest.mock.MagicMock`.
- [ ] Test cases:
  - Valid OpenAI response is parsed correctly into a schedule list.
  - Malformed JSON from OpenAI returns an empty schedule without raising.
  - OpenAI API exception returns an empty schedule without raising.
  - System prompt contains the word "JSON" (sanity check).
  - User prompt contains the `visited_ids` if provided.

```bash
pytest tests/test_ai_planner.py -v
```

### Success Criteria

- `core/ai_planner.py` exists and is importable.
- All AI planner tests pass with mocked OpenAI.
- No real OpenAI calls are made in tests.

---

## Phase 5 — Refactor App Orchestration

### Objective
Wire the new AI Planner and Budget Guard into `app.py`. Remove all references to
`optimize_schedule` from the old greedy optimizer.

### Tasks

- [ ] Open `app.py`. Refactor `build_itinerary(payload)` with the following logic:

  ```
  1. Fetch hotel candidates → select best hotel via rank_hotels() (keep existing logic).
  2. hotel_cost_total = reserve_hotel_budget(hotel.cost_per_night, num_days)
  3. Fetch attractions (20 results) — single fetch_places call.
  4. Fetch restaurants (15 results) — single fetch_places call.
  5. Build OpenAI client: openai.OpenAI(api_key=OPENAI_API_KEY)
  6. Build system_prompt via build_system_prompt(trip_context)
  7. visited_ids = set()
  8. accumulated_activity_cost = 0
  9. For each day (0 to num_days-1):
       a. daily_budget = allocate_daily_budget(...)
       b. if daily_budget <= 0: append empty DayPlan, continue
       c. unvisited_pois = [p for p in attractions if p["place_id"] not in visited_ids]
       d. user_prompt = build_user_prompt(day_context, unvisited_pois + restaurants, visited_ids)
       e. raw_response = plan_day(system_prompt, user_prompt, openai_client)
       f. schedule = parse_ai_response(raw_response)
       g. day_cost = sum(entry["cost"] for entry in schedule)
       h. accumulated_activity_cost += day_cost
       i. visited_ids |= {e["place_id"] for e in schedule if e["category"] == "Attraction"}
       j. Build DayPlan from schedule entries.
  10. Build and return ItineraryResponse.
  ```

- [ ] Remove `from core.optimizer import optimize_schedule` import.
- [ ] Add imports: `from core.ai_planner import build_system_prompt, build_user_prompt, plan_day, parse_ai_response`
- [ ] Add imports: `from core.budget import reserve_hotel_budget, allocate_daily_budget, check_within_budget`
- [ ] Remove `_extract_coords` helper from `app.py` if it's no longer used.
- [ ] Ensure `_build_day_plan` correctly maps AI schedule entries to `ItineraryEntry` objects.

### Tests

- [ ] Update `tests/test_api.py`:
  - Mock `app_module.plan_day` to return a sample schedule dict.
  - Keep existing mocks for `fetch_places`, `fetch_travel_time`.
  - Remove any mock for `optimize_schedule`.
  - All existing test assertions (budget respected, no duplicates, correct dates) must still pass.

```bash
pytest tests/test_api.py -v
```

### Success Criteria

- `app.py` no longer imports from `core.optimizer`.
- `build_itinerary()` uses `plan_day()` for every day's schedule.
- All `test_api.py` tests pass.
- Server starts and `/health` returns 200.

---

## Phase 6 — Update Pydantic Schemas

### Objective
Add new fields to the response schema to surface AI-generated content to the frontend.

### Tasks

- [ ] Open `models/schemas.py`.
- [ ] Add `ai_justification: str | None = None` to `ItineraryEntry`.
- [ ] Add `day_summary: str | None = None` to `DayPlan`.
- [ ] Add `meal_type` validation — it already exists, but confirm it accepts `"Breakfast"`, `"Lunch"`, `"Dinner"`, and `None`.
- [ ] Confirm `theme`, `travel_type`, and `budget_tier` remain plain strings (no enum needed for MVP).
- [ ] Run a quick schema import test:
  ```bash
  python -c "from models.schemas import ItineraryResponse; print('OK')"
  ```

### Tests

- [ ] Add two test cases to `tests/test_ai_planner.py`:
  - Confirm `ItineraryEntry` accepts `ai_justification` without error.
  - Confirm `DayPlan` accepts `day_summary` without error.

### Success Criteria

- `ItineraryEntry` has `ai_justification`.
- `DayPlan` has `day_summary`.
- No schema validation errors when building a full `ItineraryResponse`.

---

## Phase 7 — Update the Frontend

### Objective
Surface the new AI-generated fields (justification, day summary) in the existing demo UI.
No redesign — minimal additions only.

### Tasks

- [ ] Open `static/index.html`.
- [ ] In the day-rendering section, add display of `day.day_summary` below the day header.
- [ ] In the itinerary-entry rendering section, add display of `entry.ai_justification` as a small italic line below the entry details.
- [ ] Ensure `escapeHtml()` is applied to both new fields before rendering.
- [ ] Visually test in a browser: submit a request and confirm justifications appear.

### Tests

Manual verification:
- [ ] Submit a trip request from the browser.
- [ ] Confirm day summary appears on each day card.
- [ ] Confirm AI justification appears on each itinerary entry.
- [ ] Confirm no raw HTML or script injection is possible (escapeHtml is applied).

### Success Criteria

- `day_summary` is visible in the rendered day card.
- `ai_justification` is visible under each entry.
- Page still renders correctly when fields are null/missing.

---

## Phase 8 — Full Test Suite Pass

### Objective
All tests green before attempting a live end-to-end run.

### Tasks

- [ ] Run the complete test suite:
  ```bash
  pytest tests/ -v
  ```
- [ ] Fix any failures before proceeding.
- [ ] Confirm the following test files all pass:
  - `tests/test_filter.py` — hotel ranking (unchanged logic, should still pass).
  - `tests/test_budget.py` — budget module (new).
  - `tests/test_ai_planner.py` — AI planner with mocked OpenAI (new).
  - `tests/test_api.py` — integration test with mocked providers and mocked OpenAI.
- [ ] Confirm `tests/test_optimizer.py` either passes (if kept as legacy) or is deleted and replaced by `test_ai_planner.py`.

### Success Criteria

```
pytest tests/ -v
# All tests PASSED. No failures. No errors.
```

---

## Phase 9 — Live End-to-End Validation

### Objective
Run a real request against live Google Maps and OpenAI APIs and verify the output is correct.

### Tasks

- [ ] Ensure `.env` has both valid API keys.
- [ ] Start the server: `uvicorn app:app --reload --port 8000`
- [ ] Send a test request:
  ```bash
  curl -X POST http://localhost:8000/api/generate-itinerary \
    -H "Content-Type: application/json" \
    -d '{
      "city": "Mysuru",
      "trip_start_date": "2025-08-10",
      "num_days": 2,
      "num_people": 2,
      "theme": "Historical",
      "travel_type": "Couple",
      "budget_tier": "Medium",
      "total_budget": 8000
    }'
  ```
- [ ] Inspect the JSON response and verify:
  - [ ] `hotel` block is present with name, rating, cost_per_night.
  - [ ] `days` has 2 entries.
  - [ ] Each day has at least 3 itinerary entries (attractions + meals).
  - [ ] `ai_justification` is non-empty on every entry.
  - [ ] No attraction `place_id` appears in both days.
  - [ ] `summary.within_budget` is `true`.
- [ ] Also verify the browser frontend at `http://localhost:8000/static/index.html` renders the full result.
- [ ] Check server logs: confirm no Google Place Details call is made more than once per place.

### Success Criteria

- Valid JSON response from the live endpoint.
- At least one meal per day.
- No duplicate attractions.
- AI justification present on all entries.
- Total cost ≤ total_budget.

---

## Phase 10 — CLI Validation and Cleanup

### Objective
Confirm the CLI runner works with the new architecture. Clean up dead code.

### Tasks

- [ ] Run the CLI:
  ```bash
  python main.py --city Mysuru --days 2 --people 2 --theme Historical \
    --travel_type Couple --budget_tier Medium --total_budget 8000
  ```
- [ ] Confirm the CLI prints a readable itinerary to stdout.
- [ ] Delete or archive `core/optimizer.py` (replaced by `core/ai_planner.py`).
- [ ] Delete `wanderwise_itinerary.json` and `final_itinerary.json` from repo root (stale artifacts).
- [ ] Delete duplicate `AGENTS.md`, `ALGORITHM.md`, `PLAN.md` from repo root — keep only the copies in `docs/`.
- [ ] Remove `data/api_dump.json` if it is not referenced anywhere in code.
- [ ] Run `pytest tests/ -v` once more after cleanup to confirm nothing broke.

### Success Criteria

- CLI prints a full multi-day itinerary without errors.
- `core/optimizer.py` no longer exists (or is clearly marked as deprecated).
- Repo root is clean — no duplicate docs, no stale JSON outputs.
- Full test suite still passes after cleanup.

---

## Phase 11 — Final Documentation Update

### Objective
Update `docs/` to reflect the new system accurately.

### Tasks

- [ ] Update `docs/AGENTS.md` — confirm it matches the final system (this file was generated for the new system).
- [ ] Update `docs/PLAN.md` — this file.
- [ ] Create or update `docs/ALGORITHM.md`:
  - Describe the new AI-based planning approach.
  - Document the OpenAI prompt schema (system prompt structure, user prompt variables, expected JSON schema).
  - Document budget flow (hotel reservation → daily allocation → within-budget check).
  - Document the hotel selection logic (kept from original: rating × 20 − euclidean distance × 1000).
  - Note what the old greedy optimizer did and why it was replaced.
- [ ] Update `README.md` (if present) or create one with:
  - Project description.
  - Setup instructions (venv, `.env`, run commands).
  - API endpoint documentation.
  - Example request/response.

### Success Criteria

- `docs/` is the single source of truth for all documentation.
- `docs/ALGORITHM.md` accurately describes the AI planning approach.
- A new developer can read `docs/` and understand the entire system without reading the code first.

---

## Phase 12 — Handoff Verification Checklist

### Final verification before marking the rebuild complete.

- [ ] `pytest tests/ -v` → all green.
- [ ] `uvicorn app:app --reload` → server starts with no errors.
- [ ] `GET /health` → `{"status": "ok"}`.
- [ ] `POST /api/generate-itinerary` with live keys → valid response.
- [ ] Browser at `/static/index.html` → full itinerary renders with AI justifications.
- [ ] `python main.py` → itinerary prints to CLI.
- [ ] No `requests` import anywhere (replaced by `httpx`).
- [ ] No `_merge_place_details` call anywhere.
- [ ] No `optimize_schedule` import anywhere.
- [ ] `OPENAI_API_KEY` loaded from `.env` only.
- [ ] `docs/` contains: `AGENTS.md`, `PLAN.md`, `ALGORITHM.md`.
- [ ] Repo root does not contain duplicate docs or stale JSON artifacts.

---

## Quick Reference — New File Map

```
Pitch/
├── .env                          # GOOGLE_MAPS_API_KEY + OPENAI_API_KEY
├── .env.example                  # Updated with both keys
├── app.py                        # Refactored orchestration (no optimizer, uses ai_planner)
├── main.py                       # CLI runner (unchanged interface, updated imports)
├── requirements.txt              # + openai, + httpx
├── core/
│   ├── __init__.py
│   ├── ai_planner.py             # NEW — OpenAI integration
│   ├── budget.py                 # NEW — Budget arithmetic
│   └── filter.py                 # KEPT — hotel ranking only
├── models/
│   ├── __init__.py
│   └── schemas.py                # + ai_justification, + day_summary fields
├── providers/
│   ├── __init__.py
│   └── google_maps.py            # FIXED — no double fetch, httpx, error handling
├── static/
│   └── index.html                # UPDATED — shows justification + day summary
├── tests/
│   ├── __init__.py
│   ├── test_ai_planner.py        # NEW
│   ├── test_budget.py            # NEW
│   ├── test_filter.py            # KEPT (hotel ranking tests)
│   └── test_api.py               # UPDATED — mocks plan_day instead of optimize_schedule
└── docs/
    ├── AGENTS.md
    ├── PLAN.md
    └── ALGORITHM.md
```

---

*This plan was generated for the WanderWise AI Rebuild. Follow phases in order. Do not proceed to the next phase until the current phase's success criteria are met.*
