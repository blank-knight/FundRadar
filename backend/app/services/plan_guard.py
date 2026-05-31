"""Free vs Premium content access control."""

from datetime import datetime
from typing import Optional

from app.models.models import User


# Feature access control mapping
PREMIUM_FEATURES = {
    "signal_today",     # Daily signal for today
    "blogger_full",     # Full blogger list (free users see top 3 only)
    "news_summary",     # News summary and sentiment analysis
    "watchlist",        # Personal watchlist
    "education_qa",     # AI Q&A for education
}

FREE_FEATURES = {
    "signal_history",   # Historical signals (2 days delayed)
    "blogger_top3",     # Top 3 bloggers only
    "news_basic",       # News titles only (no summary/sentiment)
}


def check_plan(user: User, feature: str) -> bool:
    """Check if user's plan allows access to a feature.

    Args:
        user: User object with plan and expiry info
        feature: Feature identifier string

    Returns:
        True if user can access the feature, False otherwise

    Raises:
        ValueError: If feature name is not recognized
    """
    # Validate feature name
    all_features = PREMIUM_FEATURES | FREE_FEATURES
    if feature not in all_features:
        raise ValueError(f"Unknown feature: {feature}")

    # Free features are always accessible
    if feature in FREE_FEATURES:
        return True

    # Premium features require paid plan
    if feature in PREMIUM_FEATURES:
        return is_premium_active(user)

    return False


def is_premium_active(user: User) -> bool:
    """Check if user has active premium subscription.

    Args:
        user: User object with plan and expiry info

    Returns:
        True if premium is active, False otherwise
    """
    # Free users are not premium
    if user.plan == "free":
        return False

    # Lifetime users never expire
    if user.plan == "lifetime":
        return True

    # Check expiration for monthly/yearly plans
    if user.plan_expires_at is None:
        # Should not happen for monthly/yearly, but treat as expired
        return False

    return user.plan_expires_at > datetime.utcnow()


def filter_bloggers_by_plan(user: User, bloggers: list, limit_free: int = 3) -> list:
    """Filter blogger list based on user's plan.

    Free users only see top N bloggers by accuracy score.
    Premium users see all bloggers.

    Args:
        user: User object with plan info
        bloggers: List of blogger objects
        limit_free: Number of bloggers free users can see (default 3)

    Returns:
        Filtered list of bloggers
    """
    if is_premium_active(user):
        return bloggers

    # Free users see top N by accuracy score
    sorted_bloggers = sorted(bloggers, key=lambda b: b.accuracy_score, reverse=True)
    return sorted_bloggers[:limit_free]


def get_plan_feature_summary(user: User) -> dict:
    """Get summary of features available to user's plan.

    Args:
        user: User object with plan info

    Returns:
        Dictionary mapping feature to access status
    """
    features = {}
    all_features = PREMIUM_FEATURES | FREE_FEATURES

    for feature in all_features:
        features[feature] = check_plan(user, feature)

    return {
        "plan": user.plan,
        "is_premium": is_premium_active(user),
        "expires_at": user.plan_expires_at.isoformat() if user.plan_expires_at else None,
        "features": features
    }
