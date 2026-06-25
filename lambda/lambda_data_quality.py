"""
lambda_data_quality.py  —  DATA QUALITY LAMBDA
────────────────────────────────────────────────────────────────────────────
Triggered by: ObjectCreated on raw/*.json

Reads the raw source files directly and produces a data quality report:
- Missing fields, invalid values, type inconsistencies
- % clean records
- Normalisation actions taken
Writes: processed/data_quality.json
"""
import json
import logging
from datetime import datetime, timezone

from lambda_utils import (
    STREAM_ALIASES, _normalise_year, _to_bool,
    _read_json, _write_json, get_bucket,
)

logger = logging.getLogger()
logger.setLevel(logging.INFO)

RAW_PREFIX = "raw/"
OUTPUT_KEY = "processed/data_quality.json"


def _audit_employees(employees: list) -> dict:
    total            = len(employees)
    missing_id       = sum(1 for e in employees if not e.get("Employee Number"))
    missing_year     = sum(1 for e in employees if not _normalise_year(e.get("Year Enrolled")))
    missing_stream   = sum(1 for e in employees if not e.get("Stream"))
    missing_role     = sum(1 for e in employees if not e.get("Role"))
    aliased_streams  = sum(1 for e in employees if e.get("Stream") and e["Stream"].strip().lower() in STREAM_ALIASES)
    duplicate_ids    = total - len({e.get("Employee Number") for e in employees if e.get("Employee Number")})

    issues = missing_id + missing_year + missing_stream
    clean  = total - issues
    return {
        "total_records":           total,
        "missing_employee_id":     missing_id,
        "missing_year_enrolled":   missing_year,
        "missing_stream":          missing_stream,
        "missing_role":            missing_role,
        "duplicate_employee_ids":  duplicate_ids,
        "stream_names_normalised": aliased_streams,
        "clean_records":           clean,
        "clean_pct":               round(clean/total*100, 1) if total else 0,
    }


def _audit_costs(costs: list) -> dict:
    total       = len(costs)
    missing_id  = sum(1 for c in costs if not c.get("employee_number"))
    nan_cost    = sum(1 for c in costs if str(c.get("total_cost_of_training","")).upper() == "NAN")
    # Detect string booleans that needed normalisation
    string_bools = sum(
        1 for c in costs
        if any(isinstance(c.get(f), str) and c[f].upper() in ("TRUE","FALSE")
               for f in ["skillbuilder_completed","instructor_completed",
                          "game_day_completed","hackathon_completed","completed_cert_voucher"])
    )
    return {
        "total_records":          total,
        "missing_employee_id":    missing_id,
        "nan_total_cost_records": nan_cost,
        "note":                   "total_cost_of_training recalculated by Lambda pipeline from cost keys",
        "string_boolean_records": string_bools,
        "note_booleans":          "String booleans (TRUE/FALSE) normalised by Lambda pipeline",
    }


def _audit_questionnaires(q_answers: list) -> dict:
    total         = len(q_answers)
    missing_id    = sum(1 for q in q_answers if not q.get("employee_number"))
    missing_q1    = sum(1 for q in q_answers if not any(a["question_id"]=="Q1" for a in q.get("answers",[])))
    incomplete    = sum(1 for q in q_answers if len(q.get("answers",[])) < 14)
    return {
        "total_records":        total,
        "missing_employee_id":  missing_id,
        "missing_q1_response":  missing_q1,
        "incomplete_responses": incomplete,
    }


def lambda_handler(event, context):
    bucket = get_bucket(event)
    logger.info("Data Quality Lambda starting — bucket: %s", bucket)

    employees_raw = (_read_json(bucket, RAW_PREFIX + "employee_data.json")          or {}).get("employees", [])
    costs_raw     = (_read_json(bucket, RAW_PREFIX + "cost_data.json")              or {}).get("costs", [])
    qa_raw        = _read_json(bucket, RAW_PREFIX + "questionnaire_answers.json")   or []

    emp_audit  = _audit_employees(employees_raw)
    cost_audit = _audit_costs(costs_raw)
    qa_audit   = _audit_questionnaires(qa_raw)

    overall_clean_pct = round(
        (emp_audit["clean_records"] / emp_audit["total_records"] * 100)
        if emp_audit["total_records"] else 0, 1
    )

    output = {
        "generated_at":         datetime.now(timezone.utc).isoformat(),
        "overall_quality_pct":  overall_clean_pct,
        "employee_data":        emp_audit,
        "cost_data":            cost_audit,
        "questionnaire_data":   qa_audit,
        "actions_taken": [
            "UTF-8 BOM stripped from all source files",
            f"{emp_audit['stream_names_normalised']} stream names normalised to standard values",
            f"{cost_audit['nan_total_cost_records']} NAN cost values recalculated from cost key table",
            f"{cost_audit['string_boolean_records']} records with string booleans (TRUE/FALSE) normalised",
            "Year values with trailing spaces cleaned",
            "Invalid year values (e.g. 0) excluded from analysis",
        ],
    }

    _write_json(bucket, OUTPUT_KEY, output)
    logger.info("Data quality report written — overall quality: %s%%", overall_clean_pct)
    return {"statusCode": 200, "body": json.dumps({"message": "Data quality report written", "output_key": OUTPUT_KEY})}
