from __future__ import annotations

from datetime import datetime, time, timedelta
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from core.filter import get_item_cost, rank_hotels, rank_places
from core.optimizer import optimize_schedule
from models.schemas import DayPlan, HotelResponse, ItineraryEntry, ItineraryRequest, ItineraryResponse, SummaryResponse
from providers.google_maps import fetch_place_details, fetch_places, fetch_travel_time, build_image_url


app = FastAPI(title="WanderWise")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIC_DIR = Path(__file__).resolve().parent / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def _merge_place_details(place: dict[str, object]) -> dict[str, object]:
    place_id = str(place.get("place_id", ""))
    if not place_id:
        return dict(place)

    details = fetch_place_details(place_id)
    merged = dict(place)
    merged.update(
        {
            "name": details.get("name") or merged.get("name"),
            "rating": details.get("rating", merged.get("rating", 0)),
            "price_level": details.get("price_level", merged.get("price_level")),
            "lat": details.get("lat", merged.get("lat")),
            "lng": details.get("lng", merged.get("lng")),
            "types": details.get("types", merged.get("types", [])),
            "opening_hours": details.get("opening_hours", merged.get("opening_hours")),
            "address": details.get("address", merged.get("address")),
            "image_url": details.get("image_url", merged.get("image_url", build_image_url(details.get("photo_reference")))),
        }
    )
    return merged


def _extract_coords(place: dict[str, object]) -> tuple[float, float]:
    if "lat" in place and "lng" in place:
        return float(place.get("lat", 0.0)), float(place.get("lng", 0.0))
    geometry = place.get("geometry", {}).get("location", {})
    return float(geometry.get("lat", 0.0)), float(geometry.get("lng", 0.0))


def _build_day_plan(
    day_index: int,
    trip_date,
    itinerary: list[dict[str, object]],
) -> DayPlan:
    day_cost = int(sum(int(entry.get("cost", 0)) for entry in itinerary))
    entries = [ItineraryEntry(**entry) for entry in itinerary]
    return DayPlan(day=day_index, date=trip_date, itinerary=entries, day_cost=day_cost)


def build_itinerary(payload: ItineraryRequest) -> ItineraryResponse:
    sample_pois = [_merge_place_details(place) for place in fetch_places(payload.city, "tourist_attraction", 10)]
    hotel_candidates = [_merge_place_details(place) for place in fetch_places(payload.city, "lodging", 10)]
    if not hotel_candidates:
        raise HTTPException(status_code=502, detail="No hotel candidates returned by provider")

    best_hotel = rank_hotels(hotel_candidates, sample_pois)
    hotel_cost_per_night = get_item_cost(best_hotel.get("price_level"), payload.num_people, "hotel")
    hotel_total_cost = hotel_cost_per_night * payload.num_days

    poi_candidates = [_merge_place_details(place) for place in fetch_places(payload.city, "tourist_attraction", 20)]
    restaurants = [_merge_place_details(place) for place in fetch_places(payload.city, "restaurant", 10)]
    ranked_pois = rank_places(poi_candidates, payload.theme, payload.budget_tier)

    days: list[DayPlan] = []
    accumulated_trip_cost = hotel_total_cost
    visited_ids: set[str] = set()

    for day_number in range(payload.num_days):
        trip_date = payload.trip_start_date + timedelta(days=day_number)
        start_time = datetime.combine(trip_date, time(9, 0))
        deadline = datetime.combine(trip_date, time(20, 0))

        remaining_budget = max(0, payload.total_budget - accumulated_trip_cost)
        if remaining_budget == 0:
            days.append(_build_day_plan(day_number + 1, trip_date, []))
            continue

        filtered_pois = [poi for poi in ranked_pois if str(poi.get("place_id", "")) not in visited_ids]
        day_itinerary = optimize_schedule(
            filtered_pois,
            restaurants,
            best_hotel,
            start_time,
            deadline,
            remaining_budget,
            payload.num_people,
            trip_date,
            fetch_travel_time,
            visited_ids=visited_ids,
        )
        accumulated_trip_cost += sum(int(entry.get("cost", 0)) for entry in day_itinerary)
        days.append(_build_day_plan(day_number + 1, trip_date, day_itinerary))

    response_total_cost = int(accumulated_trip_cost)
    return ItineraryResponse(
        hotel=HotelResponse(
            name=str(best_hotel.get("name", "Unknown Hotel")),
            address=best_hotel.get("address"),
            rating=float(best_hotel.get("rating", 0) or 0),
            cost_per_night=hotel_cost_per_night,
            image_url=best_hotel.get("image_url"),
        ),
        days=days,
        summary=SummaryResponse(
            total_cost=response_total_cost,
            budget_limit=payload.total_budget,
            within_budget=response_total_cost <= payload.total_budget,
        ),
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/generate-itinerary", response_model=ItineraryResponse)
def generate_itinerary(payload: ItineraryRequest) -> ItineraryResponse:
    return build_itinerary(payload)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=False)