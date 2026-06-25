"""
lambda_success_factors.py  —  SUCCESS FACTORS LAMBDA
────────────────────────────────────────────────────────────────────────────
Triggered by: ObjectCreated on processed/all_data.json

Identifies what drives successful programme completion and employee growth.
Successful employee = completed >= 4 of 5 modules AND avg satisfaction >= 7
Segments by: stream, role, experience bucket, year, cloud type.
Writes: processed/success_factors.json
"""
import json
import logging
from datetime import datetime, timezone

from lambda_utils import _read_json, _write_json, get_bucket

logger = logging.getLogger()
logger.setLevel(logging.INFO)

INPUT_KEY  = "processed/all_data.json"
OUTPUT_KEY = "processed/success_factors.json"

PAID_COMP_FIELDS = [
    "skillbuilder_completed",
    "instructor_completed",
    "mytms_completed",
    "game_day_completed",
    "completed_cert_voucher",
]


def _is_successful(rec: dict) -> bool:
    t = rec["training"]
    modules_done = sum(int(t.get(f, False)) for f in PAID_COMP_FIELDS)
    avg_score    = rec["satisfaction"].get("avg_numeric_score") or 0
    return modules_done >= 4 and avg_score >= 7


def _exp_bucket(years) -> str:
    try:
        y = int(years)
    except (TypeError, ValueError):
        return "Unknown"
    if y <= 3:    return "0-3 yrs"
    elif y <= 7:  return "4-7 yrs"
    elif y <= 12: return "8-12 yrs"
    elif y <= 20: return "13-20 yrs"
    else:         return "20+ yrs"


def _group(records, key_fn, label_key):
    buckets: dict[str, dict] = {}
    for rec in records:
        k = str(key_fn(rec) or "Unknown")
        if k not in buckets:
            buckets[k] = {"successful": 0, "unsuccessful": 0}
        if _is_successful(rec): buckets[k]["successful"]   += 1
        else:                   buckets[k]["unsuccessful"] += 1
    result = []
    for k, b in sorted(buckets.items(), key=lambda x: -(x[1]["successful"]+x[1]["unsuccessful"])):
        total = b["successful"] + b["unsuccessful"]
        result.append({
            label_key:          k,
            "successful":       b["successful"],
            "unsuccessful":     b["unsuccessful"],
            "total":            total,
            "success_rate_pct": round(b["successful"]/total*100, 1) if total else 0,
        })
    return result


def _compute_success_factors(records: list) -> dict:
    total           = len(records)
    successful_count = sum(1 for r in records if _is_successful(r))

    return {
        "definition":              "Successful = completed >= 4 of 5 modules AND avg satisfaction >= 7",
        "total_successful":        successful_count,
        "total_unsuccessful":      total - successful_count,
        "overall_success_rate_pct":round(successful_count/total*100, 1) if total else 0,
        "by_stream":      _group(records, lambda r: r.get("stream"),                         "stream"),
        "by_role":        _group(records, lambda r: r.get("role"),                           "role"),
        "by_experience":  _group(records, lambda r: _exp_bucket(r.get("years_experience")),  "experience_bucket"),
        "by_year":        _group(records, lambda r: str(r.get("year_enrolled") or "Unknown"),"year"),
        "by_cloud_type":  _group(records, lambda r: r.get("cloud_type"),                     "cloud_type"),
    }


def lambda_handler(event, context):
    bucket = get_bucket(event)
    logger.info("Success Factors Lambda starting — bucket: %s", bucket)

    all_data = _read_json(bucket, INPUT_KEY)
    if not all_data:
        raise ValueError(f"Could not read {INPUT_KEY}")

    metrics = _compute_success_factors(all_data.get("employees", []))
    _write_json(bucket, OUTPUT_KEY, {"generated_at": datetime.now(timezone.utc).isoformat(), **metrics})
    return {"statusCode": 200, "body": json.dumps({"message": "Success factors written", "output_key": OUTPUT_KEY})}
