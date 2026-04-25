from __future__ import annotations

def reserve_hotel_budget(cost_per_night: int, num_days: int) -> int:
    """Returns total hotel cost for the trip.
    
    A one-day trip still requires one billable stay in the current cost model.
    Multi-day trips use nights (num_days - 1) for total hotel cost.
    """
    nights = max(1, num_days - 1)
    return cost_per_night * nights

def allocate_daily_budget(
    total_budget: int,
    hotel_total: int,
    accumulated_activity_cost: int,
    num_days: int,
    current_day_index: int,
) -> int:
    """Returns the budget available for the current day's activities.
    
    Distributes the remaining activity budget equally among the remaining days.
    """
    remaining_total_budget = total_budget - hotel_total - accumulated_activity_cost
    if remaining_total_budget <= 0:
        return 0
    
    remaining_days = num_days - current_day_index
    if remaining_days <= 0:
        return 0
    
    return remaining_total_budget // remaining_days

def check_within_budget(total_cost: int, budget_limit: int) -> bool:
    """Returns True if total_cost <= budget_limit."""
    return total_cost <= budget_limit
