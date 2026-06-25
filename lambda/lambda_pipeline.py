"""
lambda_pipeline.py  —  DATA PIPELINE LAMBDA
────────────────────────────────────────────────────────────────────────────
Triggered by: ObjectCreated on raw/*.json

Reads all raw intake JSON files from S3, cleans and joins them, then writes
the enriched employee dataset to processed/all_data.json.

This is the foundation — all analytical Lambdas read from all_data.json.
"""
import json
import logging
from datetime import datetime, timezone

from lambda_utils import (
    DEFAULT_COSTS, STREAM_ALIASES,
    _to_bool, _normalise_stream, _normalise_year,
    _read_json, _write_json, get_bucket,
)

logger = logging.getLogger()
logger.setLevel(logging.INFO)

RAW_PREFIX  = "raw/"
OUTPUT_KEY  = "processed/all_data.json"


# ── Load all source files ─────────────────────────────────────────────────────

def _load_all_data(bucket: str):
    emp_data     = _read_json(bucket, RAW_PREFIX + "employee_data.json")     or {"employees": []}
    cost_data    = _read_json(bucket, RAW_PREFIX + "cost_data.json")         or {"costs": []}
    q_ans_raw    = _read_json(bucket, RAW_PREFIX + "questionnaire_answers.json") or []
    cost_key_raw = _read_json(bucket, RAW_PREFIX + "cost_key_data.json")     or {"cost_keys": [{}]}

    employees = list(emp_data.get("employees", []))
    costs     = list(cost_data.get("costs", []))
    q_answers = list(q_ans_raw) if isinstance(q_ans_raw, list) else []
    cost_keys = cost_key_raw.get("cost_keys", [{}])[0] if cost_key_raw.get("cost_keys") else {}

    # Merge future year files (e.g. employee_data_2026.json) when they arrive
    existing_emp  = {e.get("Employee Number") for e in employees}
    existing_cost = {c.get("employee_number") for c in costs}
    existing_qa   = {q.get("employee_number") for q in q_answers}

    for year in range(2026, 2031):
        emp_y = _read_json(bucket, f"{RAW_PREFIX}employee_data_{year}.json")
        if emp_y:
            new = [e for e in emp_y.get("employees", []) if e.get("Employee Number") not in existing_emp]
            employees.extend(new)
            existing_emp.update(e.get("Employee Number") for e in new)

        cost_y = _read_json(bucket, f"{RAW_PREFIX}cost_data_{year}.json")
        if cost_y:
            new = [c for c in cost_y.get("costs", []) if c.get("employee_number") not in existing_cost]
            costs.extend(new)
            existing_cost.update(c.get("employee_number") for c in new)

        qa_y = _read_json(bucket, f"{RAW_PREFIX}questionnaire_answers_{year}.json")
        if qa_y and isinstance(qa_y, list):
            new = [q for q in qa_y if q.get("employee_number") not in existing_qa]
            q_answers.extend(new)
            existing_qa.update(q.get("employee_number") for q in new)

    return employees, costs, q_answers, cost_keys


# ── Per-employee cost calculation ─────────────────────────────────────────────

def _calculate_cost(cost_rec: dict, cost_keys: dict) -> float:
    total = 0.0
    if _to_bool(cost_rec.get("skillbuilder_completed",  False)): total += cost_keys.get("skillbuilder_cost",      DEFAULT_COSTS["skillbuilder"])
    if _to_bool(cost_rec.get("instructor_completed",    False)): total += cost_keys.get("instructor_cost",        DEFAULT_COSTS["instructor"])
    if _to_bool(cost_rec.get("mytms_completed",         False)): total += cost_keys.get("mytms_cost",             DEFAULT_COSTS["mytms"])
    if _to_bool(cost_rec.get("game_day_completed",      False)): total += cost_keys.get("game_day_cost",          DEFAULT_COSTS["game_day"])
    if _to_bool(cost_rec.get("hackathon_completed",     False)): total += cost_keys.get("hackathon_cost",         DEFAULT_COSTS["hackathon"])
    if _to_bool(cost_rec.get("completed_cert_voucher",  False)): total += cost_keys.get("foundational_cert_cost", DEFAULT_COSTS["foundational_cert"])
    return round(total, 2)


# ── Join the three datasets into one record per employee ──────────────────────

def _build_employee_records(employees, costs, q_answers, cost_keys):
    cost_index = {c["employee_number"]: c for c in costs if c.get("employee_number")}
    qa_index   = {q["employee_number"]: q for q in q_answers if q.get("employee_number")}

    records = []
    for emp in employees:
        emp_num = emp.get("Employee Number")
        if not emp_num:
            continue

        cost_rec = cost_index.get(emp_num, {})
        qa_rec   = qa_index.get(emp_num, {})

        # Parse answers
        answers_flat  = {}
        numeric_scores = []
        for item in qa_rec.get("answers", []):
            qid = item.get("question_id")
            ans = item.get("answer")
            if qid == "Q8"  and isinstance(ans, str): ans = ans.strip().title()
            if qid == "Q11":
                if isinstance(ans, str):  ans = 1 if ans.strip().lower() in ("yes","1","true") else 0
                elif isinstance(ans, bool): ans = int(ans)
                elif ans not in (0,1):    ans = None
            if qid == "Q12" and isinstance(ans, str): ans = ans.strip()
            answers_flat[qid] = ans
            if qid not in ("Q8","Q12","Q13","Q14") and isinstance(ans, (int, float)):
                numeric_scores.append(ans)

        avg_score = round(sum(numeric_scores)/len(numeric_scores), 2) if numeric_scores else None

        records.append({
            "employee_number":  emp_num,
            "name":             emp.get("Name"),
            "surname":          emp.get("Surname"),
            "role":             emp.get("Role"),
            "department_code":  emp.get("Department Code"),
            "years_experience": emp.get("No. Years Experience"),
            "stream":           _normalise_stream(emp.get("Stream")),
            "cloud_type":       emp.get("Cloud Type"),
            "year_enrolled":    _normalise_year(emp.get("Year Enrolled")),
            "training": {
                "skillbuilder_signed":    _to_bool(cost_rec.get("skillbuilder_signed",    False)),
                "skillbuilder_completed": _to_bool(cost_rec.get("skillbuilder_completed", False)),
                "instructor_signed":      _to_bool(cost_rec.get("instructor_signed",      False)),
                "instructor_completed":   _to_bool(cost_rec.get("instructor_completed",   False)),
                "mytms_signed":           _to_bool(cost_rec.get("mytms_signed",           False)),
                "mytms_completed":        _to_bool(cost_rec.get("mytms_completed",        False)),
                "game_day_signed":        _to_bool(cost_rec.get("game_day_signed",        False)),
                "game_day_completed":     _to_bool(cost_rec.get("game_day_completed",     False)),
                "hackathon_signed":       _to_bool(cost_rec.get("hackathon_signed",       False)),
                "hackathon_completed":    _to_bool(cost_rec.get("hackathon_completed",    False)),
                "received_cert_voucher":  _to_bool(cost_rec.get("received_cert_voucher",  False)),
                "completed_cert_voucher": _to_bool(cost_rec.get("completed_cert_voucher", False)),
                "total_cost_eur":         _calculate_cost(cost_rec, cost_keys),
            },
            "satisfaction": {**answers_flat, "avg_numeric_score": avg_score},
        })

    return records


# ── Basic aggregations (used by the frontend existing charts) ─────────────────

def _aggregate_by_year(records):
    buckets = {}
    for rec in records:
        year = rec.get("year_enrolled")
        if not year: continue
        if year not in buckets:
            buckets[year] = {"employees":[], "total_cost_eur":0.0, "q_scores":{},
                             "module_signed":{m:0 for m in ["skillbuilder","instructor","mytms","game_day","hackathon","cert"]},
                             "module_completed":{m:0 for m in ["skillbuilder","instructor","mytms","game_day","hackathon","cert"]}}
        b = buckets[year]
        b["employees"].append(rec["employee_number"])
        b["total_cost_eur"] += rec["training"]["total_cost_eur"]
        t = rec["training"]
        for mod, s_key, c_key in [
            ("skillbuilder","skillbuilder_signed","skillbuilder_completed"),
            ("instructor","instructor_signed","instructor_completed"),
            ("mytms","mytms_signed","mytms_completed"),
            ("game_day","game_day_signed","game_day_completed"),
            ("hackathon","hackathon_signed","hackathon_completed"),
            ("cert","received_cert_voucher","completed_cert_voucher"),
        ]:
            b["module_signed"][mod]    += int(t[s_key])
            b["module_completed"][mod] += int(t[c_key])
        for qid in ["Q1","Q2","Q3","Q4","Q5","Q6","Q7","Q9","Q10","Q11"]:
            score = rec["satisfaction"].get(qid)
            if isinstance(score, (int,float)):
                b["q_scores"].setdefault(qid, []).append(score)

    result = []
    for year, b in sorted(buckets.items()):
        count = len(b["employees"])
        avg_q = {qid: round(sum(s)/len(s),2) for qid,s in b["q_scores"].items() if s}
        all_q = list(avg_q.values())
        comp_rates = {}
        for mod in b["module_signed"]:
            sig, comp = b["module_signed"][mod], b["module_completed"][mod]
            comp_rates[mod] = {"signed":sig,"completed":comp,
                               "rate_pct":round(comp/sig*100,1) if sig else 0,
                               "drop_off_rate_pct":round((sig-comp)/sig*100,1) if sig else 0}
        result.append({"year":year,"employee_count":count,
                        "total_cost_eur":round(b["total_cost_eur"],2),
                        "avg_cost_per_employee_eur":round(b["total_cost_eur"]/count,2) if count else 0,
                        "completion_rates":comp_rates,
                        "avg_satisfaction_overall":round(sum(all_q)/len(all_q),2) if all_q else None,
                        "avg_by_question":avg_q})
    return result


def _aggregate_by_stream(records):
    buckets = {}
    for rec in records:
        stream = rec.get("stream","Unknown")
        if stream not in buckets:
            buckets[stream] = {"count":0,"total_cost_eur":0.0,"avg_scores":[],"modules_done":0,"total_modules":0}
        b = buckets[stream]
        b["count"] += 1
        b["total_cost_eur"] += rec["training"]["total_cost_eur"]
        avg = rec["satisfaction"].get("avg_numeric_score")
        if avg is not None: b["avg_scores"].append(avg)
        t = rec["training"]
        b["modules_done"] += sum([int(t["skillbuilder_completed"]),int(t["instructor_completed"]),
                                   int(t["mytms_completed"]),int(t["game_day_completed"]),int(t["completed_cert_voucher"])])
        b["total_modules"] += 5

    result = []
    for stream, b in sorted(buckets.items(), key=lambda x: -x[1]["count"]):
        count = b["count"]
        result.append({"stream":stream,"employee_count":count,
                        "total_cost_eur":round(b["total_cost_eur"],2),
                        "avg_cost_per_employee_eur":round(b["total_cost_eur"]/count,2) if count else 0,
                        "avg_satisfaction":round(sum(b["avg_scores"])/len(b["avg_scores"]),2) if b["avg_scores"] else None,
                        "avg_module_completion_pct":round(b["modules_done"]/b["total_modules"]*100,1) if b["total_modules"] else 0})
    return result


def _module_overall_stats(records):
    modules = {m:{"signed":0,"completed":0,"cost_eur":c} for m,c in [
        ("skillbuilder",DEFAULT_COSTS["skillbuilder"]),
        ("instructor",  DEFAULT_COSTS["instructor"]),
        ("mytms",       DEFAULT_COSTS["mytms"]),
        ("game_day",    DEFAULT_COSTS["game_day"]),
        ("hackathon",   DEFAULT_COSTS["hackathon"]),
        ("cert",        DEFAULT_COSTS["foundational_cert"]),
    ]}
    for rec in records:
        t = rec["training"]
        modules["skillbuilder"]["signed"]  += int(t["skillbuilder_signed"])
        modules["skillbuilder"]["completed"]+= int(t["skillbuilder_completed"])
        modules["instructor"]["signed"]    += int(t["instructor_signed"])
        modules["instructor"]["completed"] += int(t["instructor_completed"])
        modules["mytms"]["signed"]         += int(t["mytms_signed"])
        modules["mytms"]["completed"]      += int(t["mytms_completed"])
        modules["game_day"]["signed"]      += int(t["game_day_signed"])
        modules["game_day"]["completed"]   += int(t["game_day_completed"])
        modules["hackathon"]["signed"]     += int(t["hackathon_signed"])
        modules["hackathon"]["completed"]  += int(t["hackathon_completed"])
        modules["cert"]["signed"]          += int(t["received_cert_voucher"])
        modules["cert"]["completed"]       += int(t["completed_cert_voucher"])
    for m, v in modules.items():
        s, c = v["signed"], v["completed"]
        v["completion_rate_pct"]  = round(c/s*100,1) if s else 0
        v["drop_off_rate_pct"]    = round((s-c)/s*100,1) if s else 0
        v["total_spend_eur"]      = round(c*v["cost_eur"],2)
    return modules


def _categorical_distribution(records, question_id):
    dist = {}
    for rec in records:
        val = rec["satisfaction"].get(question_id)
        if val is not None:
            dist[str(val)] = dist.get(str(val), 0) + 1
    return dist


# ── Lambda handler ─────────────────────────────────────────────────────────────

def lambda_handler(event, context):
    bucket = get_bucket(event)
    logger.info("Pipeline starting — bucket: %s", bucket)

    employees, costs, q_answers, cost_keys = _load_all_data(bucket)
    logger.info("Loaded: %d employees, %d cost records, %d questionnaire responses",
                len(employees), len(costs), len(q_answers))

    records    = _build_employee_records(employees, costs, q_answers, cost_keys)
    by_year    = _aggregate_by_year(records)
    by_stream  = _aggregate_by_stream(records)
    module_stats = _module_overall_stats(records)

    total_cost = round(sum(r["training"]["total_cost_eur"] for r in records), 2)
    all_scores = [r["satisfaction"]["avg_numeric_score"] for r in records if r["satisfaction"]["avg_numeric_score"]]
    overall_sat = round(sum(all_scores)/len(all_scores),2) if all_scores else None

    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "total_employees":      len(records),
            "total_cost_eur":       total_cost,
            "years_available":      sorted({r["year_enrolled"] for r in records if r["year_enrolled"]}),
            "streams_available":    sorted({r["stream"] for r in records if r["stream"]}),
            "avg_satisfaction_overall": overall_sat,
        },
        "by_year":       by_year,
        "by_stream":     by_stream,
        "module_stats":  module_stats,
        "q8_most_valuable":             _categorical_distribution(records, "Q8"),
        "q11_prefer_platform_academy":  _categorical_distribution(records, "Q11"),
        "q12_external_tools":           _categorical_distribution(records, "Q12"),
        "employees": records,
    }

    _write_json(bucket, OUTPUT_KEY, output)
    logger.info("Pipeline complete — %d employees processed", len(records))

    return {
        "statusCode": 200,
        "body": json.dumps({"message": "Pipeline complete", "employees_processed": len(records), "output_key": OUTPUT_KEY}),
    }
