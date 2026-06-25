"""
lambda_utils.py
────────────────────────────────────────────────────────────────────────────
Shared utilities imported by every Lambda in this project.
Each Lambda ZIP must include both its own .py file AND this file.
"""
import json
import boto3
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

s3 = boto3.client("s3")

# ── Cost keys (fallback if cost_key_data.json is missing) ────────────────────
DEFAULT_COSTS = {
    "skillbuilder":      123.80,
    "instructor":        208.00,
    "mytms":              50.00,
    "game_day":          305.00,
    "hackathon":           0.00,
    "foundational_cert": 150.00,
}

# ── Stream name aliases (normalise inconsistent values in the raw data) ───────
STREAM_ALIASES = {
    "datascience":              "Data Science",
    "solutions architect":      "Solutions Architecture",
    "cloud ops / reliability":  "Cloud Operations / Reliability",
    "cloud ops/reliability":    "Cloud Operations / Reliability",
}


def _to_bool(val) -> bool:
    """Handle True/False booleans, 'TRUE'/'FALSE' strings, and 1/0 integers."""
    if isinstance(val, bool):
        return val
    if isinstance(val, str):
        return val.strip().upper() == "TRUE"
    return bool(val)


def _normalise_stream(raw) -> str:
    if not raw:
        return "Unknown"
    return STREAM_ALIASES.get(raw.strip().lower(), raw.strip())


def _normalise_year(raw) -> int | None:
    try:
        year = int(str(raw).strip())
        return year if year > 2000 else None
    except (ValueError, TypeError):
        return None


def _read_json(bucket: str, key: str):
    """Download an S3 object and parse JSON, handling UTF-8 BOM."""
    try:
        response = s3.get_object(Bucket=bucket, Key=key)
        text = response["Body"].read().decode("utf-8-sig")
        return json.loads(text)
    except s3.exceptions.NoSuchKey:
        logger.warning("S3 key not found: s3://%s/%s — skipping", bucket, key)
        return None
    except Exception as exc:
        logger.error("Failed to read s3://%s/%s: %s", bucket, key, exc)
        return None


def _write_json(bucket: str, key: str, data: dict):
    """Serialise data to JSON and write to S3."""
    body = json.dumps(data, ensure_ascii=False, default=str)
    s3.put_object(
        Bucket=bucket,
        Key=key,
        Body=body.encode("utf-8"),
        ContentType="application/json",
        CacheControl="no-cache",
    )
    logger.info("Written → s3://%s/%s", bucket, key)


def get_bucket(event) -> str:
    """Extract the S3 bucket name from an S3 trigger event or env var."""
    if event.get("Records"):
        return event["Records"][0]["s3"]["bucket"]["name"]
    import os
    bucket = os.environ.get("DATA_BUCKET")
    if not bucket:
        raise ValueError("Could not determine S3 bucket from event or DATA_BUCKET env var")
    return bucket
