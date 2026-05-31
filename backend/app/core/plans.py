"""Subscription plan configurations."""

from typing import Dict, TypedDict


class PlanConfig(TypedDict):
    """Plan configuration structure."""
    price_cents: int
    days: int
    name: str


PLANS: Dict[str, PlanConfig] = {
    "monthly": {
        "price_cents": 2900,
        "days": 30,
        "name": "月度会员"
    },
    "yearly": {
        "price_cents": 29900,
        "days": 365,
        "name": "年度会员"
    },
    "lifetime": {
        "price_cents": 99900,
        "days": 36500,  # 100 years
        "name": "永久会员"
    }
}


def get_plan_info(plan_type: str) -> PlanConfig:
    """Get plan configuration by type.

    Args:
        plan_type: Plan type (monthly, yearly, lifetime)

    Returns:
        Plan configuration dict

    Raises:
        KeyError: If plan type is invalid
    """
    return PLANS[plan_type]


def get_plan_price_yuan(plan_type: str) -> float:
    """Get plan price in yuan.

    Args:
        plan_type: Plan type (monthly, yearly, lifetime)

    Returns:
        Price in yuan (e.g., 29.00)
    """
    return PLANS[plan_type]["price_cents"] / 100


def is_valid_plan(plan_type: str) -> bool:
    """Check if plan type is valid.

    Args:
        plan_type: Plan type to validate

    Returns:
        True if valid, False otherwise
    """
    return plan_type in PLANS
