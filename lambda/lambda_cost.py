"""
lambda_cost.py  —  COST ENGINE LAMBDA
────────────────────────────────────────────────────────────────────────────
Triggered by: ObjectCreated on processed/all_data.json

Reads the enriched employee records and produces detailed cost metrics:
cost per employee, per programme module, per year, and per stream.
Writes: processed/cost_metrics.json
"""
import json
import logging
from datetime import datetime, timezone

from lambda_utils import DEFAULT_COSTS, _read_json, _write_json, get_bucket

logger = logging.getLogger()
logger.setLevel(logging.INFO)

INPUT_KEY  = "processed/all_data.json"
OUTPUT_KEY = "processed/cost_metrics.json"


def _compute_cost_metrics(records: list, by_year: list, by_stream: list) -> dict:
    # ── Per-module spend ──────────────────────────────────────────────────────
    module_labels = {
        "skillbuilder": "Cloud Skillbuilder",
        "instructor":   "Instructor-Led",
        "mytms":        "MyTMS",
        "game_day":     "Game Day",
        "hackathon":    "Hackathon",
        "cert":         "Certification",
    }
    module_costs = {
        "skillbuilder": DEFAULT_COSTS["skillbuilder"],
        "instructor":   DEFAULT_COSTS["instructor"],
        "mytms":        DEFAULT_COSTS["mytms"],
        "game_day":     DEFAULT_COSTS["game_day"],
        "hackathon":    DEFAULT_COSTS["hackathon"],
        "cert":         DEFAULT_COSTS["foundational_cert"],
    }
    module_completed = {k: 0 for k in module_costs}
    completion_field_map = {
        "skillbuilder": "skillbuilder_completed",
        "instructor":   "instructor_completed",
        "mytms":        "mytms_completed",
        "game_day":     "game_day_completed",
        "hackathon":    "hackathon_completed",
        "cert":         "completed_cert_voucher",
    }
    for rec in records:
        t = rec["training"]
        for mod, field in completion_field_map.items():
            if t.get(field):
                module_completed[mod] += 1

    cost_per_module = [
        {
            "module":          module_labels[m],
            "unit_cost_eur":   module_costs[m],
            "completions":     module_completed[m],
            "total_spend_eur": round(module_completed[m] * module_costs[m], 2),
        }
        for m in module_costs
    ]

    # ── Per-employee cost distribution ────────────────────────────────────────
    all_costs = [r["training"]["total_cost_eur"] for r in records]
    all_costs_sorted = sorted(all_costs)
    n = len(all_costs_sorted)

    cost_distribution = {
        "min_eur":    round(min(all_costs), 2) if all_costs else 0,
        "max_eur":    round(max(all_costs), 2) if all_costs else 0,
        "avg_eur":    round(sum(all_costs)/n, 2) if n else 0,
        "median_eur": round(all_costs_sorted[n//2], 2) if n else 0,
        "total_eur":  round(sum(all_costs), 2),
    }

    # ── Year summary (pulled from already-aggregated by_year) ─────────────────
    cost_by_year = [
        {
            "year":                     y["year"],
            "employee_count":           y["employee_count"],
            "total_cost_eur":           y["total_cost_eur"],
            "avg_cost_per_employee_eur":y["avg_cost_per_employee_eur"],
        }
        for y in by_year
    ]

    # ── Stream summary ─────────────────────────────────────────────────────────
    cost_by_stream = [
        {
            "stream":                   s["stream"],
            "employee_count":           s["employee_count"],
            "total_cost_eur":           s["total_cost_eur"],
            "avg_cost_per_employee_eur":s["avg_cost_per_employee_eur"],
        }
        for s in by_stream
    ]

    return {
        "cost_per_module":   cost_per_module,
        "cost_distribution": cost_distribution,
        "cost_by_year":      cost_by_year,
        "cost_by_stream":    cost_by_stream,
    }


def lambda_handler(event, context):
    bucket = get_bucket(event)
    logger.info("Cost Engine starting — bucket: %s", bucket)

    all_data = _read_json(bucket, INPUT_KEY)
    if not all_data:
        raise ValueError(f"Could not read {INPUT_KEY} from bucket {bucket}")

    metrics = _compute_cost_metrics(
        all_data.get("employees", []),
        all_data.get("by_year", []),
        all_data.get("by_stream", []),
    )

    output = {"generated_at": datetime.now(timezone.utc).isoformat(), **metrics}
    _write_json(bucket, OUTPUT_KEY, output)

    return {"statusCode": 200, "body": json.dumps({"message": "Cost metrics written", "output_key": OUTPUT_KEY})}
