from datetime import date

from fastapi.testclient import TestClient

import app as app_module

client = TestClient(app_module.app)


def _fake_places(city: str, place_type: str, limit: int):
	if place_type == "lodging":
		return [
			{
				"place_id": "hotel-1",
				"name": "Central Stay",
				"rating": 4.6,
				"price_level": 2,
				"lat": 12.30,
				"lng": 76.65,
				"types": ["lodging"],
				"opening_hours": None,
				"address": "1 Hotel Road",
				"image_url": "hotel-image",
			}
		]
	if place_type == "restaurant":
		return [
			{
				"place_id": "rest-1",
				"name": "Lunch House",
				"rating": 4.3,
				"price_level": 1,
				"lat": 12.31,
				"lng": 76.66,
				"types": ["restaurant"],
				"opening_hours": None,
				"address": "2 Food Street",
				"image_url": "restaurant-image",
			}
		]
	return [
		{
			"place_id": "poi-1",
			"name": "Mysore Palace",
			"rating": 4.8,
			"price_level": 1,
			"lat": 12.30,
			"lng": 76.65,
			"types": ["tourist_attraction"],
			"opening_hours": None,
			"address": "Palace Road",
			"image_url": "poi-image",
			"visit_duration_minutes": 90,
		},
		{
			"place_id": "poi-2",
			"name": "Jaganmohan Palace",
			"rating": 4.4,
			"price_level": 1,
			"lat": 12.31,
			"lng": 76.66,
			"types": ["tourist_attraction"],
			"opening_hours": None,
			"address": "Museum Road",
			"image_url": "poi-image-2",
			"visit_duration_minutes": 90,
		},
	][:limit]


def _fake_place_details(place_id: str):
	mapping = {
		"hotel-1": {
			"name": "Central Stay",
			"rating": 4.6,
			"price_level": 2,
			"lat": 12.30,
			"lng": 76.65,
			"types": ["lodging"],
			"opening_hours": None,
			"address": "1 Hotel Road",
			"image_url": "hotel-image",
		},
		"rest-1": {
			"name": "Lunch House",
			"rating": 4.3,
			"price_level": 1,
			"lat": 12.31,
			"lng": 76.66,
			"types": ["restaurant"],
			"opening_hours": None,
			"address": "2 Food Street",
			"image_url": "restaurant-image",
		},
		"poi-1": {
			"name": "Mysore Palace",
			"rating": 4.8,
			"price_level": 1,
			"lat": 12.30,
			"lng": 76.65,
			"types": ["tourist_attraction"],
			"opening_hours": None,
			"address": "Palace Road",
			"image_url": "poi-image",
			"visit_duration_minutes": 90,
		},
		"poi-2": {
			"name": "Jaganmohan Palace",
			"rating": 4.4,
			"price_level": 1,
			"lat": 12.31,
			"lng": 76.66,
			"types": ["tourist_attraction"],
			"opening_hours": None,
			"address": "Museum Road",
			"image_url": "poi-image-2",
			"visit_duration_minutes": 90,
		},
	}
	return mapping[place_id]


def _fake_travel_time(origin_lat, origin_lng, dest_lat, dest_lng, departure_epoch):
	return 10


def setup_module(module):
	app_module.fetch_places = _fake_places
	app_module.fetch_place_details = _fake_place_details
	app_module.fetch_travel_time = _fake_travel_time


def test_health_endpoint():
	response = client.get("/health")

	assert response.status_code == 200
	assert response.json() == {"status": "ok"}


def test_static_frontend_served():
	response = client.get("/static/index.html")

	assert response.status_code == 200
	assert "WanderWise demo planner" in response.text


def test_generate_itinerary_valid_request():
	response = client.post(
		"/api/generate-itinerary",
		json={
			"city": "Mysuru",
			"trip_start_date": "2025-08-10",
			"num_days": 1,
			"num_people": 2,
			"theme": "Historical",
			"travel_type": "Couple",
			"budget_tier": "Medium",
			"total_budget": 5000,
		},
	)

	body = response.json()
	assert response.status_code == 200
	assert set(body.keys()) == {"hotel", "days", "summary"}
	assert body["hotel"]["name"] == "Central Stay"
	assert len(body["days"]) == 1
	assert body["summary"]["total_cost"] <= 5000


def test_generate_itinerary_budget_respected():
	response = client.post(
		"/api/generate-itinerary",
		json={
			"city": "Mysuru",
			"trip_start_date": "2025-08-10",
			"num_days": 1,
			"num_people": 2,
			"theme": "Historical",
			"travel_type": "Couple",
			"budget_tier": "Medium",
			"total_budget": 5000,
		},
	)

	assert response.status_code == 200
	assert response.json()["summary"]["total_cost"] <= 5000


def test_generate_itinerary_no_duplicate_places():
	response = client.post(
		"/api/generate-itinerary",
		json={
			"city": "Mysuru",
			"trip_start_date": "2025-08-10",
			"num_days": 2,
			"num_people": 2,
			"theme": "Historical",
			"travel_type": "Couple",
			"budget_tier": "Medium",
			"total_budget": 8000,
		},
	)

	assert response.status_code == 200
	body = response.json()
	place_ids = [entry["place_id"] for day in body["days"] for entry in day["itinerary"] if entry.get("place_id")]
	assert len(place_ids) == len(set(place_ids))
	assert body["days"][0]["date"] == "2025-08-10"
	assert body["days"][1]["date"] == "2025-08-11"
