from __future__ import annotations

from datetime import datetime
import os
from typing import Any

import requests
from dotenv import load_dotenv

load_dotenv()

GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY", "")
GOOGLE_MAPS_BASE_URL = "https://maps.googleapis.com/maps/api"


def _request_json(url: str, params: dict[str, Any]) -> dict[str, Any]:
    response = requests.get(url, params=params, timeout=20)
    response.raise_for_status()
    return response.json()


def _extract_lat_lng(payload: dict[str, Any]) -> tuple[float | None, float | None]:
    location = payload.get("geometry", {}).get("location", {})
    return location.get("lat"), location.get("lng")


def build_image_url(photo_reference: str | None, max_width: int = 400) -> str:
    """Return a Google Places photo URL, or a placeholder when no photo exists."""
    if not photo_reference:
        return "https://via.placeholder.com/400x200?text=No+Image"
    return (
        f"{GOOGLE_MAPS_BASE_URL}/place/photo?"
        f"maxwidth={max_width}&photoreference={photo_reference}&key={GOOGLE_MAPS_API_KEY}"
    )


def fetch_place_details(place_id: str) -> dict[str, Any]:
    """Fetch rich details for a single place (opening hours, photos, address)."""
    response = _request_json(
        f"{GOOGLE_MAPS_BASE_URL}/place/details/json",
        {
            "place_id": place_id,
            "fields": "name,rating,price_level,geometry,opening_hours,photos,formatted_address,types",
            "key": GOOGLE_MAPS_API_KEY,
        },
    )
    result = response.get("result", {})
    photos = result.get("photos") or []
    photo_reference = photos[0].get("photo_reference") if photos else None
    lat, lng = _extract_lat_lng(result)
    return {
        "place_id": place_id,
        "name": result.get("name"),
        "rating": result.get("rating", 0),
        "price_level": result.get("price_level"),
        "geometry": result.get("geometry", {}),
        "lat": lat,
        "lng": lng,
        "opening_hours": result.get("opening_hours", {}).get("periods"),
        "photos": photos,
        "photo_reference": photo_reference,
        "formatted_address": result.get("formatted_address"),
        "types": result.get("types", []),
        "image_url": build_image_url(photo_reference),
        "address": result.get("formatted_address"),
    }


def fetch_places(city: str, place_type: str, limit: int) -> list[dict[str, Any]]:
    """Search for places in a city by type and return enriched place dicts."""
    response = _request_json(
        f"{GOOGLE_MAPS_BASE_URL}/place/textsearch/json",
        {
            "query": f"{place_type} in {city}",
            "key": GOOGLE_MAPS_API_KEY,
        },
    )

    results: list[dict[str, Any]] = []
    for item in response.get("results", [])[:limit]:
        place_id = item.get("place_id")
        if not place_id:
            continue

        details = fetch_place_details(place_id)
        lat, lng = _extract_lat_lng(item)
        details_lat, details_lng = details.get("lat"), details.get("lng")
        photos = details.get("photos") or item.get("photos") or []
        photo_reference = photos[0].get("photo_reference") if photos else None

        results.append(
            {
                "place_id": place_id,
                "name": details.get("name") or item.get("name"),
                "rating": details.get("rating", item.get("rating", 0)),
                "price_level": details.get("price_level", item.get("price_level")),
                "lat": details_lat if details_lat is not None else lat,
                "lng": details_lng if details_lng is not None else lng,
                "types": details.get("types", item.get("types", [])),
                "opening_hours": details.get("opening_hours"),
                "address": details.get("formatted_address", item.get("formatted_address")),
                "photo_reference": photo_reference,
                "image_url": build_image_url(photo_reference),
            }
        )

    return results


def fetch_travel_time(
    origin_lat: float,
    origin_lng: float,
    dest_lat: float,
    dest_lng: float,
    departure_time: int | datetime,
) -> int:
    """Return driving time in minutes between two coordinates.

    Falls back to 15 minutes if the Distance Matrix API returns an error
    or if the network call fails.
    """
    departure_epoch = int(departure_time.timestamp()) if isinstance(departure_time, datetime) else int(departure_time)

    try:
        response = _request_json(
            f"{GOOGLE_MAPS_BASE_URL}/distancematrix/json",
            {
                "origins": f"{origin_lat},{origin_lng}",
                "destinations": f"{dest_lat},{dest_lng}",
                "mode": "driving",
                "departure_time": departure_epoch,
                "key": GOOGLE_MAPS_API_KEY,
            },
        )
        element = response["rows"][0]["elements"][0]
        if element.get("status") != "OK":
            return 15
        return max(1, int(round(element["duration"]["value"] / 60)))
    except Exception:
        return 15


def is_open_at(opening_periods: list[Any] | None, target_datetime: datetime) -> bool:
    """Return True if a place is open at the given datetime.

    Uses the ``periods`` array from the Place Details API.
    Returns True when opening_periods is None (place assumed open 24 h).
    """
    if not opening_periods:
        return True

    weekday = target_datetime.weekday()
    current_minutes = target_datetime.hour * 60 + target_datetime.minute

    for period in opening_periods:
        open_info = period.get("open", {})
        close_info = period.get("close", {})
        if open_info.get("day") != weekday:
            continue

        open_time = str(open_info.get("time", "0000"))
        close_time = str(close_info.get("time", "2359")) if close_info else "2359"
        if len(open_time) != 4 or len(close_time) != 4:
            continue

        open_minutes = int(open_time[:2]) * 60 + int(open_time[2:])
        close_minutes = int(close_time[:2]) * 60 + int(close_time[2:])
        if open_minutes <= current_minutes < close_minutes:
            return True

    return False