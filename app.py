from __future__ import annotations

import os
from datetime import datetime, time, timedelta
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from openai import OpenAI

from core.filter import get_item_cost, rank_hotels, rank_places
from core.budget import reserve_hotel_budget, allocate_daily_budget, check_within_budget
from core.ai_planner import build_system_prompt, build_user_prompt, plan_day, parse_ai_response
from models.schemas import DayPlan, HotelResponse, ItineraryEntry, ItineraryRequest, ItineraryResponse, SummaryResponse
from providers.google_maps import fetch_places, fetch_travel_time, build_image_url


app = FastAPI(title="WanderWise")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load OpenAI Client
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
openai_client = OpenAI(api_key=OPENAI_API_KEY)

STATIC_DIR = Path(__file__).resolve().parent / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def _build_day_plan(
    day_index: int,
    trip_date,
    schedule: list[dict[str, object]],
    day_summary: str | None = None
) -> DayPlan:
    day_cost = int(sum(int(entry.get("cost", 0)) for entry in schedule))
    entries = [ItineraryEntry(**entry) for entry in schedule]
    return DayPlan(
        day=day_index, 
        date=trip_date, 
        itinerary=entries, 
        day_cost=day_cost,
        day_summary=day_summary
    )


def build_itinerary(payload: ItineraryRequest) -> ItineraryResponse:
    if not OPENAI_API_KEY:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY not configured")

    # 1. Fetch Candidates
    # Fetch a wider pool for better variety across multiple days
    hotel_candidates = fetch_places(payload.city, "lodging", 10)
    if not hotel_candidates:
        raise HTTPException(status_code=502, detail="No hotel candidates returned by provider")

    sample_pois = fetch_places(payload.city, "tourist_attraction", 10)
    best_hotel = rank_hotels(hotel_candidates, sample_pois)
    
    hotel_cost_per_night = get_item_cost(
        best_hotel.get("price_level"), 
        payload.num_people, 
        "hotel", 
        best_hotel.get("types")
    )
    hotel_total_cost = reserve_hotel_budget(hotel_cost_per_night, payload.num_days)

    # Fetch more candidates to ensure variety
    attractions = fetch_places(payload.city, "tourist_attraction", 30)
    restaurants = fetch_places(payload.city, "restaurant", 25)

    for p in attractions:
        p["estimated_cost"] = get_item_cost(
            p.get("price_level"), 
            payload.num_people, 
            "attraction", 
            p.get("types")
        )
    for r in restaurants:
        r["estimated_cost"] = get_item_cost(
            r.get("price_level"), 
            payload.num_people, 
            "restaurant", 
            r.get("types")
        )

    # 2. Planning Orchestration
    trip_context = {
        "city": payload.city,
        "theme": payload.theme,
        "travel_type": payload.travel_type,
        "num_people": payload.num_people,
        "budget_tier": payload.budget_tier
    }
    system_prompt = build_system_prompt(trip_context)
    
    days: list[DayPlan] = []
    accumulated_activity_cost = 0
    visited_ids: set[str] = set()

    for day_number in range(payload.num_days):
        day_index = day_number + 1
        trip_date = payload.trip_start_date + timedelta(days=day_number)
        
        daily_budget = allocate_daily_budget(
            payload.total_budget,
            hotel_total_cost,
            accumulated_activity_cost,
            payload.num_days,
            day_number,
        )

        if daily_budget <= 0:
            days.append(_build_day_plan(day_index, trip_date, [], "Total budget limit reached."))
            continue

        day_context = {
            "day_number": day_index,
            "date": str(trip_date),
            "remaining_budget": daily_budget
        }
        
        user_prompt = build_user_prompt(day_context, attractions + restaurants, visited_ids)
        
        raw_response = plan_day(system_prompt, user_prompt, openai_client)
        schedule = parse_ai_response(raw_response)
        
        processed_schedule = []
        current_lat, current_lng = best_hotel.get("lat"), best_hotel.get("lng")
        day_running_cost = 0

        for entry in schedule:
            pid = entry.get("place_id")
            source_place = next((p for p in attractions + restaurants if p.get("place_id") == pid), {})
            
            if not source_place:
                continue 

            cost = int(entry.get("cost", source_place.get("estimated_cost", 300)))
            
            # BUDGET GUARD
            if day_running_cost + cost > daily_budget:
                continue

            dest_lat, dest_lng = source_place.get("lat"), source_place.get("lng")
            travel_time = 0
            if current_lat and current_lng and dest_lat and dest_lng:
                travel_time = fetch_travel_time(current_lat, current_lng, dest_lat, dest_lng, trip_date)
            
            entry["travel_time_from_previous"] = travel_time
            entry["image_url"] = entry.get("image_url") or source_place.get("image_url", "")
            entry["cost"] = cost
            
            processed_schedule.append(entry)
            
            # Update state
            day_running_cost += cost
            current_lat, current_lng = dest_lat, dest_lng
            # Mark ALL scheduled places as visited to avoid duplicates (meals and attractions)
            if pid:
                visited_ids.add(str(pid))

        accumulated_activity_cost += day_running_cost
        days.append(_build_day_plan(day_index, trip_date, processed_schedule, raw_response.get("day_summary")))

    response_total_cost = int(hotel_total_cost + accumulated_activity_cost)
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
            within_budget=check_within_budget(response_total_cost, payload.total_budget),
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
