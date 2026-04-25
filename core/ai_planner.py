from __future__ import annotations
import json
import os
from typing import Any
from openai import OpenAI

OPENAI_MODEL = "gpt-4o"

def build_system_prompt(trip_context: dict[str, Any]) -> str:
    """Constructs the system prompt with the role and JSON schema."""
    return f"""You are a professional travel planner for WanderWise. 
Your goal is to construct a coherent, high-quality day-by-day travel itinerary.

Trip Profile:
- City: {trip_context.get('city')}
- Theme: {trip_context.get('theme')}
- Travel Type: {trip_context.get('travel_type')}
- Travelers: {trip_context.get('num_people')}
- Budget Tier: {trip_context.get('budget_tier')}

Instructions:
1. You must return ONLY a valid JSON object. No conversational text.
2. Schedule activities between 08:00 and 22:00.
3. MANDATORY MEALS: 
   - Breakfast: ~08:00
   - Lunch: ~13:00 
   - Dinner: ~19:00 (MUST be labeled "Dinner", not "Lunch")
4. VARIETY IS CRITICAL: 
   - Do not pick the same restaurant twice.
   - Do not pick different branches of the same brand (e.g., "Kareem's Kitchen") on the same day. 
   - Try to provide diverse culinary experiences.
5. For every entry, provide a short 'ai_justification' (one sentence).
6. STRICT BUDGET RULE: Stay within the 'remaining_budget' for the day. 
7. LOGICAL SEQUENCE: Group nearby places together to minimize travel.

Required JSON Schema:
{{
  "schedule": [
    {{
      "place_id": "string",
      "location_name": "string",
      "category": "Attraction | Restaurant",
      "meal_type": "Breakfast | Lunch | Dinner | null",
      "arrival_time": "HH:MM",
      "departure_time": "HH:MM",
      "cost": number,
      "ai_justification": "string"
    }}
  ],
  "day_summary": "string"
}}
"""

def build_user_prompt(day_context: dict[str, Any], places: list[dict[str, Any]], visited_ids: set[str]) -> str:
    """Constructs the user prompt with day-specific context and candidates."""
    compact_places = []
    for p in places:
        pid = p.get("place_id")
        if pid in visited_ids:
            continue
        compact_places.append({
            "place_id": pid,
            "name": p.get("name"),
            "rating": p.get("rating"),
            "types": p.get("types", [])[:3],
            "cost": p.get("estimated_cost", 300),
            "address": p.get("address")
        })

    return f"""Plan Day {day_context.get('day_number')} ({day_context.get('date')}).
MAX ACTIVITY BUDGET FOR THIS DAY: Rs {day_context.get('remaining_budget')}

Candidate Places:
{json.dumps(compact_places, indent=2)}

Already Visited IDs:
{list(visited_ids)}

Generate the JSON schedule for this day. Include Breakfast, Lunch, and Dinner. Avoid repeating brands."""

def plan_day(system_prompt: str, user_prompt: str, openai_client: OpenAI) -> dict[str, Any]:
    """Calls OpenAI API to generate a day's plan."""
    try:
        response = openai_client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            response_format={"type": "json_object"},
            max_tokens=2000,
            temperature=0.7
        )
        content = response.choices[0].message.content
        if not content:
            raise ValueError("Empty response from OpenAI")
        return json.loads(content)
    except Exception as e:
        print(f"OpenAI Planning Error: {e}")
        return {"schedule": [], "day_summary": f"Could not plan this day due to an error: {str(e)}"}

def parse_ai_response(raw: dict[str, Any]) -> list[dict[str, Any]]:
    """Extracts and validates the schedule from AI response."""
    schedule = raw.get("schedule")
    if isinstance(schedule, list):
        return schedule
    return []
