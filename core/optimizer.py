from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Callable

from core.filter import get_item_cost
from providers.google_maps import is_open_at


def _extract_coords(place: dict[str, Any]) -> tuple[float, float]:
    if "lat" in place and "lng" in place:
        return float(place.get("lat", 0.0)), float(place.get("lng", 0.0))

    location = place.get("geometry", {}).get("location", {})
    return float(location.get("lat", 0.0)), float(location.get("lng", 0.0))


def _opening_periods(place: dict[str, Any]) -> list[dict[str, Any]] | None:
    opening_hours = place.get("opening_hours")
    if isinstance(opening_hours, dict):
        periods = opening_hours.get("periods")
        return periods if isinstance(periods, list) else None
    if isinstance(opening_hours, list):
        return opening_hours
    return None


def _place_id(place: dict[str, Any]) -> str:
    return str(place.get("place_id") or place.get("id") or place.get("name") or "")


def _format_time(value: datetime) -> str:
    return value.strftime("%H:%M")


def optimize_schedule(
    ranked_pois: list[dict[str, Any]],
    restaurants: list[dict[str, Any]],
    hotel: dict[str, Any],
    start_time: datetime,
    deadline: datetime,
    total_budget: int,
    people: int,
    target_date: date,
    fetch_travel_time_fn: Callable[[float, float, float, float, int], int],
    visited_ids: set[str] | None = None,
) -> list[dict[str, Any]]:
    """Greedily build a single day's itinerary (docs/ALGORITHM.md §5).

    Parameters
    ----------
    ranked_pois:
        POIs pre-sorted by wanderwise_score (descending).
    restaurants:
        Candidate restaurants; the first feasible one is used for lunch.
    hotel:
        Selected hotel dict — used as the day's starting coordinates.
    start_time:
        Day start (typically 09:00 local).
    deadline:
        Hard cutoff (typically 20:00 local).
    total_budget:
        Remaining INR budget for this day's activities.
    people:
        Number of travellers (for cost calculation).
    target_date:
        The calendar date being planned — needed for opening-hour checks.
    fetch_travel_time_fn:
        Callable(origin_lat, origin_lng, dest_lat, dest_lng, departure_epoch) -> minutes.
    visited_ids:
        Shared set across days; mutated in-place to prevent repeating places.
    """
    itinerary: list[dict[str, Any]] = []
    active_visited_ids = visited_ids if visited_ids is not None else set()
    current_time = datetime.combine(target_date, start_time.time())
    day_deadline = datetime.combine(target_date, deadline.time())
    current_lat, current_lng = _extract_coords(hotel)
    running_cost = 0
    lunch_taken = False

    while current_time < day_deadline:
        # --- Lunch insertion ---
        if current_time.hour >= 13 and not lunch_taken:
            lunch = restaurants[0] if restaurants else None
            if lunch is not None:
                lunch_lat, lunch_lng = _extract_coords(lunch)
                travel_minutes = fetch_travel_time_fn(
                    current_lat,
                    current_lng,
                    lunch_lat,
                    lunch_lng,
                    int(current_time.timestamp()),
                )
                arrival_time = current_time + timedelta(minutes=travel_minutes)
                lunch_duration = int(lunch.get("visit_duration_minutes", 60) or 60)
                lunch_cost = get_item_cost(lunch.get("price_level"), people, "restaurant")

                if (
                    arrival_time < day_deadline
                    and arrival_time + timedelta(minutes=lunch_duration) <= day_deadline
                    and running_cost + lunch_cost <= total_budget
                    and is_open_at(_opening_periods(lunch), arrival_time)
                ):
                    departure_time = arrival_time + timedelta(minutes=lunch_duration)
                    itinerary.append(
                        {
                            "place_id": _place_id(lunch),
                            "location_name": lunch.get("name", "Lunch"),
                            "category": "Restaurant",
                            "meal_type": "Lunch",
                            "arrival_time": _format_time(arrival_time),
                            "departure_time": _format_time(departure_time),
                            "travel_time_from_previous": travel_minutes,
                            "cost": lunch_cost,
                            "image_url": lunch.get("image_url", ""),
                        }
                    )
                    current_time = departure_time + timedelta(minutes=15)
                    current_lat, current_lng = lunch_lat, lunch_lng
                    running_cost += lunch_cost
                    lunch_taken = True
                    continue

            lunch_taken = True

        # --- POI selection (greedy first-feasible) ---
        selected_poi: dict[str, Any] | None = None
        selected_travel_minutes = 0
        selected_cost = 0
        selected_duration = 0

        for poi in ranked_pois:
            poi_id = _place_id(poi)
            if not poi_id or poi_id in active_visited_ids:
                continue

            poi_lat, poi_lng = _extract_coords(poi)
            travel_minutes = fetch_travel_time_fn(
                current_lat,
                current_lng,
                poi_lat,
                poi_lng,
                int(current_time.timestamp()),
            )
            arrival_time = current_time + timedelta(minutes=travel_minutes)
            poi_duration = int(poi.get("visit_duration_minutes", 90) or 90)
            poi_cost = get_item_cost(poi.get("price_level"), people, "attraction")

            if not is_open_at(_opening_periods(poi), arrival_time):
                continue
            if running_cost + poi_cost > total_budget:
                continue
            if arrival_time + timedelta(minutes=poi_duration) > day_deadline:
                continue

            selected_poi = poi
            selected_travel_minutes = travel_minutes
            selected_cost = poi_cost
            selected_duration = poi_duration
            break

        if selected_poi is None:
            break

        arrival_time = current_time + timedelta(minutes=selected_travel_minutes)
        departure_time = arrival_time + timedelta(minutes=selected_duration)
        itinerary.append(
            {
                "place_id": _place_id(selected_poi),
                "location_name": selected_poi.get("name", "Unknown"),
                "category": "Attraction",
                "arrival_time": _format_time(arrival_time),
                "departure_time": _format_time(departure_time),
                "travel_time_from_previous": selected_travel_minutes,
                "cost": selected_cost,
                "image_url": selected_poi.get("image_url", ""),
            }
        )
        active_visited_ids.add(_place_id(selected_poi))
        current_time = departure_time + timedelta(minutes=15)
        current_lat, current_lng = _extract_coords(selected_poi)
        running_cost += selected_cost

    return itinerary