from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field


class ItineraryRequest(BaseModel):
    city: str
    trip_start_date: date
    num_days: int = Field(ge=1)
    num_people: int = Field(ge=1)
    theme: str
    travel_type: str
    budget_tier: str
    total_budget: int = Field(ge=0)


class HotelResponse(BaseModel):
    name: str
    address: str | None = None
    rating: float = 0
    cost_per_night: int
    image_url: str | None = None


class ItineraryEntry(BaseModel):
    place_id: str | None = None
    location_name: str
    category: str
    arrival_time: str
    departure_time: str
    travel_time_from_previous: int = 0
    cost: int
    image_url: str | None = None
    meal_type: str | None = None
    ai_justification: str | None = None


class DayPlan(BaseModel):
    day: int
    date: date
    itinerary: list[ItineraryEntry]
    day_cost: int
    day_summary: str | None = None


class SummaryResponse(BaseModel):
    total_cost: int
    budget_limit: int
    within_budget: bool


class ItineraryResponse(BaseModel):
    hotel: HotelResponse
    days: list[DayPlan]
    summary: SummaryResponse
