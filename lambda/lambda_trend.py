"""
lambda_trend.py  —  TREND ANALYSIS LAMBDA
────────────────────────────────────────────────────────────────────────────
Triggered by: ObjectCreated on processed/all_data.json

Tracks performance over time by intake year:
- Year-on-year cost, satisfaction, and completion trends
- Detects whether metrics are improving or declining
Writes: processed/trend_metrics.json
"""
import json
import logging
from datetime import datetime, timezone

from lambda_utils import _read_json, _write_json, get_bucket

logger = logging.getLogger()
logger.setLevel(logging.INFO)

INPUT_KEY  = "processed/all_data.json"
OUTPUT_KEY = "processed/trend_metrics.json"


def _trend_direction(values: list) -> str:
    """Simple trend: compare first and last value."""
    if len(values) < 2: return "insufficient data"
    delta = values[-1] - values[0]
    if abs(delta) < 0.01: return "stable"
    return "increasing" if delta > 0 else "decreasing"


def _compute_trend_metrics(by_year: list) -> dict:
    if not by_year:
        return {"years": [], "trends": {}}

    years        = [y["year"]                         for y in by_year]
    costs        = [y["avg_cost_per_employee_eur"]     for y in by_year]
    satisfaction = [y["avg_satisfaction_overall"] or 0 for y in by_year]
    headcounts   = [y["employee_count"]               for y in by_year]

    # Avg completion across all modules per year
    def _avg_completion(y):
        cr = y.get("completion_rates", {})
        rates = [v["rate_pct"] for v in cr.values() if v.get("rate_pct") is not None]
        return round(sum(rates)/len(rates), 1) if rates else 0

    completions = [_avg_completion(y) for y in by_year]

    # Year-on-year change
    def _yoy(values):
        changes = []
        for i in range(1, len(values)):
            prev = values[i-1]
            curr = values[i]
            delta_abs = round(curr - prev, 2)
            delta_pct = round((curr - prev)/prev*100, 1) if prev else 0
            changes.append({
                "from_year": years[i-1],
                "to_year":   years[i],
                "change":    delta_abs,
                "change_pct":delta_pct,
            })
        return changes

    # Per-year summary enriched with completion
    year_summaries = []
    for i, y in enumerate(by_year):
        year_summaries.append({
            "year":               y["year"],
            "employee_count":     y["employee_count"],
            "avg_cost_eur":       y["avg_cost_per_employee_eur"],
            "avg_satisfaction":   y["avg_satisfaction_overall"],
            "avg_completion_pct": completions[i],
            "total_cost_eur":     y["total_cost_eur"],
        })

    return {
        "year_summaries": year_summaries,
        "year_on_year": {
            "cost":         _yoy(costs),
            "satisfaction": _yoy(satisfaction),
            "completion":   _yoy(completions),
            "headcount":    _yoy(headcounts),
        },
        "trends": {
            "cost_trend":         _trend_direction(costs),
            "satisfaction_trend": _trend_direction(satisfaction),
            "completion_trend":   _trend_direction(completions),
            "headcount_trend":    _trend_direction(headcounts),
        },
        "insight": {
            "cost_vs_satisfaction": (
                "Cost and satisfaction are moving in the same direction"
                if _trend_direction(costs) == _trend_direction(satisfaction)
                else "Cost is rising but satisfaction is not keeping up — review programme value"
                if _trend_direction(costs) == "increasing" and _trend_direction(satisfaction) != "increasing"
                else "Satisfaction improving despite cost control — strong ROI signal"
            ),
        },
    }


def lambda_handler(event, context):
    bucket = get_bucket(event)
    logger.info("Trend Analysis Lambda starting — bucket: %s", bucket)

    all_data = _read_json(bucket, INPUT_KEY)
    if not all_data:
        raise ValueError(f"Could not read {INPUT_KEY}")

    metrics = _compute_trend_metrics(all_data.get("by_year", []))
    _write_json(bucket, OUTPUT_KEY, {"generated_at": datetime.now(timezone.utc).isoformat(), **metrics})
    return {"statusCode": 200, "body": json.dumps({"message": "Trend metrics written", "output_key": OUTPUT_KEY})}
