"""
lambda_completion.py  —  COMPLETION ENGINE LAMBDA
────────────────────────────────────────────────────────────────────────────
Triggered by: ObjectCreated on processed/all_data.json

Computes completion and drop-off rates per module, per year, and per stream.
Drop-off rate = (enrolled - completed) / enrolled × 100
Writes: processed/completion_metrics.json
"""
import json
import logging
from datetime import datetime, timezone

from lambda_utils import _read_json, _write_json, get_bucket

logger = logging.getLogger()
logger.setLevel(logging.INFO)

INPUT_KEY  = "processed/all_data.json"
OUTPUT_KEY = "processed/completion_metrics.json"

MODULE_LABELS = {
    "skillbuilder": "Cloud Skillbuilder",
    "instructor":   "Instructor-Led",
    "mytms":        "MyTMS",
    "game_day":     "Game Day",
    "hackathon":    "Hackathon",
    "cert":         "Certification",
}
SIGN_FIELD = {
    "skillbuilder": "skillbuilder_signed",
    "instructor":   "instructor_signed",
    "mytms":        "mytms_signed",
    "game_day":     "game_day_signed",
    "hackathon":    "hackathon_signed",
    "cert":         "received_cert_voucher",
}
COMP_FIELD = {
    "skillbuilder": "skillbuilder_completed",
    "instructor":   "instructor_completed",
    "mytms":        "mytms_completed",
    "game_day":     "game_day_completed",
    "hackathon":    "hackathon_completed",
    "cert":         "completed_cert_voucher",
}


def _compute_completion_metrics(records: list, module_stats: dict) -> dict:
    # ── Overall per-module rates (from pre-computed module_stats) ─────────────
    per_module = [
        {
            "module":              MODULE_LABELS.get(m, m),
            "enrolled":            v["signed"],
            "completed":           v["completed"],
            "dropped_off":         v["signed"] - v["completed"],
            "completion_rate_pct": v["completion_rate_pct"],
            "drop_off_rate_pct":   v["drop_off_rate_pct"],
        }
        for m, v in module_stats.items()
    ]
    # Sort by drop-off rate descending (highest risk at top)
    per_module.sort(key=lambda x: -x["drop_off_rate_pct"])

    # ── Overall programme completion (employee completed all 5 paid modules) ──
    fully_complete = sum(
        1 for r in records
        if all(r["training"].get(COMP_FIELD[m]) for m in ["skillbuilder","instructor","mytms","game_day","cert"])
    )
    total = len(records)

    # ── Completion by year ────────────────────────────────────────────────────
    year_buckets: dict[int, dict] = {}
    for rec in records:
        year = rec.get("year_enrolled")
        if not year: continue
        if year not in year_buckets:
            year_buckets[year] = {m: {"signed":0,"completed":0} for m in COMP_FIELD}
        for mod in COMP_FIELD:
            t = rec["training"]
            year_buckets[year][mod]["signed"]    += int(t.get(SIGN_FIELD[mod], False))
            year_buckets[year][mod]["completed"] += int(t.get(COMP_FIELD[mod], False))

    completion_by_year = []
    for year, mods in sorted(year_buckets.items()):
        total_signed    = sum(v["signed"]    for v in mods.values())
        total_completed = sum(v["completed"] for v in mods.values())
        completion_by_year.append({
            "year":                year,
            "overall_completion_rate_pct": round(total_completed/total_signed*100,1) if total_signed else 0,
            "overall_drop_off_rate_pct":   round((total_signed-total_completed)/total_signed*100,1) if total_signed else 0,
            "per_module": {
                MODULE_LABELS.get(m,m): {
                    "completion_rate_pct": round(v["completed"]/v["signed"]*100,1) if v["signed"] else 0,
                    "drop_off_rate_pct":   round((v["signed"]-v["completed"])/v["signed"]*100,1) if v["signed"] else 0,
                }
                for m, v in mods.items()
            },
        })

    return {
        "per_module":              per_module,
        "completion_by_year":      completion_by_year,
        "fully_complete_employees":fully_complete,
        "fully_complete_rate_pct": round(fully_complete/total*100,1) if total else 0,
        "total_employees":         total,
    }


def lambda_handler(event, context):
    bucket = get_bucket(event)
    logger.info("Completion Engine starting — bucket: %s", bucket)

    all_data = _read_json(bucket, INPUT_KEY)
    if not all_data:
        raise ValueError(f"Could not read {INPUT_KEY}")

    metrics = _compute_completion_metrics(
        all_data.get("employees", []),
        all_data.get("module_stats", {}),
    )

    _write_json(bucket, OUTPUT_KEY, {"generated_at": datetime.now(timezone.utc).isoformat(), **metrics})
    return {"statusCode": 200, "body": json.dumps({"message": "Completion metrics written", "output_key": OUTPUT_KEY})}
