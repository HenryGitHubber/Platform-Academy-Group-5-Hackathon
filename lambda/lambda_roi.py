"""
lambda_roi.py  —  ROI ENGINE LAMBDA
────────────────────────────────────────────────────────────────────────────
Triggered by: ObjectCreated on processed/all_data.json

Combines cost, completion, and satisfaction to rank programmes by ROI.
Formula (from mind map):
    ROI = (Satisfaction_norm × Completion_norm) / Cost_norm
    where each metric is normalised to 0–1 scale.
Writes: processed/roi_metrics.json
"""
import json
import logging
from datetime import datetime, timezone

from lambda_utils import _read_json, _write_json, get_bucket

logger = logging.getLogger()
logger.setLevel(logging.INFO)

INPUT_KEY  = "processed/all_data.json"
OUTPUT_KEY = "processed/roi_metrics.json"


def _compute_roi(by_stream: list, by_year: list, records: list) -> dict:
    # ── ROI by stream ─────────────────────────────────────────────────────────
    max_cost = max((s["avg_cost_per_employee_eur"] for s in by_stream if s["avg_cost_per_employee_eur"] > 0), default=1)

    scored_streams = []
    for s in by_stream:
        cost = s["avg_cost_per_employee_eur"] or 0
        sat  = s["avg_satisfaction"]          or 0
        comp = s["avg_module_completion_pct"] or 0
        cost_norm = cost / max_cost if max_cost > 0 else 0
        roi = round((sat/10 * comp/100) / cost_norm, 4) if cost_norm > 0 else 0
        scored_streams.append({
            "stream":              s["stream"],
            "employee_count":      s["employee_count"],
            "avg_cost_eur":        round(cost, 2),
            "avg_satisfaction":    sat,
            "avg_completion_pct":  comp,
            "roi_score":           roi,
        })
    scored_streams.sort(key=lambda x: -x["roi_score"])
    for i, s in enumerate(scored_streams):
        s["rank"] = i + 1

    # ── ROI by year ───────────────────────────────────────────────────────────
    max_year_cost = max((y["avg_cost_per_employee_eur"] for y in by_year if y["avg_cost_per_employee_eur"] > 0), default=1)

    scored_years = []
    for y in by_year:
        cost = y["avg_cost_per_employee_eur"]     or 0
        sat  = y["avg_satisfaction_overall"]      or 0
        # avg completion across all modules for this year
        cr   = y.get("completion_rates", {})
        all_rates = [v["rate_pct"] for v in cr.values() if v["rate_pct"] > 0]
        comp = round(sum(all_rates)/len(all_rates), 1) if all_rates else 0
        cost_norm = cost / max_year_cost if max_year_cost > 0 else 0
        roi = round((sat/10 * comp/100) / cost_norm, 4) if cost_norm > 0 else 0
        scored_years.append({
            "year":               y["year"],
            "employee_count":     y["employee_count"],
            "avg_cost_eur":       round(cost, 2),
            "avg_satisfaction":   sat,
            "avg_completion_pct": comp,
            "roi_score":          roi,
        })
    scored_years.sort(key=lambda x: x["year"])

    return {
        "formula": "ROI = (Satisfaction/10 x AvgCompletion/100) / (Cost/MaxCost)",
        "by_stream": scored_streams,
        "by_year":   scored_years,
    }


def lambda_handler(event, context):
    bucket = get_bucket(event)
    logger.info("ROI Engine starting — bucket: %s", bucket)

    all_data = _read_json(bucket, INPUT_KEY)
    if not all_data:
        raise ValueError(f"Could not read {INPUT_KEY}")

    metrics = _compute_roi(
        all_data.get("by_stream", []),
        all_data.get("by_year",   []),
        all_data.get("employees", []),
    )
    _write_json(bucket, OUTPUT_KEY, {"generated_at": datetime.now(timezone.utc).isoformat(), **metrics})
    return {"statusCode": 200, "body": json.dumps({"message": "ROI metrics written", "output_key": OUTPUT_KEY})}
