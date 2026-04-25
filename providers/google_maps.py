from __future__ import annotations

from datetime import datetime, date
import os
from typing import Any

import httpx
from dotenv import load_dotenv

load_dotenv()

GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY", "")
GOOGLE_MAPS_BASE_URL = "https://maps.googleapis.com/maps/api"


def _require_api_key() -> str:
    api_key = GOOGLE_MAPS_API_KEY.strip()
    if not api_key:
        raise RuntimeError("GOOGLE_MAPS_API_KEY is not configured. Set it in the .env file before using Google Maps APIs.")
    return api_key


def _request_json(url: str, params: dict[str, Any]) -> dict[str, Any]:
    with httpx.Client() as client:
        response = client.get(url, params=params, timeout=20)
        response.raise_for_status()
        return response.json()


def _extract_lat_lng(payload: dict[str, Any]) -> tuple[float | None, float | None]:
    location = payload.get("geometry", {}).get("location", {})
    return location.get("lat"), location.get("lng")


def _time_to_minutes(raw_time: Any) -> int | None:
    value = str(raw_time or "")
    if len(value) != 4 or not value.isdigit():
        return None
    return (int(value[:2]) * 60 + int(value[2:])) % (24 * 60)


def build_image_url(photo_reference: str | None, max_width: int = 400) -> str:
    """Return a Google Places photo URL, or a placeholder when no photo exists."""
    if not photo_reference:
        return "https://via.placeholder.com/400x200?text=No+Image"
    api_key = _require_api_key()
    return (
        f"{GOOGLE_MAPS_BASE_URL}/place/photo?"
        f"maxwidth={max_width}&photoreference={photo_reference}&key={api_key}"
    )


def fetch_place_details(place_id: str) -> dict[str, Any]:
    """Fetch rich details for a single place (opening hours, photos, address)."""
    try:
        api_key = _require_api_key()
        response = _request_json(
            f"{GOOGLE_MAPS_BASE_URL}/place/details/json",
            {
                "place_id": place_id,
                "fields": "name,rating,price_level,geometry,opening_hours,photos,formatted_address,types",
                "key": api_key,
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
    except Exception as e:
        print(f"Error fetching details for {place_id}: {e}")
        return {"place_id": place_id, "name": "Unknown Place", "rating": 0}


def fetch_places(city: str, place_type: str, limit: int) -> list[dict[str, Any]]:
    """Search for places in a city by type and return enriched place dicts."""
    try:
        api_key = _require_api_key()
        response = _request_json(
            f"{GOOGLE_MAPS_BASE_URL}/place/textsearch/json",
            {
                "query": f"{place_type} in {city}",
                "key": api_key,
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
    except Exception as e:
        print(f"Error fetching places for {city} ({place_type}): {e}")
        return []


def fetch_travel_time(
    origin_lat: float,
    origin_lng: float,
    dest_lat: float,
    dest_lng: float,
    departure_time: int | datetime,
) -> int:
    """Return driving time in minutes between two coordinates."""
    if isinstance(departure_time, datetime):
        departure_epoch = int(departure_time.timestamp())
    elif isinstance(departure_time, date):
        # Convert date to datetime at midnight
        departure_epoch = int(datetime.combine(departure_time, datetime.min.time()).timestamp())
    else:
        departure_epoch = int(departure_time)

    try:
        api_key = _require_api_key()
        response = _request_json(
            f"{GOOGLE_MAPS_BASE_URL}/distancematrix/json",
            {
                "origins": f"{origin_lat},{origin_lng}",
                "destinations": f"{dest_lat},{dest_lng}",
                "mode": "driving",
                "departure_time": departure_epoch,
                "key": api_key,
            },
        )
        element = response["rows"][0]["elements"][0]
        if element.get("status") != "OK":
            return 15
        return max(1, int(round(element["duration"]["value"] / 60)))
    except Exception:
        return 15


def is_open_at(opening_periods: list[Any] | None, target_datetime: datetime) -> bool:
    """Return True if a place is open at the given datetime."""
    if not opening_periods:
        return True

    weekday = target_datetime.weekday()
    current_minutes = target_datetime.hour * 60 + target_datetime.minute

    for period in opening_periods:
        open_info = period.get("open", {})
        close_info = period.get("close", {})

        open_day = open_info.get("day")
        if open_day is None:
            continue

        close_day = close_info.get("day", open_day)
        open_minutes = _time_to_minutes(open_info.get("time", "0000"))
        close_minutes = _time_to_minutes(close_info.get("time", "2359")) if close_info else (24 * 60 - 1)
        if open_minutes is None or close_minutes is None:
            continue

        if open_day == close_day:
            if weekday == open_day and open_minutes <= current_minutes < close_minutes:
                return True
            continue

        if weekday == open_day and current_minutes >= open_minutes:
            return True
        if weekday == close_day and current_minutes < close_minutes:
            return True

    return False
