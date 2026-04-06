#!/usr/bin/env python3
"""
Database backup: pg_dump → gzip → Cloudflare R2 (S3-compatible).

Usage:
    python scripts/backup.py

Required env vars:
    DATABASE_URL           PostgreSQL connection string
    R2_ACCOUNT_ID          Cloudflare account ID
    R2_ACCESS_KEY_ID       R2 access key ID
    R2_SECRET_ACCESS_KEY   R2 secret access key
    R2_BUCKET_NAME         R2 bucket name

Optional env vars:
    BACKUP_ALERT_EMAIL     Email address to notify on failure
    SENDGRID_API_KEY       SendGrid key (used to send failure alerts)
    EMAIL_FROM             Sender address for alert emails

Retention policy:
    30 daily backups   (daily/son-of-mervan-YYYY-MM-DD.sql.gz)
    12 monthly backups (monthly/son-of-mervan-YYYY-MM.sql.gz, uploaded on the 1st of each month)

Scheduled via Railway cron:  0 3 * * *
"""
import gzip
import json
import logging
import os
import subprocess
import sys
from datetime import date, datetime
from urllib.parse import urlparse

import boto3
import requests
from botocore.client import Config

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

DAILY_KEEP = 30
MONTHLY_KEEP = 12


# ---------------------------------------------------------------------------
# R2 client
# ---------------------------------------------------------------------------

def _r2_client():
    account_id = os.environ["R2_ACCOUNT_ID"]
    return boto3.client(
        "s3",
        endpoint_url=f"https://{account_id}.r2.cloudflarestorage.com",
        aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
        config=Config(signature_version="s3v4"),
        region_name="auto",
    )


# ---------------------------------------------------------------------------
# Backup helpers
# ---------------------------------------------------------------------------

def _pg_dump_gzipped(database_url: str) -> bytes:
    """Run pg_dump and return gzip-compressed SQL."""
    parsed = urlparse(database_url)
    env = os.environ.copy()
    env["PGPASSWORD"] = parsed.password or ""

    cmd = [
        "pg_dump",
        "-h", parsed.hostname or "localhost",
        "-p", str(parsed.port or 5432),
        "-U", parsed.username or "postgres",
        "-d", parsed.path.lstrip("/"),
        "--no-password",
        "--format=plain",
    ]

    result = subprocess.run(cmd, capture_output=True, env=env)
    if result.returncode != 0:
        raise RuntimeError(f"pg_dump exited {result.returncode}: {result.stderr.decode()[:500]}")

    compressed = gzip.compress(result.stdout)
    logger.info(
        "pg_dump complete: %d bytes raw → %d bytes compressed",
        len(result.stdout),
        len(compressed),
    )
    return compressed


def _upload(client, bucket: str, key: str, data: bytes) -> None:
    client.put_object(Bucket=bucket, Key=key, Body=data)
    logger.info("Uploaded s3://%s/%s (%d bytes)", bucket, key, len(data))


def _apply_retention(client, bucket: str, prefix: str, keep: int) -> None:
    """Delete oldest objects under `prefix`, retaining `keep` most recent."""
    paginator = client.get_paginator("list_objects_v2")
    objects = []
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        objects.extend(page.get("Contents", []))

    if len(objects) <= keep:
        logger.info(
            "Retention: %d/%d objects under %s — nothing to prune",
            len(objects),
            keep,
            prefix,
        )
        return

    objects.sort(key=lambda o: o["LastModified"], reverse=True)
    to_delete = objects[keep:]
    for obj in to_delete:
        client.delete_object(Bucket=bucket, Key=obj["Key"])
        logger.info("Pruned: %s", obj["Key"])


# ---------------------------------------------------------------------------
# Failure alerting
# ---------------------------------------------------------------------------

def _send_failure_alert(error: str) -> None:
    alert_email = os.getenv("BACKUP_ALERT_EMAIL")
    if not alert_email:
        return

    api_key = os.getenv("SENDGRID_API_KEY")
    email_from = os.getenv("EMAIL_FROM", "no-reply@example.com")

    if not api_key:
        logger.error("[DEV] Backup failure alert would be sent to %s: %s", alert_email, error)
        return

    payload = {
        "personalizations": [{"to": [{"email": alert_email}]}],
        "from": {"email": email_from},
        "subject": "ALERT: Son of Mervan database backup failed",
        "content": [{
            "type": "text/plain",
            "value": (
                "The daily database backup for Son of Mervan has failed.\n\n"
                f"Error: {error}\n\n"
                f"Time (UTC): {datetime.utcnow().isoformat()}\n\n"
                "Please investigate immediately to avoid data loss."
            ),
        }],
    }

    try:
        r = requests.post(
            "https://api.sendgrid.com/v3/mail/send",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            data=json.dumps(payload),
            timeout=15,
        )
        if r.status_code in (200, 202):
            logger.info("Failure alert sent to %s", alert_email)
        else:
            logger.error("Failed to send alert: %d %s", r.status_code, r.text)
    except Exception as exc:
        logger.exception("Exception sending failure alert: %s", exc)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    database_url = os.getenv("DATABASE_URL", "")
    if not database_url or not database_url.startswith("postgresql"):
        msg = f"DATABASE_URL must be a PostgreSQL connection string; got {database_url!r}"
        logger.error(msg)
        _send_failure_alert(msg)
        sys.exit(1)

    bucket = os.environ["R2_BUCKET_NAME"]
    today = date.today()
    date_str = today.isoformat()          # YYYY-MM-DD
    month_str = today.strftime("%Y-%m")   # YYYY-MM

    try:
        logger.info("Starting backup for %s", date_str)
        data = _pg_dump_gzipped(database_url)

        client = _r2_client()

        # Daily backup — always
        daily_key = f"daily/son-of-mervan-{date_str}.sql.gz"
        _upload(client, bucket, daily_key, data)
        _apply_retention(client, bucket, "daily/", DAILY_KEEP)

        # Monthly backup — only on the 1st of the month
        if today.day == 1:
            monthly_key = f"monthly/son-of-mervan-{month_str}.sql.gz"
            _upload(client, bucket, monthly_key, data)
            _apply_retention(client, bucket, "monthly/", MONTHLY_KEEP)
            logger.info("Monthly backup written for %s", month_str)

        logger.info("Backup completed successfully")

    except Exception as exc:
        error_msg = str(exc)
        logger.exception("Backup failed: %s", error_msg)
        _send_failure_alert(error_msg)
        sys.exit(1)


if __name__ == "__main__":
    main()
