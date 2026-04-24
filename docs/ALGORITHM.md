# WanderWise Algorithm Documentation

## 1. What This Project Does

This project generates a day itinerary (and supports a two-day flow in the CLI script) using Google Maps data, user preferences, time limits, and budget limits.

The system:
1. Collects places, hotels, and restaurants from Google Maps APIs.
2. Scores and ranks hotels and places.
3. Builds a time-ordered schedule that respects opening hours, travel time, and total budget.
4. Returns a JSON itinerary with timing and cost.


## 2. Main Components

- Entry API layer: app.py
  - Exposes POST /api/generate-itinerary.
  - Parses user input and triggers planning.

- CLI runner: main.py
  - Demonstrates a two-day planning flow.
  - Prints itinerary and total expenditure.

- Data provider: providers/google_maps.py
  - Wraps Google Maps Places/Place Details/Distance Matrix calls.
  - Enriches places with image URLs.

- Scoring engine: core/filter.py
  - Computes preference-aware scores for POIs.
  - Ranks hotels by rating and geographic centrality.
  - Estimates cost using price-level maps.

- Optimizer: core/optimizer.py
  - Builds final schedule using a greedy, constraint-aware selection loop.


## 3. End-to-End Flow

### API flow (app.py)

1. Read request body fields:
   - city, theme, budget, people, total_budget
2. Fetch sample POIs and hotel candidates.
3. Choose the best hotel using hotel ranking.
4. Fetch full POI list and restaurants.
5. Rank POIs by wanderwise_score.
6. Estimate hotel cost (2 nights in current implementation).
7. Build schedule from start time to deadline.
8. Return JSON with hotel + itinerary + cost summary.

### CLI flow (main.py)

1. Hardcoded preferences for Mysuru.
2. Select hotel once.
3. Run optimizer for day 1 and day 2.
4. Keep a running total cost across days.


## 4. Algorithms Used

## 4.1 POI Scoring Algorithm (Weighted Rule-Based Ranking)

Implemented in core/filter.py -> rank_places.

For each POI:

- Base score: rating * 10
- Theme bonus: +50 if POI type matches selected theme map
- Budget penalty: -40 if user budget is low and POI price_level > 2

Final score:

score = (rating * 10) + theme_bonus - budget_penalty

POIs are sorted descending by this score.

Interpretation:
- This is a deterministic, weighted heuristic ranking algorithm.
- It is not machine learning; it is a transparent rule-based scorer.


## 4.2 Hotel Selection Algorithm (Centrality + Rating Heuristic)

Implemented in core/filter.py -> rank_hotels.

Steps:
1. Compute centroid of top sample POIs:
   - avg_lat = mean(poi_lat)
   - avg_lng = mean(poi_lng)
2. For each hotel:
   - rating component = rating * 20
   - distance penalty = euclidean_distance(hotel, centroid) * 1000
   - hotel_score = rating component - distance penalty
3. Select max hotel_score.

Interpretation:
- This is a greedy best-candidate heuristic.
- It balances quality (rating) and expected travel convenience (central location).


## 4.3 Schedule Optimization Algorithm (Greedy First-Feasible)

Implemented in core/optimizer.py -> optimize_schedule.

This is the core itinerary algorithm.

Loop while current time < day deadline:
1. If it is lunch window (hour >= 13) and lunch not taken:
   - Insert first restaurant.
   - Add lunch duration and cost.
   - Continue.
2. Otherwise scan ranked POIs in order and pick the first POI that satisfies all constraints:
   - Not already visited.
   - Arrival time computed using live travel minutes from Distance Matrix.
   - Open at arrival time.
   - Adding this POI cost keeps total <= total_budget.
   - Visit duration fits before deadline.
3. Append selected POI to itinerary.
4. Advance current time/location/cost.
5. Mark POI visited.
6. Stop if no feasible POI exists.

Why this works:
- Ranked list gives preference quality order.
- First-feasible selection gives speed and predictability.
- Constraints enforce practical schedules.

Important note:
- This is a greedy optimizer, not a global optimum solver.
- It does not use TSP, dynamic programming, or mixed-integer programming.


## 5. Constraints Enforced During Planning

- Time window: start_time -> deadline
- Opening hours: checked per POI period/day/time
- Travel time: fetched from Google Distance Matrix
- Budget cap: running_cost + candidate_cost <= user total_budget
- No duplicates: visited place_id set
- Lunch insertion: one lunch slot after 1 PM


## 6. Cost Model

In core/filter.py -> get_item_cost:

- POI/meal cost from price_level map and people count
- Hotel cost from separate hotel_price_map
- Lunch uses fixed per-person estimate in current logic

Current maps:
- price_map: {0: 0, 1: 300, 2: 700, 3: 1500, 4: 3000}
- hotel_price_map: {0: 0, 1: 2500, 2: 5000, 3: 10000, 4: 20000}


## 7. Complexity (High Level)

Let n = number of ranked POIs.

- POI ranking: O(n log n) due to sorting.
- Hotel ranking: O(h) where h = number of hotels.
- Scheduling loop:
  - In worst case scans POI list repeatedly.
  - Upper bound roughly O(n^2) in a day when many candidates become infeasible late.

For small n (around 10 to 30), this is fast and practical.


## 8. Practical Characteristics

Strengths:
- Fast response and simple explainable logic.
- Integrates real travel times and opening hours.
- Budget and timing constraints are explicit.

Limitations:
- Greedy first-feasible may miss better global routes.
- Uses Euclidean distance for hotel centrality (not road network distance).
- Lunch currently always picks first restaurant.
- Depends on external API quality and quota.


## 9. Output Shape

Primary API output includes:
- hotel object
- itinerary array with:
  - location_name
  - arrival_time
  - departure_time
  - image_url
  - cost
- summary with:
  - total_cost
  - budget_limit


## 10. In One Line

This project uses a weighted heuristic ranking + greedy first-feasible schedule construction algorithm under time, opening-hours, travel-time, and budget constraints to generate a practical itinerary.