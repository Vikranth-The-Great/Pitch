from __future__ import annotations

from math import sqrt
from typing import Any

THEME_MAP: dict[str, list[str]] = {
    "Historical": ["museum", "hindu_temple", "church", "mosque", "tourist_attraction"],
    "Devotional": ["hindu_temple", "church", "mosque", "place_of_worship"],
    "Adventure": ["park", "natural_feature", "campground", "zoo", "amusement_park"],
    "Entertainment": ["amusement_park", "zoo", "movie_theater", "shopping_mall", "night_club"],
}

PRICE_MAP = {0: 0, 1: 300, 2: 700, 3: 1500, 4: 3000}
HOTEL_PRICE_MAP = {0: 0, 1: 2500, 2: 5000, 3: 10000, 4: 20000}


def _normalize_theme(theme: str | None) -> str:
    if not theme:
        return "Historical"
    normalized = theme.strip().lower()
    for key in THEME_MAP:
        if key.lower() == normalized:
            return key
    return theme if theme in THEME_MAP else "Historical"


def _normalize_budget_tier(budget_tier: str | None) -> str:
    if not budget_tier:
        return "Medium"
    return budget_tier.strip().title()


def _poi_lat_lng(poi: dict[str, Any]) -> tuple[float, float]:
    if "lat" in poi and "lng" in poi:
        return float(poi["lat"]), float(poi["lng"])
    geometry = poi.get("geometry", {}).get("location", {})
    return float(geometry.get("lat", 0.0)), float(geometry.get("lng", 0.0))


def rank_places(places: list[dict[str, Any]], theme: str, budget_tier: str) -> list[dict[str, Any]]:
    """Score and sort POIs using the WanderWise weighted heuristic.

    Formula (from docs/ALGORITHM.md):
        score = (rating * 10) + theme_bonus - budget_penalty
    where:
        theme_bonus  = 50 if the POI type matches the requested theme, else 0
        budget_penalty = 40 if budget_tier == "Low" and price_level > 2, else 0
    """
    selected_theme = _normalize_theme(theme)
    selected_budget_tier = _normalize_budget_tier(budget_tier)
    theme_types = THEME_MAP.get(selected_theme, [])

    scored_places: list[dict[str, Any]] = []
    for place in places:
        rating = float(place.get("rating", 0) or 0)
        price_level = place.get("price_level", 0)
        types = place.get("types", []) or []

        base_score = rating * 10
        theme_bonus = 50 if any(place_type in theme_types for place_type in types) else 0
        budget_penalty = 40 if selected_budget_tier == "Low" and (price_level or 0) > 2 else 0
        score = base_score + theme_bonus - budget_penalty

        ranked_place = dict(place)
        ranked_place["wanderwise_score"] = score
        scored_places.append(ranked_place)

    return sorted(scored_places, key=lambda item: item["wanderwise_score"], reverse=True)


def rank_hotels(hotels: list[dict[str, Any]], sample_pois: list[dict[str, Any]]) -> dict[str, Any]:
    """Select the best hotel using centrality scoring (from docs/ALGORITHM.md).

    Formula:
        hotel_score = (rating * 20) - (euclidean_distance_to_poi_centroid * 1000)
    """
    if not hotels:
        raise ValueError("hotels must not be empty")
    if not sample_pois:
        return dict(hotels[0])

    avg_lat = sum(_poi_lat_lng(poi)[0] for poi in sample_pois) / len(sample_pois)
    avg_lng = sum(_poi_lat_lng(poi)[1] for poi in sample_pois) / len(sample_pois)

    ranked_hotels: list[dict[str, Any]] = []
    for hotel in hotels:
        hotel_lat, hotel_lng = _poi_lat_lng(hotel)
        distance = sqrt((hotel_lat - avg_lat) ** 2 + (hotel_lng - avg_lng) ** 2)
        hotel_score = (float(hotel.get("rating", 0) or 0) * 20) - (distance * 1000)

        ranked_hotel = dict(hotel)
        ranked_hotel["hotel_score"] = hotel_score
        ranked_hotels.append(ranked_hotel)

    best_hotel = max(ranked_hotels, key=lambda item: item["hotel_score"])
    best_hotel.setdefault(
        "justification",
        f"Picked for its {best_hotel.get('rating', 0)} rating and proximity to the center of your planned activities.",
    )
    return best_hotel


def get_item_cost(price_level: int | None, people: int, category: str) -> int:
    """Return the estimated INR cost for a visit.

    Uses fixed price maps from docs/ALGORITHM.md:
        PRICE_MAP       = {0: 0, 1: 300, 2: 700, 3: 1500, 4: 3000}   (per person)
        HOTEL_PRICE_MAP = {0: 0, 1: 2500, 2: 5000, 3: 10000, 4: 20000} (flat/night)

    Defaults price_level to 1 when None.
    """
    normalized_price_level = 1 if price_level is None else int(price_level)
    normalized_category = (category or "").strip().lower()

    if normalized_category == "hotel":
        return HOTEL_PRICE_MAP.get(normalized_price_level, HOTEL_PRICE_MAP[1])

    return PRICE_MAP.get(normalized_price_level, PRICE_MAP[1]) * people