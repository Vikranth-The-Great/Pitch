# AGENTS.md — WanderWise: Practical Travel Itinerary Generator

> This file is the primary guide for AI coding agents (Copilot, Cursor, Codex, etc.) working on WanderWise.
> Read this file fully before writing any code. Follow every instruction precisely.

---

## Project Overview

WanderWise is a backend-first travel itinerary generation system.

Given a destination city, trip dates, number of people, budget, and personalization preferences,
the system fetches real places from Google Maps APIs, scores and ranks them, selects the best hotel,
and constructs a practical day-by-day schedule that respects opening hours, travel time, and budget constraints.

The algorithm is fixed and must not be changed. See `docs/ALGORITHM.md` for the complete algorithm specification.

---

## Business Requirements

### Inputs the system must accept

| Field            | Description                                                       |
|------------------|-------------------------------------------------------------------|
| city             | Destination city (e.g., Mysuru)                                   |
| trip_start_date  | ISO date string — used to check day-of-week opening hours         |
| num_days         | Number of trip days — controls nearby hub expansion               |
| num_people       | Number of travellers — used for cost calculations                 |
| theme            | One of: Historical, Devotional, Adventure, Entertainment          |
| travel_type      | One of: Solo, Couple, Friends, Family                             |
| budget_tier      | One of: Low, Medium, High                                         |
| total_budget     | Maximum spend in INR (integer)                                    |

### Output the system must return

For each day the system must return:

- Recommended hotel (name, address, rating, estimated cost per night, image URL)
- Ordered itinerary entries:
  - location_name
  - arrival_time
  - departure_time
  - travel_time_from_previous (minutes)
  - cost (INR, per group)
  - image_url
  - category (Attraction / Restaurant / Hotel)
  - meal_type (if applicable: Breakfast / Lunch / Dinner)
- Daily cost summary
- Total trip cost summary vs budget cap

### Functional constraints

- Opening hours must be validated against the actual day of the week derived from trip_start_date
- Travel time between locations must be fetched from Google Distance Matrix API
- Budget cap must be strictly enforced — no itinerary entry may cause running_cost to exceed total_budget
- No place may appear twice across the full itinerary
- Lunch must be inserted after 13:00 on each day
- Breakfast and dinner slots are nice-to-have if budget and time allow

---

## Technical Stack

| Layer         | Technology                              |
|---------------|-----------------------------------------|
| Language      | Python 3.11+                            |
| API Framework | FastAPI                                 |
| HTTP Client   | httpx (async) or requests (sync)        |
| Google APIs   | Places API, Place Details API, Distance Matrix API |
| Config        | python-dotenv (.env file)               |
| Validation    | Pydantic v2 (request/response models)  |
| Testing       | pytest                                  |
| Serialization | JSON (built-in)                         |
| CLI Runner    | Python argparse or plain script         |

> No database is required for MVP. All data is fetched live from Google Maps APIs per request.
> No frontend framework is required. A simple HTML file with fetch() is sufficient for demo purposes.

---

## Project Structure

```
wanderwise/
├── app.py                  # FastAPI entry point — POST /api/generate-itinerary
├── main.py                 # CLI runner for local testing
├── .env                    # API keys (never commit this)
├── .env.example            # Template for environment variables
├── requirements.txt        # Python dependencies
├── docs/
│   ├── ALGORITHM.md        # Fixed algorithm reference — do not modify
│   ├── AGENTS.md           # This file
│   └── PLAN.md             # Phase-by-phase execution plan
├── core/
│   ├── filter.py           # POI scoring, hotel ranking, cost estimation
│   └── optimizer.py        # Greedy schedule construction
├── providers/
│   └── google_maps.py      # All Google Maps API wrappers
├── models/
│   └── schemas.py          # Pydantic request/response models
└── tests/
    ├── test_filter.py
    ├── test_optimizer.py
    └── test_api.py
```

---

## Implementation Strategy

Follow this order strictly. Do not skip steps.

### Step 1 — Environment Setup
- Create the project directory structure above
- Create `.env.example` with `GOOGLE_MAPS_API_KEY=your_key_here`
- Create `requirements.txt` with: fastapi, uvicorn, requests, python-dotenv, pydantic

### Step 2 — Google Maps Provider (`providers/google_maps.py`)
- Implement `fetch_places(city, place_type, limit)` using Places API
- Implement `fetch_place_details(place_id)` to get opening hours and image reference
- Implement `fetch_travel_time(origin_lat, origin_lng, dest_lat, dest_lng, departure_time)` using Distance Matrix API
- Implement `build_image_url(photo_reference)` to return a usable image URL
- All functions must return plain Python dicts

### Step 3 — Scoring Engine (`core/filter.py`)
Implement exactly as specified in `docs/ALGORITHM.md`. Do not deviate.

- `rank_places(places, theme, budget_tier)` — weighted score: `(rating * 10) + theme_bonus - budget_penalty`
- `rank_hotels(hotels, poi_centroid)` — score: `(rating * 20) - (euclidean_distance * 1000)`
- `get_item_cost(price_level, people, category)` — use fixed price_map and hotel_price_map from ALGORITHM.md

### Step 4 — Optimizer (`core/optimizer.py`)
Implement exactly as specified in `docs/ALGORITHM.md`. Do not deviate.

- `optimize_schedule(ranked_pois, restaurants, hotel, start_time, deadline, total_budget, people, date, fetch_travel_time_fn)`
- Loop greedily: check lunch window → scan ranked POIs → pick first feasible → advance state
- Return list of itinerary entries with arrival_time, departure_time, travel_time_from_previous, cost

### Step 5 — API Layer (`app.py`)
- FastAPI app with `POST /api/generate-itinerary`
- Parse request using Pydantic model
- Orchestrate: fetch → rank → select hotel → build schedule → return JSON
- Add `GET /health` endpoint returning `{"status": "ok"}`

### Step 6 — CLI Runner (`main.py`)
- Accept arguments or use hardcoded defaults for quick local testing
- Print per-day itinerary and total expenditure to stdout

### Step 7 — Tests (`tests/`)
- Unit test `rank_places` with mock POI data
- Unit test `rank_hotels` with mock hotel + centroid data
- Unit test `optimize_schedule` with mocked travel-time function
- Integration test the `/api/generate-itinerary` endpoint with a mock Google Maps provider

---

## Coding Standards

- Keep every function short and single-purpose
- Use type hints on all function signatures
- Use Pydantic models for all API request and response shapes
- Never hardcode API keys — always load from `.env`
- Return plain dicts or Pydantic models from all functions — no custom class hierarchies
- Do not add authentication, databases, caching, or queues to the MVP
- Do not build a complex frontend — a minimal HTML page with a form and fetch() is enough
- All planning and working documents live in the `docs/` directory
- Follow the algorithm in `docs/ALGORITHM.md` exactly — no modifications to scoring logic or optimizer loop

---

## Environment Variables

```
GOOGLE_MAPS_API_KEY=your_google_maps_api_key_here
```

---

## Running the Application

```bash
# Install dependencies
pip install -r requirements.txt

# Start API server
uvicorn app:app --reload --port 8000

# Run CLI demo
python main.py

# Run tests
pytest tests/
```

---

## API Contract

### POST /api/generate-itinerary

**Request Body:**
```json
{
  "city": "Mysuru",
  "trip_start_date": "2025-08-10",
  "num_days": 2,
  "num_people": 2,
  "theme": "Historical",
  "travel_type": "Couple",
  "budget_tier": "Medium",
  "total_budget": 8000
}
```

**Response:**
```json
{
  "hotel": {
    "name": "Hotel Example",
    "address": "...",
    "rating": 4.2,
    "cost_per_night": 5000,
    "image_url": "https://..."
  },
  "days": [
    {
      "day": 1,
      "date": "2025-08-10",
      "itinerary": [
        {
          "location_name": "Mysore Palace",
          "category": "Attraction",
          "arrival_time": "09:00",
          "departure_time": "11:00",
          "travel_time_from_previous": 15,
          "cost": 700,
          "image_url": "https://..."
        },
        {
          "location_name": "Hotel Dasaprakash",
          "category": "Restaurant",
          "meal_type": "Lunch",
          "arrival_time": "13:00",
          "departure_time": "14:00",
          "travel_time_from_previous": 10,
          "cost": 400,
          "image_url": "https://..."
        }
      ],
      "day_cost": 3200
    }
  ],
  "summary": {
    "total_cost": 6400,
    "budget_limit": 8000,
    "within_budget": true
  }
}
```

---

## Notes for AI Coding Agents

- The algorithm in `docs/ALGORITHM.md` is the source of truth for `core/filter.py` and `core/optimizer.py`
- Do not introduce ML models, LLMs, or external ranking services
- Do not change scoring weights or optimizer loop logic
- When in doubt, refer to `docs/ALGORITHM.md` and `docs/PLAN.md`
- Complete one phase at a time and verify tests before moving to the next phase
