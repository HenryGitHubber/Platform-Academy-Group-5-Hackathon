import json
import boto3
import codecs
import logging
from datetime import datetime, timezone

logger = logging.getLogger()
logger.setLevel(logging.INFO)

s3 = boto3.client("s3")

# ── Configuration ────────────────────────────────────────────────────────────
RAW_PREFIX = "raw/"
OUTPUT_KEY = "processed/all_data.json"

# Cost per completed module in EUR (from cost_key_data.json)
DEFAULT_COSTS = {
    "skillbuilder": 123.80,
    "instructor": 208.00,
    "mytms": 50.00,
    "game_day": 305.00,
    "hackathon": 0.00,
    "foundational_cert": 150.00,
}

# Normalise inconsistent stream names found in the data
def _to_bool(val) -> bool:
    """Handle True/False booleans, 'TRUE'/'FALSE' strings, and 1/0 integers."""
    if isinstance(val, bool):
        return val
    if isinstance(val, str):
        return val.strip().upper() == "TRUE"
    return bool(val)


STREAM_ALIASES = {
    "datascience": "Data Science",
    "solutions architect": "Solutions Architecture",
    "cloud ops / reliability": "Cloud Operations / Reliability",
    "cloud ops/reliability": "Cloud Operations / Reliability",
}

# ── Helpers ───────────────────────────────────────────────────────────────────

def _read_json(bucket: str, key: str):
    """Download an S3 object and parse JSON, handling UTF-8 BOM."""
    try:
        response = s3.get_object(Bucket=bucket, Key=key)
        raw_bytes = response["Body"].read()
        # Strip UTF-8 BOM if present
        text = raw_bytes.decode("utf-8-sig")
        return json.loads(text)
    except s3.exceptions.NoSuchKey:
        logger.warning("Key not found in S3: %s/%s — skipping", bucket, key)
        return None
    except Exception as exc:
        logger.error("Failed to read %s/%s: %s", bucket, key, exc)
        return None


def _write_json(bucket: str, key: str, data: dict):
    body = json.dumps(data, ensure_ascii=False, default=str)
    s3.put_object(
        Bucket=bucket,
        Key=key,
        Body=body.encode("utf-8"),
        ContentType="application/json",
        CacheControl="no-cache",
    )
    logger.info("Written output to s3://%s/%s", bucket, key)


def _normalise_stream(raw: str | None) -> str:
    if not raw:
        return "Unknown"
    return STREAM_ALIASES.get(raw.strip().lower(), raw.strip())


def _normalise_year(raw) -> int | None:
    try:
        year = int(str(raw).strip())
        return year if year > 2000 else None
    except (ValueError, TypeError):
        return None


def _calculate_cost(cost_record: dict, cost_keys: dict) -> float:
    """Sum up completed module costs for one employee."""
    total = 0.0
    if cost_record.get("skillbuilder_completed"):
        total += cost_keys.get("skillbuilder_cost", DEFAULT_COSTS["skillbuilder"])
    if cost_record.get("instructor_completed"):
        total += cost_keys.get("instructor_cost", DEFAULT_COSTS["instructor"])
    if cost_record.get("mytms_completed"):
        total += cost_keys.get("mytms_cost", DEFAULT_COSTS["mytms"])
    if cost_record.get("game_day_completed"):
        total += cost_keys.get("game_day_cost", DEFAULT_COSTS["game_day"])
    if cost_record.get("hackathon_completed"):
        total += cost_keys.get("hackathon_cost", DEFAULT_COSTS["hackathon"])
    if cost_record.get("completed_cert_voucher"):
        total += cost_keys.get("foundational_cert_cost", DEFAULT_COSTS["foundational_cert"])
    return round(total, 2)


# ── Core processing ────────────────────────────────────────────────────────────

def _load_all_data(bucket: str) -> tuple[list, list, list, dict]:
    """
    Load base files plus any year-specific override files.
    Year-specific files (e.g. employee_data_2026.json) are merged in.
    Returns: (employees, costs, q_answers, cost_keys)
    """
    # Load base data (2023-2025)
    emp_data = _read_json(bucket, RAW_PREFIX + "employee_data.json") or {"employees": []}
    cost_data = _read_json(bucket, RAW_PREFIX + "cost_data.json") or {"costs": []}
    q_answers_raw = _read_json(bucket, RAW_PREFIX + "questionnaire_answers.json") or []
    cost_key_raw = _read_json(bucket, RAW_PREFIX + "cost_key_data.json") or {"cost_keys": [{}]}

    employees = list(emp_data.get("employees", []))
    costs = list(cost_data.get("costs", []))
    q_answers = list(q_answers_raw) if isinstance(q_answers_raw, list) else []

    # Extract cost key values (use first entry)
    cost_keys = cost_key_raw.get("cost_keys", [{}])[0] if cost_key_raw.get("cost_keys") else {}

    # Discover and merge any year-specific files present in the raw prefix
    # e.g. employee_data_2026.json, cost_data_2026.json, questionnaire_answers_2026.json
    existing_emp_numbers = {e.get("Employee Number") for e in employees}
    existing_cost_numbers = {c.get("employee_number") for c in costs}
    existing_q_numbers = {q.get("employee_number") for q in q_answers}

    for year in range(2026, 2031):
        emp_year = _read_json(bucket, f"{RAW_PREFIX}employee_data_{year}.json")
        if emp_year:
            new_emps = [
                e for e in emp_year.get("employees", [])
                if e.get("Employee Number") not in existing_emp_numbers
            ]
            employees.extend(new_emps)
            existing_emp_numbers.update(e.get("Employee Number") for e in new_emps)
            logger.info("Merged %d employees from year %d", len(new_emps), year)

        cost_year = _read_json(bucket, f"{RAW_PREFIX}cost_data_{year}.json")
        if cost_year:
            new_costs = [
                c for c in cost_year.get("costs", [])
                if c.get("employee_number") not in existing_cost_numbers
            ]
            costs.extend(new_costs)
            existing_cost_numbers.update(c.get("employee_number") for c in new_costs)

        qa_year = _read_json(bucket, f"{RAW_PREFIX}questionnaire_answers_{year}.json")
        if qa_year and isinstance(qa_year, list):
            new_qa = [
                q for q in qa_year
                if q.get("employee_number") not in existing_q_numbers
            ]
            q_answers.extend(new_qa)
            existing_q_numbers.update(q.get("employee_number") for q in new_qa)

    return employees, costs, q_answers, cost_keys


def _build_employee_records(employees, costs, q_answers, cost_keys) -> list[dict]:
    """Join the three datasets into one enriched record per employee."""
    # Index cost and questionnaire data by employee_number for O(1) lookup
    cost_index = {c["employee_number"]: c for c in costs if c.get("employee_number")}
    qa_index = {q["employee_number"]: q for q in q_answers if q.get("employee_number")}

    records = []
    for emp in employees:
        emp_num = emp.get("Employee Number")
        if not emp_num:
            continue

        cost_rec = cost_index.get(emp_num, {})
        qa_rec = qa_index.get(emp_num, {})

        # Calculate actual training cost
        total_cost = _calculate_cost(cost_rec, cost_keys)

        # Build flat answers dict from the answers array
        answers_flat = {}
        numeric_scores = []
        for item in qa_rec.get("answers", []):
            qid = item.get("question_id")
            ans = item.get("answer")
            # Normalise categorical answers
            if qid == "Q8" and isinstance(ans, str):
                ans = ans.strip().title()
            elif qid == "Q11":
                # Normalise to integer 1/0
                if isinstance(ans, str):
                    ans = 1 if ans.strip().lower() in ("yes", "1", "true") else 0
                elif isinstance(ans, bool):
                    ans = int(ans)
                elif ans not in (0, 1):
                    ans = None  # discard invalid values
            elif qid == "Q12" and isinstance(ans, str):
                ans = ans.strip()
            answers_flat[qid] = ans
            # Q1-Q10 and Q9 are numeric; Q8, Q12, Q13, Q14 are text; Q11 is 0/1
            if qid not in ("Q8", "Q12", "Q13", "Q14") and isinstance(ans, (int, float)):
                numeric_scores.append(ans)

        avg_score = round(sum(numeric_scores) / len(numeric_scores), 2) if numeric_scores else None

        records.append({
            "employee_number": emp_num,
            "name": emp.get("Name"),
            "surname": emp.get("Surname"),
            "role": emp.get("Role"),
            "department_code": emp.get("Department Code"),
            "years_experience": emp.get("No. Years Experience"),
            "stream": _normalise_stream(emp.get("Stream")),
            "cloud_type": emp.get("Cloud Type"),
            "year_enrolled": _normalise_year(emp.get("Year Enrolled")),
            "training": {
                "skillbuilder_signed": _to_bool(cost_rec.get("skillbuilder_signed", False)),
                "skillbuilder_completed": _to_bool(cost_rec.get("skillbuilder_completed", False)),
                "instructor_signed": _to_bool(cost_rec.get("instructor_signed", False)),
                "instructor_completed": _to_bool(cost_rec.get("instructor_completed", False)),
                "mytms_signed": _to_bool(cost_rec.get("mytms_signed", False)),
                "mytms_completed": _to_bool(cost_rec.get("mytms_completed", False)),
                "game_day_signed": _to_bool(cost_rec.get("game_day_signed", False)),
                "game_day_completed": _to_bool(cost_rec.get("game_day_completed", False)),
                "hackathon_signed": _to_bool(cost_rec.get("hackathon_signed", False)),
                "hackathon_completed": _to_bool(cost_rec.get("hackathon_completed", False)),
                "received_cert_voucher": cost_rec.get("received_cert_voucher", False),
                "completed_cert_voucher": cost_rec.get("completed_cert_voucher", False),
                "total_cost_eur": total_cost,
            },
            "satisfaction": {
                **answers_flat,
                "avg_numeric_score": avg_score,
            },
        })

    return records


def _aggregate_by_year(records: list[dict]) -> list[dict]:
    buckets: dict[int, dict] = {}

    for rec in records:
        year = rec.get("year_enrolled")
        if not year:
            continue
        if year not in buckets:
            buckets[year] = {
                "year": year,
                "employees": [],
                "total_cost_eur": 0.0,
                "q_scores": {},
                "module_signed": {m: 0 for m in ["skillbuilder", "instructor", "mytms", "game_day", "hackathon", "cert"]},
                "module_completed": {m: 0 for m in ["skillbuilder", "instructor", "mytms", "game_day", "hackathon", "cert"]},
            }
        b = buckets[year]
        b["employees"].append(rec["employee_number"])
        b["total_cost_eur"] += rec["training"]["total_cost_eur"]

        t = rec["training"]
        b["module_signed"]["skillbuilder"] += int(_to_bool(t["skillbuilder_signed"]))
        b["module_completed"]["skillbuilder"] += int(_to_bool(t["skillbuilder_completed"]))
        b["module_signed"]["instructor"] += int(_to_bool(t["instructor_signed"]))
        b["module_completed"]["instructor"] += int(_to_bool(t["instructor_completed"]))
        b["module_signed"]["mytms"] += int(_to_bool(t["mytms_signed"]))
        b["module_completed"]["mytms"] += int(_to_bool(t["mytms_completed"]))
        b["module_signed"]["game_day"] += int(_to_bool(t["game_day_signed"]))
        b["module_completed"]["game_day"] += int(_to_bool(t["game_day_completed"]))
        b["module_signed"]["hackathon"] += int(_to_bool(t["hackathon_signed"]))
        b["module_completed"]["hackathon"] += int(_to_bool(t["hackathon_completed"]))
        b["module_signed"]["cert"] += int(_to_bool(t["received_cert_voucher"]))
        b["module_completed"]["cert"] += int(_to_bool(t["completed_cert_voucher"]))

        for qid in ["Q1", "Q2", "Q3", "Q4", "Q5", "Q6", "Q7", "Q9", "Q10", "Q11"]:
            score = rec["satisfaction"].get(qid)
            if isinstance(score, (int, float)):
                if qid not in b["q_scores"]:
                    b["q_scores"][qid] = []
                b["q_scores"][qid].append(score)

    result = []
    for year, b in sorted(buckets.items()):
        count = len(b["employees"])
        avg_q = {
            qid: round(sum(scores) / len(scores), 2)
            for qid, scores in b["q_scores"].items() if scores
        }
        all_numeric = [v for v in avg_q.values()]
        completion_rates = {}
        for module in b["module_signed"]:
            signed = b["module_signed"][module]
            completed = b["module_completed"][module]
            completion_rates[module] = {
                "signed": signed,
                "completed": completed,
                "rate_pct": round((completed / signed * 100), 1) if signed else 0,
            }
        result.append({
            "year": year,
            "employee_count": count,
            "total_cost_eur": round(b["total_cost_eur"], 2),
            "avg_cost_per_employee_eur": round(b["total_cost_eur"] / count, 2) if count else 0,
            "completion_rates": completion_rates,
            "avg_satisfaction_overall": round(sum(all_numeric) / len(all_numeric), 2) if all_numeric else None,
            "avg_by_question": avg_q,
        })

    return result


def _aggregate_by_stream(records: list[dict]) -> list[dict]:
    buckets: dict[str, dict] = {}

    for rec in records:
        stream = rec.get("stream", "Unknown")
        if stream not in buckets:
            buckets[stream] = {
                "stream": stream,
                "count": 0,
                "total_cost_eur": 0.0,
                "avg_scores": [],
                "completion_counts": 0,
                "total_modules": 0,
            }
        b = buckets[stream]
        b["count"] += 1
        b["total_cost_eur"] += rec["training"]["total_cost_eur"]
        avg = rec["satisfaction"].get("avg_numeric_score")
        if avg is not None:
            b["avg_scores"].append(avg)

        # Count completed modules out of max 5 (excl. hackathon at €0)
        t = rec["training"]
        modules_done = sum([
            int(_to_bool(t["skillbuilder_completed"])),
            int(_to_bool(t["instructor_completed"])),
            int(_to_bool(t["mytms_completed"])),
            int(_to_bool(t["game_day_completed"])),
            int(_to_bool(t["completed_cert_voucher"])),
        ])
        b["completion_counts"] += modules_done
        b["total_modules"] += 5

    result = []
    for stream, b in sorted(buckets.items(), key=lambda x: -x[1]["count"]):
        count = b["count"]
        result.append({
            "stream": stream,
            "employee_count": count,
            "total_cost_eur": round(b["total_cost_eur"], 2),
            "avg_cost_per_employee_eur": round(b["total_cost_eur"] / count, 2) if count else 0,
            "avg_satisfaction": round(sum(b["avg_scores"]) / len(b["avg_scores"]), 2) if b["avg_scores"] else None,
            "avg_module_completion_pct": round(b["completion_counts"] / b["total_modules"] * 100, 1) if b["total_modules"] else 0,
        })

    return result


def _module_overall_stats(records: list[dict]) -> dict:
    modules = {
        "skillbuilder": {"signed": 0, "completed": 0, "cost_eur": DEFAULT_COSTS["skillbuilder"]},
        "instructor": {"signed": 0, "completed": 0, "cost_eur": DEFAULT_COSTS["instructor"]},
        "mytms": {"signed": 0, "completed": 0, "cost_eur": DEFAULT_COSTS["mytms"]},
        "game_day": {"signed": 0, "completed": 0, "cost_eur": DEFAULT_COSTS["game_day"]},
        "hackathon": {"signed": 0, "completed": 0, "cost_eur": DEFAULT_COSTS["hackathon"]},
        "cert": {"signed": 0, "completed": 0, "cost_eur": DEFAULT_COSTS["foundational_cert"]},
    }
    for rec in records:
        t = rec["training"]
        modules["skillbuilder"]["signed"] += int(_to_bool(t["skillbuilder_signed"]))
        modules["skillbuilder"]["completed"] += int(_to_bool(t["skillbuilder_completed"]))
        modules["instructor"]["signed"] += int(_to_bool(t["instructor_signed"]))
        modules["instructor"]["completed"] += int(_to_bool(t["instructor_completed"]))
        modules["mytms"]["signed"] += int(_to_bool(t["mytms_signed"]))
        modules["mytms"]["completed"] += int(_to_bool(t["mytms_completed"]))
        modules["game_day"]["signed"] += int(_to_bool(t["game_day_signed"]))
        modules["game_day"]["completed"] += int(_to_bool(t["game_day_completed"]))
        modules["hackathon"]["signed"] += int(_to_bool(t["hackathon_signed"]))
        modules["hackathon"]["completed"] += int(_to_bool(t["hackathon_completed"]))
        modules["cert"]["signed"] += int(_to_bool(t["received_cert_voucher"]))
        modules["cert"]["completed"] += int(_to_bool(t["completed_cert_voucher"]))

    for m, vals in modules.items():
        s = vals["signed"]
        c = vals["completed"]
        vals["completion_rate_pct"] = round(c / s * 100, 1) if s else 0
        vals["drop_off_rate_pct"] = round((s - c) / s * 100, 1) if s else 0
        vals["total_spend_eur"] = round(c * vals["cost_eur"], 2)

    return modules


def _categorical_distribution(records: list[dict], question_id: str) -> dict:
    dist: dict[str, int] = {}
    for rec in records:
        val = rec["satisfaction"].get(question_id)
        if val is not None:
            key = str(val)
            dist[key] = dist.get(key, 0) + 1
    return dist


# ── NEW: Satisfaction Band Classification ────────────────────────────────────────

def _classify_satisfaction_bands(records: list[dict]) -> dict:
    """
    Classify employees into satisfaction bands from the mind map:
    0-3 Dissatisfied | 4-6 Somewhat Satisfied | 6-8 Satisfied | 9-10 Extremely Satisfied
    """
    band_order = [
        "Dissatisfied (0-3)",
        "Somewhat Satisfied (4-6)",
        "Satisfied (6-8)",
        "Extremely Satisfied (9-10)",
    ]

    def _get_band(score):
        if score is None:
            return None
        if score <= 3:
            return "Dissatisfied (0-3)"
        elif score <= 6:
            return "Somewhat Satisfied (4-6)"
        elif score <= 8:
            return "Satisfied (6-8)"
        else:
            return "Extremely Satisfied (9-10)"

    overall = {b: 0 for b in band_order}
    by_year: dict[str, dict] = {}

    for rec in records:
        score = rec["satisfaction"].get("avg_numeric_score")
        band = _get_band(score)
        if not band:
            continue
        overall[band] += 1
        year = str(rec.get("year_enrolled") or "Unknown")
        if year not in by_year:
            by_year[year] = {b: 0 for b in band_order}
        by_year[year][band] += 1

    return {"overall": overall, "by_year": by_year, "band_order": band_order}


# ── NEW: ROI Score Calculation ────────────────────────────────────────────────

def _calculate_roi_scores(records: list[dict], by_stream: list[dict]) -> dict:
    """
    ROI Score = (Satisfaction_norm x Completion_norm) / Cost_norm
    Normalised to 0-1. Higher score = better value for money.
    Computed at stream level (scatter plot) and year level (trend).
    """
    if not by_stream:
        return {"by_stream": [], "by_year": []}

    max_cost = max(
        (s["avg_cost_per_employee_eur"] for s in by_stream if s["avg_cost_per_employee_eur"] > 0),
        default=1,
    )

    scored_streams = []
    for s in by_stream:
        cost = s["avg_cost_per_employee_eur"] or 0
        sat = s["avg_satisfaction"] or 0
        comp = s["avg_module_completion_pct"] or 0
        sat_norm = sat / 10
        comp_norm = comp / 100
        cost_norm = cost / max_cost if max_cost > 0 else 0
        roi = round((sat_norm * comp_norm) / cost_norm, 4) if cost_norm > 0 else 0
        scored_streams.append({
            "stream": s["stream"],
            "employee_count": s["employee_count"],
            "avg_cost_eur": round(cost, 2),
            "avg_satisfaction": sat,
            "avg_completion_pct": comp,
            "roi_score": roi,
        })

    scored_streams.sort(key=lambda x: -x["roi_score"])
    for i, s in enumerate(scored_streams):
        s["rank"] = i + 1

    # Per-year ROI
    year_buckets: dict[int, dict] = {}
    for rec in records:
        year = rec.get("year_enrolled")
        if not year:
            continue
        if year not in year_buckets:
            year_buckets[year] = {"costs": [], "sats": [], "comps": []}
        b = year_buckets[year]
        b["costs"].append(rec["training"]["total_cost_eur"])
        avg_s = rec["satisfaction"].get("avg_numeric_score")
        if avg_s is not None:
            b["sats"].append(avg_s)
        t = rec["training"]
        modules_done = sum([
            int(_to_bool(t["skillbuilder_completed"])),
            int(_to_bool(t["instructor_completed"])),
            int(_to_bool(t["mytms_completed"])),
            int(_to_bool(t["game_day_completed"])),
            int(_to_bool(t["completed_cert_voucher"])),
        ])
        b["comps"].append(modules_done / 5 * 100)

    max_year_cost = max(
        (sum(b["costs"]) / len(b["costs"]) for b in year_buckets.values() if b["costs"]),
        default=1,
    )
    year_roi = []
    for year, b in sorted(year_buckets.items()):
        avg_cost = sum(b["costs"]) / len(b["costs"]) if b["costs"] else 0
        avg_sat = sum(b["sats"]) / len(b["sats"]) if b["sats"] else 0
        avg_comp = sum(b["comps"]) / len(b["comps"]) if b["comps"] else 0
        sat_norm = avg_sat / 10
        comp_norm = avg_comp / 100
        cost_norm = avg_cost / max_year_cost if max_year_cost > 0 else 0
        roi = round((sat_norm * comp_norm) / cost_norm, 4) if cost_norm > 0 else 0
        year_roi.append({
            "year": year,
            "avg_cost_eur": round(avg_cost, 2),
            "avg_satisfaction": round(avg_sat, 2),
            "avg_completion_pct": round(avg_comp, 2),
            "roi_score": roi,
        })

    return {"by_stream": scored_streams, "by_year": year_roi}


# ── NEW: Success Factors Analysis ─────────────────────────────────────────────

def _success_factors(records: list[dict]) -> dict:
    """
    Classify employees as Successful or Unsuccessful.
    Successful = completed >= 4 of 5 modules AND avg satisfaction >= 7.
    Then segment by stream, role, experience bucket, year, and cloud type.
    """
    def _is_successful(rec: dict) -> bool:
        t = rec["training"]
        modules_done = sum([
            int(_to_bool(t["skillbuilder_completed"])),
            int(_to_bool(t["instructor_completed"])),
            int(_to_bool(t["mytms_completed"])),
            int(_to_bool(t["game_day_completed"])),
            int(_to_bool(t["completed_cert_voucher"])),
        ])
        avg_score = rec["satisfaction"].get("avg_numeric_score") or 0
        return modules_done >= 4 and avg_score >= 7

    def _exp_bucket(years) -> str:
        try:
            y = int(years)
        except (TypeError, ValueError):
            return "Unknown"
        if y <= 3:   return "0-3 yrs"
        elif y <= 7: return "4-7 yrs"
        elif y <= 12: return "8-12 yrs"
        elif y <= 20: return "13-20 yrs"
        else:         return "20+ yrs"

    def _group(key_fn, label):
        buckets: dict[str, dict] = {}
        for rec in records:
            k = str(key_fn(rec) or "Unknown")
            if k not in buckets:
                buckets[k] = {"successful": 0, "unsuccessful": 0}
            if _is_successful(rec):
                buckets[k]["successful"] += 1
            else:
                buckets[k]["unsuccessful"] += 1
        result = []
        for k, b in sorted(buckets.items(), key=lambda x: -(x[1]["successful"] + x[1]["unsuccessful"])):
            total = b["successful"] + b["unsuccessful"]
            result.append({
                label: k,
                "successful": b["successful"],
                "unsuccessful": b["unsuccessful"],
                "total": total,
                "success_rate_pct": round(b["successful"] / total * 100, 1) if total else 0,
            })
        return result

    successful_count = sum(1 for r in records if _is_successful(r))
    return {
        "definition": "Successful = completed >= 4 of 5 modules AND avg satisfaction >= 7",
        "total_successful": successful_count,
        "total_unsuccessful": len(records) - successful_count,
        "overall_success_rate_pct": round(successful_count / len(records) * 100, 1) if records else 0,
        "by_stream": _group(lambda r: r.get("stream"), "stream"),
        "by_role": _group(lambda r: r.get("role"), "role"),
        "by_experience": _group(lambda r: _exp_bucket(r.get("years_experience")), "experience_bucket"),
        "by_year": _group(lambda r: str(r.get("year_enrolled") or "Unknown"), "year"),
        "by_cloud_type": _group(lambda r: r.get("cloud_type"), "cloud_type"),
    }


# ── NEW: Data Quality Metrics ─────────────────────────────────────────────────

def _data_quality_metrics(employees_raw: list, costs_raw: list, q_answers_raw: list, records: list[dict]) -> dict:
    """
    Surface data quality stats so the dashboard can show trust indicators.
    """
    total_emp = len(employees_raw)
    missing_year = sum(1 for e in employees_raw if not _normalise_year(e.get("Year Enrolled")))
    missing_stream = sum(1 for e in employees_raw if not e.get("Stream"))
    missing_emp_id = sum(1 for e in employees_raw if not e.get("Employee Number"))
    aliased_count = sum(
        1 for e in employees_raw
        if e.get("Stream") and e["Stream"].strip().lower() in STREAM_ALIASES
    )
    total_cost = len(costs_raw)
    nan_cost = sum(1 for c in costs_raw if str(c.get("total_cost_of_training", "")).upper() == "NAN")
    total_qa = len(q_answers_raw)
    missing_qa = sum(1 for r in records if not r["satisfaction"].get("Q1"))
    clean_emp = total_emp - missing_year - missing_stream - missing_emp_id
    clean_pct = round(clean_emp / total_emp * 100, 1) if total_emp else 0
    return {
        "employee_data": {
            "total_records": total_emp,
            "missing_year": missing_year,
            "missing_stream": missing_stream,
            "missing_employee_id": missing_emp_id,
            "stream_names_normalized": aliased_count,
            "clean_records": clean_emp,
            "clean_pct": clean_pct,
        },
        "cost_data": {
            "total_records": total_cost,
            "nan_total_cost_records": nan_cost,
            "note": "total_cost_of_training was NAN — recalculated by Lambda from cost keys",
        },
        "questionnaire_data": {
            "total_records": total_qa,
            "records_missing_q1": missing_qa,
        },
        "overall_quality_pct": clean_pct,
    }


# ── Lambda handler ─────────────────────────────────────────────────────────────

def lambda_handler(event, context):
    # Determine bucket from S3 trigger event or environment variable fallback
    bucket = None
    if event.get("Records"):
        bucket = event["Records"][0]["s3"]["bucket"]["name"]
    else:
        import os
        bucket = os.environ.get("DATA_BUCKET")

    if not bucket:
        raise ValueError("Could not determine S3 bucket from event or DATA_BUCKET env var")

    logger.info("Processing data from bucket: %s", bucket)

    # ── Load ──────────────────────────────────────────────────────────────────
    employees, costs, q_answers, cost_keys = _load_all_data(bucket)
    logger.info(
        "Loaded: %d employees, %d cost records, %d questionnaire responses",
        len(employees), len(costs), len(q_answers)
    )

    # ── Transform ─────────────────────────────────────────────────────────────
    records = _build_employee_records(employees, costs, q_answers, cost_keys)

    # ── Aggregate ─────────────────────────────────────────────────────────────
    by_year = _aggregate_by_year(records)
    by_stream = _aggregate_by_stream(records)
    module_stats = _module_overall_stats(records)
    q8_dist = _categorical_distribution(records, "Q8")   # Most valuable part
    q11_dist = _categorical_distribution(records, "Q11")  # Prefer Platform Academy
    q12_dist = _categorical_distribution(records, "Q12")  # External tools used

    # ── New analytical functions ───────────────────────────────────────────────
    satisfaction_bands = _classify_satisfaction_bands(records)
    roi_scores = _calculate_roi_scores(records, by_stream)
    success_factors = _success_factors(records)
    data_quality = _data_quality_metrics(employees, costs, q_answers, records)

    total_cost = round(sum(r["training"]["total_cost_eur"] for r in records), 2)
    all_avg_scores = [r["satisfaction"]["avg_numeric_score"] for r in records if r["satisfaction"]["avg_numeric_score"]]
    overall_avg_satisfaction = round(sum(all_avg_scores) / len(all_avg_scores), 2) if all_avg_scores else None

    # ── Build output ──────────────────────────────────────────────────────────
    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "total_employees": len(records),
            "total_cost_eur": total_cost,
            "years_available": sorted({r["year_enrolled"] for r in records if r["year_enrolled"]}),
            "streams_available": sorted({r["stream"] for r in records if r["stream"]}),
            "avg_satisfaction_overall": overall_avg_satisfaction,
            "overall_success_rate_pct": success_factors["overall_success_rate_pct"],
            "data_quality_pct": data_quality["overall_quality_pct"],
        },
        "by_year": by_year,
        "by_stream": by_stream,
        "module_stats": module_stats,
        "satisfaction_bands": satisfaction_bands,
        "roi_scores": roi_scores,
        "success_factors": success_factors,
        "data_quality": data_quality,
        "q8_most_valuable": q8_dist,
        "q11_prefer_platform_academy": q11_dist,
        "q12_external_tools": q12_dist,
        "employees": records,
    }

    # ── Write to S3 ───────────────────────────────────────────────────────────
    _write_json(bucket, OUTPUT_KEY, output)

    return {
        "statusCode": 200,
        "body": json.dumps({
            "message": "Processing complete",
            "employees_processed": len(records),
            "output_key": OUTPUT_KEY,
        }),
    }
