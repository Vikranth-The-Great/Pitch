# PLAN.md — WanderWise Execution Plan

> This is the single source of truth for development execution.
> AI coding agents must implement one phase at a time, run all tests, verify success criteria, then proceed.
> Never skip a phase. Never implement the next phase until the current phase passes all success criteria.

---

## Project Summary

WanderWise generates a practical, multi-day travel itinerary for a given city using Google Maps APIs,
a weighted heuristic POI scoring algorithm, a centrality-based hotel selection algorithm,
and a greedy first-feasible schedule optimizer.

The algorithm is fixed and documented in `docs/ALGORITHM.md`. Do not modify it.

---

## Phase Overview

| Phase | Name                        | Key Output                              |
|-------|-----------------------------|-----------------------------------------|
| 1     | Project Setup               | Repo structure, env config, deps        |
| 2     | Google Maps Provider        | Live API wrappers working               |
| 3     | Scoring Engine              | rank_places and rank_hotels working     |
| 4     | Cost Model                  | get_item_cost working                   |
| 5     | Schedule Optimizer          | optimize_schedule working               |
| 6     | API Layer                   | POST /api/generate-itinerary live       |
| 7     | CLI Runner                  | main.py demo working end-to-end         |
| 8     | Multi-Day Support           | num_days loop across days               |
| 9     | Unit Tests                  | All core logic tested                   |
| 10    | Integration Tests           | Full API flow tested with mocks         |
| 11    | Demo Frontend               | Minimal HTML form hitting the API       |
| 12    | Final Review & Cleanup      | Code clean, docs updated, ready to demo |

---

## Phase 1 — Project Setup

### Objective
Create the project skeleton with correct directory structure, dependencies, and environment configuration.

### Tasks
- [ ] Create the following directory structure:
  ```
  wanderwise/
  ├── app.py
  ├── main.py
  ├── requirements.txt
  ├── .env.example
  ├── docs/
  │   ├── ALGORITHM.md
  │   ├── AGENTS.md
  │   └── PLAN.md
  ├── core/
  │   ├── __init__.py
  │   ├── filter.py
  │   └── optimizer.py
  ├── providers/
  │   ├── __init__.py
  │   └── google_maps.py
  ├── models/
  │   ├── __init__.py
  │   └── schemas.py
  └── tests/
      ├── __init__.py
      ├── test_filter.py
      ├── test_optimizer.py
      └── test_api.py
  ```
- [ ] Create `requirements.txt` containing:
  ```
  fastapi
  uvicorn
  requests
  python-dotenv
  pydantic
  pytest
  httpx
  ```
- [ ] Create `.env.example`:
  ```
  GOOGLE_MAPS_API_KEY=your_google_maps_api_key_here
  ```
- [ ] Create `.env` locally with a real key (never commit this file)
- [ ] Add `.env` to `.gitignore`
- [ ] Create empty `__init__.py` files in `core/`, `providers/`, `models/`, `tests/`
- [ ] Copy `ALGORITHM.md` into `docs/ALGORITHM.md`
- [ ] Install dependencies: `pip install -r requirements.txt`

### Test
```bash
python -c "import fastapi, pydantic, requests, dotenv; print('All imports OK')"
```

### Success Criteria
- All directories and files exist
- `pip install -r requirements.txt` completes without errors
- Import test passes

---

## Phase 2 — Google Maps Provider

### Objective
Implement all Google Maps API wrappers in `providers/google_maps.py`.

### Tasks
- [ ] Load `GOOGLE_MAPS_API_KEY` from `.env` using `python-dotenv`
- [ ] Implement `fetch_places(city: str, place_type: str, limit: int) -> list[dict]`
  - Uses Google Places API (Text Search or Nearby Search)
  - Returns list of dicts with: place_id, name, rating, price_level, lat, lng, types
- [ ] Implement `fetch_place_details(place_id: str) -> dict`
  - Uses Google Place Details API
  - Returns: opening_hours (periods), photo_reference, address, price_level
- [ ] Implement `fetch_travel_time(origin_lat, origin_lng, dest_lat, dest_lng, departure_epoch: int) -> int`
  - Uses Google Distance Matrix API
  - Returns travel time in minutes
  - Falls back to 15 minutes if API fails or quota exceeded
- [ ] Implement `build_image_url(photo_reference: str, max_width: int = 400) -> str`
  - Returns a Google Places photo URL string
- [ ] Implement `is_open_at(opening_periods: list, target_datetime) -> bool`
  - Checks if a place is open at a given datetime using the periods array from Place Details

### Test
```python
# Manual smoke test (requires real API key)
from providers.google_maps import fetch_places
places = fetch_places("Mysuru", "tourist_attraction", 5)
assert len(places) > 0
assert "place_id" in places[0]
print("Provider smoke test passed")
```

### Success Criteria
- `fetch_places("Mysuru", "tourist_attraction", 5)` returns at least 3 results
- `fetch_travel_time(...)` returns an integer (minutes)
- `is_open_at(...)` returns True or False correctly for a known open place

---

## Phase 3 — Scoring Engine

### Objective
Implement `rank_places` and `rank_hotels` in `core/filter.py` exactly as defined in `docs/ALGORITHM.md`.

### Tasks

#### rank_places
- [ ] Implement `rank_places(places: list[dict], theme: str, budget_tier: str) -> list[dict]`
- [ ] Define theme_map mapping each theme to a list of Google place types:
  - Historical: ["museum", "hindu_temple", "church", "mosque", "tourist_attraction"]
  - Devotional: ["hindu_temple", "church", "mosque", "place_of_worship"]
  - Adventure: ["park", "natural_feature", "campground", "zoo", "amusement_park"]
  - Entertainment: ["amusement_park", "zoo", "movie_theater", "shopping_mall", "night_club"]
- [ ] Apply scoring formula exactly:
  ```
  base_score = rating * 10
  theme_bonus = 50 if any(t in theme_map[theme] for t in poi["types"]) else 0
  budget_penalty = 40 if budget_tier == "Low" and poi.get("price_level", 0) > 2 else 0
  score = base_score + theme_bonus - budget_penalty
  ```
- [ ] Sort POIs descending by score
- [ ] Attach `wanderwise_score` field to each POI dict

#### rank_hotels
- [ ] Implement `rank_hotels(hotels: list[dict], sample_pois: list[dict]) -> dict`
- [ ] Compute centroid of top sample POIs:
  ```python
  avg_lat = mean(poi["lat"] for poi in sample_pois)
  avg_lng = mean(poi["lng"] for poi in sample_pois)
  ```
- [ ] For each hotel compute:
  ```python
  from math import sqrt
  distance = sqrt((hotel["lat"] - avg_lat)**2 + (hotel["lng"] - avg_lng)**2)
  hotel_score = (hotel["rating"] * 20) - (distance * 1000)
  ```
- [ ] Return the hotel dict with the highest `hotel_score`

### Test (`tests/test_filter.py`)
```python
def test_rank_places_theme_bonus():
    pois = [
        {"name": "Palace", "rating": 4.0, "price_level": 1, "types": ["tourist_attraction"]},
        {"name": "Mall", "rating": 4.5, "price_level": 3, "types": ["shopping_mall"]},
    ]
    ranked = rank_places(pois, theme="Historical", budget_tier="Medium")
    assert ranked[0]["name"] == "Palace"  # theme bonus pushes it ahead

def test_rank_hotels_centrality():
    hotels = [
        {"name": "Central Hotel", "rating": 4.0, "lat": 12.30, "lng": 76.65},
        {"name": "Far Hotel",     "rating": 4.5, "lat": 12.50, "lng": 77.00},
    ]
    sample_pois = [{"lat": 12.30, "lng": 76.65}]
    best = rank_hotels(hotels, sample_pois)
    assert best["name"] == "Central Hotel"
```

### Success Criteria
- `test_rank_places_theme_bonus` passes
- `test_rank_hotels_centrality` passes
- Scores match the formula from `docs/ALGORITHM.md` exactly

---

## Phase 4 — Cost Model

### Objective
Implement `get_item_cost` in `core/filter.py` using the fixed price maps from `docs/ALGORITHM.md`.

### Tasks
- [ ] Implement `get_item_cost(price_level: int, people: int, category: str) -> int`
- [ ] Use these maps exactly (do not change values):
  ```python
  price_map       = {0: 0, 1: 300, 2: 700, 3: 1500, 4: 3000}
  hotel_price_map = {0: 0, 1: 2500, 2: 5000, 3: 10000, 4: 20000}
  ```
- [ ] If `category == "hotel"`, use `hotel_price_map[price_level]` (flat, not per-person)
- [ ] Otherwise use `price_map[price_level] * people`
- [ ] Default `price_level` to 1 if None or missing

### Test (`tests/test_filter.py`)
```python
def test_get_item_cost_attraction():
    cost = get_item_cost(price_level=2, people=2, category="attraction")
    assert cost == 1400  # 700 * 2

def test_get_item_cost_hotel():
    cost = get_item_cost(price_level=2, people=2, category="hotel")
    assert cost == 5000  # flat rate from hotel_price_map
```

### Success Criteria
- Both cost tests pass
- Default fallback for None price_level does not raise an exception

---

## Phase 5 — Schedule Optimizer

### Objective
Implement `optimize_schedule` in `core/optimizer.py` exactly as defined in `docs/ALGORITHM.md`.

### Tasks
- [ ] Implement `optimize_schedule(ranked_pois, restaurants, hotel, start_time, deadline, total_budget, people, target_date, fetch_travel_time_fn) -> list[dict]`
- [ ] Maintain state: `current_time`, `current_lat`, `current_lng`, `running_cost`, `visited_ids`
- [ ] Implement greedy loop:
  ```
  while current_time < deadline:
      if current_time.hour >= 13 and not lunch_taken:
          insert restaurant as lunch slot
          advance time and cost
          set lunch_taken = True
          continue
      for poi in ranked_pois:
          if poi already visited: skip
          travel_minutes = fetch_travel_time_fn(current_lat, current_lng, poi.lat, poi.lng, departure_epoch)
          arrival = current_time + timedelta(minutes=travel_minutes)
          if not is_open_at(poi.opening_hours, arrival): skip
          poi_cost = get_item_cost(poi.price_level, people, "attraction")
          if running_cost + poi_cost > total_budget: skip
          visit_duration = poi.get("visit_duration_minutes", 90)
          if arrival + timedelta(minutes=visit_duration) > deadline: skip
          # feasible — add to itinerary
          append entry with arrival_time, departure_time, travel_time_from_previous, cost
          advance current_time, current_lat, current_lng, running_cost
          mark poi visited
          break
      else:
          break  # no feasible POI found — stop
  return itinerary
  ```
- [ ] Each itinerary entry dict must include:
  - location_name, category, arrival_time (HH:MM), departure_time (HH:MM), travel_time_from_previous (int minutes), cost (int INR), image_url

### Test (`tests/test_optimizer.py`)
```python
def mock_travel_fn(olat, olng, dlat, dlng, epoch):
    return 10  # always 10 minutes

def test_optimize_schedule_basic():
    pois = [
        {"place_id": "p1", "name": "Palace", "rating": 4.5, "price_level": 1,
         "lat": 12.30, "lng": 76.65, "types": ["tourist_attraction"],
         "opening_hours": None, "image_url": "", "visit_duration_minutes": 90},
    ]
    restaurants = [
        {"place_id": "r1", "name": "Dasaprakash", "price_level": 1,
         "lat": 12.31, "lng": 76.66, "image_url": ""},
    ]
    from datetime import datetime, timedelta
    start = datetime(2025, 8, 10, 9, 0)
    deadline = datetime(2025, 8, 10, 20, 0)
    result = optimize_schedule(pois, restaurants, {}, start, deadline, 5000, 2, start.date(), mock_travel_fn)
    assert len(result) >= 1
    assert result[0]["location_name"] == "Palace"
```

### Success Criteria
- Optimizer test passes with mock travel function
- Lunch is inserted after 13:00
- Budget cap is never exceeded in any returned itinerary
- No POI appears twice in the output list

---

## Phase 6 — API Layer

### Objective
Wire everything together in `app.py` as a FastAPI application.

### Tasks
- [ ] Define Pydantic request model `ItineraryRequest` in `models/schemas.py` with all 8 input fields
- [ ] Define Pydantic response models for hotel, itinerary entry, day plan, and summary
- [ ] Implement `GET /health` returning `{"status": "ok"}`
- [ ] Implement `POST /api/generate-itinerary`:
  1. Parse and validate request body
  2. Fetch sample POIs using `fetch_places(city, "tourist_attraction", 10)`
  3. Fetch hotel candidates using `fetch_places(city, "lodging", 10)`
  4. Enrich each hotel with place details
  5. Call `rank_hotels(hotels, sample_pois)` to select best hotel
  6. Fetch full POI list and restaurant list
  7. Enrich POIs with place details (opening hours, images)
  8. Call `rank_places(pois, theme, budget_tier)` to get ranked POIs
  9. Loop for `num_days`:
     - Compute `start_time` and `deadline` for that day (09:00 → 20:00)
     - Call `optimize_schedule(...)` for that day
     - Accumulate costs
  10. Return structured JSON response

### Test
```bash
uvicorn app:app --reload &
curl -X GET http://localhost:8000/health
# Expected: {"status": "ok"}
```

### Success Criteria
- `GET /health` returns `{"status": "ok"}` with HTTP 200
- `POST /api/generate-itinerary` with valid body returns a JSON response with `hotel`, `days`, and `summary` keys
- Response `summary.total_cost` never exceeds `total_budget` in the request

---

## Phase 7 — CLI Runner

### Objective
Implement `main.py` as a standalone CLI demo for rapid local testing without an HTTP client.

### Tasks
- [ ] Accept optional CLI arguments: `--city`, `--days`, `--people`, `--theme`, `--budget_tier`, `--total_budget`, `--start_date`
- [ ] Fall back to Mysuru defaults if no arguments provided
- [ ] Call the same core logic used by `app.py` (import and reuse, do not duplicate)
- [ ] Print each day's itinerary to stdout in a readable format:
  ```
  === Day 1 — 2025-08-10 ===
  Hotel: Hotel Roopa (Rating: 4.1) — ₹5000/night

  09:00 → 11:00  Mysore Palace           ₹700   [Travel: 0 min]
  11:10 → 12:40  Jaganmohan Palace       ₹300   [Travel: 10 min]
  13:00 → 14:00  LUNCH — Dasaprakash    ₹400   [Travel: 8 min]
  ...

  Day 1 Total: ₹3200
  ──────────────────────────────
  Trip Total:  ₹6100 / ₹8000 budget
  ```

### Test
```bash
python main.py --city Mysuru --days 1 --people 2 --theme Historical --budget_tier Medium --total_budget 5000 --start_date 2025-08-10
```

### Success Criteria
- CLI prints at least one attraction and one lunch entry
- Total cost printed is within `total_budget`
- No unhandled exceptions on valid input

---

## Phase 8 — Multi-Day Support

### Objective
Ensure the system correctly handles `num_days > 1`, advancing the date each day and never repeating places.

### Tasks
- [ ] Maintain a global `visited_ids` set across all days — pass it into each day's optimizer call
- [ ] Increment the date by 1 for each day (day 1 = `trip_start_date`, day 2 = `trip_start_date + 1 day`, etc.)
- [ ] Pass the correct date to `optimize_schedule` so opening hours are evaluated for the correct day of the week
- [ ] If `num_days > 1` and city is a known hub city (e.g., Mysuru), optionally include nearby attractions (e.g., Srirangapatna) on day 2 by fetching places for `"Srirangapatna"` as a secondary city
- [ ] Running cost accumulates across all days — enforce `total_budget` across the whole trip, not per day

### Test
```bash
python main.py --city Mysuru --days 2 --people 2 --theme Historical --budget_tier Medium --total_budget 8000 --start_date 2025-08-10
```

### Success Criteria
- Day 2 itinerary contains no place_ids that appeared in Day 1
- Dates increment correctly (Day 1: 2025-08-10, Day 2: 2025-08-11)
- Total cost across both days does not exceed `total_budget`

---

## Phase 9 — Unit Tests

### Objective
Write and run all unit tests for `core/filter.py` and `core/optimizer.py`.

### Tasks
- [ ] Complete `tests/test_filter.py`:
  - `test_rank_places_theme_bonus` (from Phase 3)
  - `test_rank_places_budget_penalty`
  - `test_rank_hotels_centrality` (from Phase 3)
  - `test_get_item_cost_attraction` (from Phase 4)
  - `test_get_item_cost_hotel` (from Phase 4)
  - `test_get_item_cost_default_price_level`
- [ ] Complete `tests/test_optimizer.py`:
  - `test_optimize_schedule_basic` (from Phase 5)
  - `test_optimize_schedule_lunch_inserted_after_1pm`
  - `test_optimize_schedule_budget_cap_respected`
  - `test_optimize_schedule_no_duplicates`

### Test
```bash
pytest tests/test_filter.py tests/test_optimizer.py -v
```

### Success Criteria
- All unit tests pass
- No test uses a real Google Maps API call — all external calls are mocked

---

## Phase 10 — Integration Tests

### Objective
Test the full API flow using FastAPI's test client with a mocked Google Maps provider.

### Tasks
- [ ] In `tests/test_api.py`, mock `providers.google_maps` to return fixture data
- [ ] Write `test_health_endpoint` — assert 200 and `{"status": "ok"}`
- [ ] Write `test_generate_itinerary_valid_request` — assert response has `hotel`, `days`, `summary`
- [ ] Write `test_generate_itinerary_budget_respected` — assert `summary.total_cost <= total_budget`
- [ ] Write `test_generate_itinerary_no_duplicate_places` — assert all place_ids in the itinerary are unique

### Test
```bash
pytest tests/test_api.py -v
```

### Success Criteria
- All integration tests pass without hitting real Google Maps APIs
- `summary.total_cost <= total_budget` assertion passes
- No duplicate place_ids in any response

---

## Phase 11 — Demo Frontend

### Objective
Build a minimal single HTML file that lets a user submit the itinerary form and see results — no framework needed.

### Tasks
- [ ] Create `static/index.html`
- [ ] Add a simple HTML form with fields matching all 8 inputs (city, start_date, num_days, num_people, theme dropdown, travel_type dropdown, budget_tier dropdown, total_budget)
- [ ] On form submit, call `POST /api/generate-itinerary` using `fetch()`
- [ ] Display results as a plain readable list: hotel name, then each day's itinerary entries with times and costs
- [ ] Mount the static directory in `app.py` using FastAPI's `StaticFiles`
- [ ] No CSS framework required — inline styles are acceptable

### Test
```
1. Open http://localhost:8000/static/index.html in a browser
2. Fill in: Mysuru, 2025-08-10, 1 day, 2 people, Historical, Couple, Medium, 5000
3. Click Generate
4. Verify itinerary appears on page
```

### Success Criteria
- Form renders in browser without errors
- Clicking Generate shows at least one attraction entry and one restaurant entry
- No JavaScript console errors on submit

---

## Phase 12 — Final Review and Cleanup

### Objective
Ensure the codebase is clean, documented, and ready to demo.

### Tasks
- [ ] Remove all debug `print()` statements from `core/` and `providers/` (keep them only in `main.py`)
- [ ] Ensure `.env` is listed in `.gitignore`
- [ ] Verify `docs/ALGORITHM.md` is unchanged from the original specification
- [ ] Verify `docs/AGENTS.md` matches the actual project structure
- [ ] Verify `docs/PLAN.md` matches the phases actually implemented
- [ ] Ensure `requirements.txt` lists only packages actually used
- [ ] Run the full test suite one final time:
  ```bash
  pytest tests/ -v
  ```
- [ ] Do a manual end-to-end demo run:
  ```bash
  python main.py --city Mysuru --days 2 --people 2 --theme Historical --budget_tier Medium --total_budget 8000 --start_date 2025-08-10
  ```
- [ ] Confirm the API response matches the contract defined in `docs/AGENTS.md`

### Success Criteria
- All tests pass
- Manual CLI demo runs without errors
- API returns correctly structured JSON
- No API keys are hardcoded anywhere in the source code
- Project is ready to demo or hand off to another developer

---

## Agent Execution Rules (Summary)

1. Read `docs/AGENTS.md` and `docs/ALGORITHM.md` before writing any code
2. Implement phases in order — Phase 1 through Phase 12
3. Run the listed tests after each phase before proceeding
4. Never modify the algorithm in `docs/ALGORITHM.md` or in `core/filter.py` / `core/optimizer.py`
5. Never skip a phase
6. Ask the user for review before beginning implementation if there is any ambiguity
