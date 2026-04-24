from datetime import datetime

from core.optimizer import optimize_schedule


def mock_travel_fn(origin_lat, origin_lng, dest_lat, dest_lng, departure_epoch):
	return 10


def test_optimize_schedule_basic():
	pois = [
		{
			"place_id": "p1",
			"name": "Palace",
			"rating": 4.5,
			"price_level": 1,
			"lat": 12.3,
			"lng": 76.65,
			"types": ["tourist_attraction"],
			"opening_hours": None,
			"image_url": "",
			"visit_duration_minutes": 90,
		}
	]
	restaurants = []
	hotel = {"lat": 12.29, "lng": 76.64}
	start = datetime(2025, 8, 10, 9, 0)
	deadline = datetime(2025, 8, 10, 20, 0)

	result = optimize_schedule(
		pois,
		restaurants,
		hotel,
		start,
		deadline,
		5000,
		2,
		start.date(),
		mock_travel_fn,
	)

	assert len(result) == 1
	assert result[0]["location_name"] == "Palace"
	assert result[0]["category"] == "Attraction"
	assert result[0]["travel_time_from_previous"] == 10
	assert result[0]["cost"] == 600


def test_optimize_schedule_inserts_lunch_after_13():
	pois = [
		{
			"place_id": "p1",
			"name": "Palace",
			"rating": 4.5,
			"price_level": 1,
			"lat": 12.3,
			"lng": 76.65,
			"types": ["tourist_attraction"],
			"opening_hours": None,
			"image_url": "",
			"visit_duration_minutes": 60,
		}
	]
	restaurants = [
		{
			"place_id": "r1",
			"name": "Dasaprakash",
			"price_level": 1,
			"lat": 12.31,
			"lng": 76.66,
			"opening_hours": None,
			"image_url": "",
			"visit_duration_minutes": 60,
		}
	]
	hotel = {"lat": 12.29, "lng": 76.64}
	start = datetime(2025, 8, 10, 13, 0)
	deadline = datetime(2025, 8, 10, 20, 0)

	result = optimize_schedule(
		pois,
		restaurants,
		hotel,
		start,
		deadline,
		5000,
		2,
		start.date(),
		mock_travel_fn,
	)

	assert result[0]["category"] == "Restaurant"
	assert result[0]["meal_type"] == "Lunch"
	assert result[0]["location_name"] == "Dasaprakash"


def test_optimize_schedule_skips_duplicate_places():
	pois = [
		{
			"place_id": "p1",
			"name": "Palace",
			"rating": 4.5,
			"price_level": 1,
			"lat": 12.3,
			"lng": 76.65,
			"types": ["tourist_attraction"],
			"opening_hours": None,
			"image_url": "",
			"visit_duration_minutes": 90,
		},
		{
			"place_id": "p1",
			"name": "Palace",
			"rating": 4.5,
			"price_level": 1,
			"lat": 12.3,
			"lng": 76.65,
			"types": ["tourist_attraction"],
			"opening_hours": None,
			"image_url": "",
			"visit_duration_minutes": 90,
		},
	]
	restaurants = []
	hotel = {"lat": 12.29, "lng": 76.64}
	start = datetime(2025, 8, 10, 9, 0)
	deadline = datetime(2025, 8, 10, 20, 0)

	result = optimize_schedule(
		pois,
		restaurants,
		hotel,
		start,
		deadline,
		5000,
		2,
		start.date(),
		mock_travel_fn,
	)

	assert [entry["location_name"] for entry in result].count("Palace") == 1


def test_optimize_schedule_budget_cap_respected():
	pois = [
		{
			"place_id": "p1",
			"name": "Palace",
			"rating": 4.5,
			"price_level": 2,
			"lat": 12.3,
			"lng": 76.65,
			"types": ["tourist_attraction"],
			"opening_hours": None,
			"image_url": "",
			"visit_duration_minutes": 60,
		}
	]
	restaurants = [
		{
			"place_id": "r1",
			"name": "Dasaprakash",
			"price_level": 1,
			"lat": 12.31,
			"lng": 76.66,
			"opening_hours": None,
			"image_url": "",
			"visit_duration_minutes": 60,
		}
	]
	hotel = {"lat": 12.29, "lng": 76.64}
	start = datetime(2025, 8, 10, 13, 0)
	deadline = datetime(2025, 8, 10, 20, 0)

	result = optimize_schedule(
		pois,
		restaurants,
		hotel,
		start,
		deadline,
		500,
		2,
		start.date(),
		mock_travel_fn,
	)

	assert sum(entry["cost"] for entry in result) <= 500
	assert all(entry["location_name"] != "Palace" for entry in result)
