"""Provisional, weight-stability fueling estimates."""
from collections.abc import Sequence
from datetime import date, timedelta
from math import isfinite
from statistics import median

from .models import HARD_FINGER, Kind, Nutrition


def resting_kcal(weight_kg: float, height_cm: float, age: int, equation: str) -> float:
    if not (30 <= weight_kg <= 300 and 120 <= height_cm <= 240 and 18 <= age <= 100):
        raise ValueError("Inputs are outside the supported adult range.")
    if equation not in {"male", "female"}:
        raise ValueError("Select the equation constant explicitly.")
    return 10 * weight_kg + 6.25 * height_cm - 5 * age + (5 if equation == "male" else -161)


def target(kind: Kind) -> Nutrition:
    if kind == Kind.REST:
        return Nutrition(day_class="rest", protein_g=150, carbs_g=285, fat_g=85)
    if kind in HARD_FINGER or kind == Kind.INTERVALS:
        return Nutrition(day_class="hard", protein_g=155, carbs_g=400, fat_g=85)
    return Nutrition(day_class="moderate", protein_g=150, carbs_g=335, fat_g=85)


def calibration_review(samples: Sequence[tuple[date, float]], as_of: date) -> tuple[int, str]:
    """Optional in-memory review. An estimate cannot change the prescribed macros."""
    if len({day for day, _ in samples}) != len(samples) or any(
        not isfinite(kg) or not 30 <= kg <= 300 or day > as_of for day, kg in samples
    ):
        raise ValueError("Use unique dates and valid adult measurements.")
    recent = [kg for day, kg in samples if as_of - timedelta(days=6) <= day <= as_of]
    prior = [kg for day, kg in samples if as_of - timedelta(days=13) <= day < as_of - timedelta(days=6)]
    if min(len(recent), len(prior)) < 3:
        return 0, "Insufficient observations: at least three comparable readings in each of two weeks."
    change = (median(recent) - median(prior)) / median(prior)
    if change <= -0.01:
        return 0, "Review unintended loss or underfueling with a qualified professional."
    if change <= -0.004:
        return 120, "Review a provisional increase of 120 kcal/day for adequate fueling."
    if change >= 0.004:
        return 0, "Review trend and measurement conditions before changing maintenance targets."
    return 0, "Hold provisional targets and review appetite, energy and recovery."
