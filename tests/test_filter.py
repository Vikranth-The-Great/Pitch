from core.filter import get_item_cost, rank_hotels, rank_places


def test_rank_places_theme_bonus():
	pois = [
		{"name": "Palace", "rating": 4.0, "price_level": 1, "types": ["tourist_attraction"]},
		{"name": "Mall", "rating": 4.5, "price_level": 3, "types": ["shopping_mall"]},
	]

	ranked = rank_places(pois, theme="Historical", budget_tier="Medium")

	assert ranked[0]["name"] == "Palace"
	assert ranked[0]["wanderwise_score"] == 90.0


def test_rank_places_budget_penalty():
	pois = [
		{"name": "Expensive", "rating": 4.2, "price_level": 4, "types": ["museum"]},
		{"name": "Affordable", "rating": 4.1, "price_level": 1, "types": ["museum"]},
	]

	ranked = rank_places(pois, theme="Historical", budget_tier="Low")

	assert ranked[0]["name"] == "Affordable"


def test_rank_hotels_centrality():
	hotels = [
		{"name": "Central Hotel", "rating": 4.0, "lat": 12.30, "lng": 76.65},
		{"name": "Far Hotel", "rating": 4.5, "lat": 12.50, "lng": 77.00},
	]
	sample_pois = [{"lat": 12.30, "lng": 76.65}]

	best = rank_hotels(hotels, sample_pois)

	assert best["name"] == "Central Hotel"


def test_get_item_cost_attraction():
	cost = get_item_cost(price_level=2, people=2, category="attraction")

	assert cost == 1400


def test_get_item_cost_hotel():
	cost = get_item_cost(price_level=2, people=2, category="hotel")

	assert cost == 5000


def test_get_item_cost_default_price_level():
	cost = get_item_cost(price_level=None, people=2, category="attraction")

	assert cost == 600
