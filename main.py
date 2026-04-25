from __future__ import annotations

import argparse
from datetime import date

from app import build_itinerary
from models.schemas import ItineraryRequest


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a WanderWise itinerary demo")
    parser.add_argument("--city", default="Mysuru")
    parser.add_argument("--days", type=int, default=2)
    parser.add_argument("--people", type=int, default=2)
    parser.add_argument("--theme", default="Historical")
    parser.add_argument("--travel_type", default="Couple")
    parser.add_argument("--budget_tier", default="Medium")
    parser.add_argument("--total_budget", type=int, default=8000)
    parser.add_argument("--start_date", default="2025-08-10")
    return parser.parse_args()


def _format_day(day) -> None:
    print(f"\n=== Day {day.day} - {day.date} ===")
    for entry in day.itinerary:
        meal_label = f"{entry.meal_type.upper()} - " if entry.meal_type else ""
        print(
            f"{entry.arrival_time} -> {entry.departure_time}  {meal_label}{entry.location_name}"
            f"   Rs{entry.cost}   [Travel: {entry.travel_time_from_previous} min]"
        )
    print(f"Day {day.day} Total: Rs{day.day_cost}")


def run_wanderwise() -> None:
    args = _parse_args()
    payload = ItineraryRequest(
        city=args.city,
        trip_start_date=date.fromisoformat(args.start_date),
        num_days=args.days,
        num_people=args.people,
        theme=args.theme,
        travel_type=args.travel_type,
        budget_tier=args.budget_tier,
        total_budget=args.total_budget,
    )
    response = build_itinerary(payload)

    print(
        f"Hotel: {response.hotel.name} (Rating: {response.hotel.rating}) - Rs{response.hotel.cost_per_night}/night"
    )
    for day in response.days:
        _format_day(day)
    print(f"\nTrip Total: Rs{response.summary.total_cost} / Rs{response.summary.budget_limit} budget")


if __name__ == "__main__":
    run_wanderwise()
