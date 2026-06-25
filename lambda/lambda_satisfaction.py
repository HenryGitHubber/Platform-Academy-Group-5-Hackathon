"""
lambda_satisfaction.py  —  SATISFACTION ENGINE LAMBDA
────────────────────────────────────────────────────────────────────────────
Triggered by: ObjectCreated on processed/all_data.json

Processes questionnaire responses to compute:
- Avg satisfaction scores overall, by year, by stream
- Satisfaction band classification (from mind map):
    0–3  Dissatisfied
    4–6  Somewhat Satisfied
    6–8  Satisfied
    9–10 Extremely Satisfied
Writes: processed/satisfaction_metrics.json
"""
import json
import logging
from datetime import datetime, timezone

from lambda_utils import _read_json, _write_json, get_bucket

logger = logging.getLogger()
logger.setLevel(logging.INFO)

INPUT_KEY  = "processed/all_data.json"
OUTPUT_KEY = "processed/satisfaction_metrics.json"

BAND_ORDER = [
    "Dissatisfied (0-3)",
    "Somewhat Satisfied (4-6)",
    "Satisfied (6-8)",
    "Extremely Satisfied (9-10)",
]


def _get_band(score) -> str | None:
    if score is None: return None
    if score <= 3:    return "Dissatisfied (0-3)"
    elif score <= 6:  return "Somewhat Satisfied (4-6)"
    elif score <= 8:  return "Satisfied (6-8)"
    else:             return "Extremely Satisfied (9-10)"


def _compute_satisfaction_metrics(records: list) -> dict:
    # ── Overall band distribution ─────────────────────────────────────────────
    overall_bands = {b: 0 for b in BAND_ORDER}
    by_year_bands: dict[str, dict] = {}
    by_stream_bands: dict[str, dict] = {}

    # ── Per-question averages ─────────────────────────────────────────────────
    question_scores: dict[str, list] = {}
    NUMERIC_QS = ["Q1","Q2","Q3","Q4","Q5","Q6","Q7","Q9","Q10","Q11"]

    for rec in records:
        score = rec["satisfaction"].get("avg_numeric_score")
        band  = _get_band(score)
        if band:
            overall_bands[band] += 1

        year   = str(rec.get("year_enrolled")   or "Unknown")
        stream = str(rec.get("stream")          or "Unknown")

        if year not in by_year_bands:   by_year_bands[year]   = {b:0 for b in BAND_ORDER}
        if stream not in by_stream_bands: by_stream_bands[stream] = {b:0 for b in BAND_ORDER}
        if band:
            by_year_bands[year][band]     += 1
            by_stream_bands[stream][band] += 1

        for qid in NUMERIC_QS:
            val = rec["satisfaction"].get(qid)
            if isinstance(val, (int, float)):
                question_scores.setdefault(qid, []).append(val)

    avg_by_question = {
        qid: round(sum(scores)/len(scores), 2)
        for qid, scores in question_scores.items() if scores
    }

    # ── Score distribution (histogram bins 1-10) ──────────────────────────────
    histogram = {str(i): 0 for i in range(1, 11)}
    for rec in records:
        score = rec["satisfaction"].get("avg_numeric_score")
        if score is not None:
            bin_key = str(min(10, max(1, round(score))))
            histogram[bin_key] = histogram.get(bin_key, 0) + 1

    return {
        "satisfaction_bands": {
            "overall":    overall_bands,
            "by_year":    by_year_bands,
            "by_stream":  by_stream_bands,
            "band_order": BAND_ORDER,
        },
        "avg_by_question":  avg_by_question,
        "score_histogram":  histogram,
    }


def lambda_handler(event, context):
    bucket = get_bucket(event)
    logger.info("Satisfaction Engine starting — bucket: %s", bucket)

    all_data = _read_json(bucket, INPUT_KEY)
    if not all_data:
        raise ValueError(f"Could not read {INPUT_KEY}")

    metrics = _compute_satisfaction_metrics(all_data.get("employees", []))
    _write_json(bucket, OUTPUT_KEY, {"generated_at": datetime.now(timezone.utc).isoformat(), **metrics})
    return {"statusCode": 200, "body": json.dumps({"message": "Satisfaction metrics written", "output_key": OUTPUT_KEY})}
