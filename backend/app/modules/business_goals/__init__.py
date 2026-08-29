"""Immutable, owner-declared Business Goals v1.0 capability."""

from app.modules.business_goals.models import BusinessGoal, GoalLifecycle
from app.modules.business_goals.service import BusinessGoalService

__all__ = ["BusinessGoal", "BusinessGoalService", "GoalLifecycle"]
