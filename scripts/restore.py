#!/usr/bin/env python3
"""
Database restore: download from Cloudflare R2 → gunzip → psql.

Usage:
    python scripts/restore.py list
        List all available backups in R2.

    python scripts/restore.py restore daily/son-of-mervan-2026-04-06.sql.gz [--dry-run] [--yes]
        Restore the specified backup. Prompts for confirmation unless --yes is supplied.
        --dry-run previews what would happen without touching the database.

Required env vars:
    DATABASE_URL           PostgreSQL connection string
    R2_ACCOUNT_ID          Cloudflare account ID
    R2_ACCESS_KEY_ID       R2 access key ID
    R2_SECRET_ACCESS_KEY   R2 secret access key
    R2_BUCKET_NAME         R2 bucket name
"""
import argparse
import gzip
import logging
import os
import subprocess
import sys
from urllib.parse import urlparse

import boto3
from botocore.client import Config

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


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
# Commands
# ---------------------------------------------------------------------------

def cmd_list(_args: argparse.Namespace) -> None:
    """Print all available backups grouped by prefix."""
    bucket = os.environ["R2_BUCKET_NAME"]
    client = _r2_client()

    for prefix in ("daily/", "monthly/"):
        paginator = client.get_paginator("list_objects_v2")
        objects = []
        for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
            objects.extend(page.get("Contents", []))

        objects.sort(key=lambda o: o["LastModified"], reverse=True)
        label = prefix.rstrip("/")
        print(f"\n{'─' * 60}")
        print(f"  {label} ({len(objects)} backup(s))")
        print(f"{'─' * 60}")

        if not objects:
            print("  (none)")
            continue

        for obj in objects:
            size_mb = obj["Size"] / 1024 / 1024
            modified = obj["LastModified"].strftime("%Y-%m-%d %H:%M UTC")
            print(f"  {obj['Key']:<52}  {size_mb:6.1f} MB  {modified}")

    print()


def cmd_restore(args: argparse.Namespace) -> None:
    """Download a backup from R2 and pipe it through psql."""
    database_url = os.getenv("DATABASE_URL", "")
    if not database_url or not database_url.startswith("postgresql"):
        logger.error("DATABASE_URL must be a PostgreSQL connection string; got %r", database_url)
        sys.exit(1)

    bucket = os.environ["R2_BUCKET_NAME"]
    key = args.key
    dry_run: bool = args.dry_run

    if dry_run:
        logger.info("[DRY RUN] Would download s3://%s/%s", bucket, key)
        logger.info("[DRY RUN] Would decompress backup and pipe to psql")
        logger.info("[DRY RUN] Target database: %s", database_url.split("@")[-1])
        logger.info("[DRY RUN] No changes made.")
        return

    # Safety confirmation
    if not args.yes:
        print(
            f"\n\033[1;31mWARNING\033[0m: This will restore the database from:\n"
            f"  {key}\n\n"
            f"  Target: {database_url.split('@')[-1]}\n\n"
            "  ALL CURRENT DATA WILL BE OVERWRITTEN.\n"
        )
        confirm = input("Type 'yes' to continue: ").strip()
        if confirm.lower() != "yes":
            print("Aborted.")
            sys.exit(0)

    client = _r2_client()

    logger.info("Downloading s3://%s/%s ...", bucket, key)
    response = client.get_object(Bucket=bucket, Key=key)
    compressed = response["Body"].read()
    logger.info("Downloaded %d bytes (compressed)", len(compressed))

    sql_bytes = gzip.decompress(compressed)
    logger.info("Decompressed: %d bytes", len(sql_bytes))

    parsed = urlparse(database_url)
    env = os.environ.copy()
    env["PGPASSWORD"] = parsed.password or ""

    cmd = [
        "psql",
        "-h", parsed.hostname or "localhost",
        "-p", str(parsed.port or 5432),
        "-U", parsed.username or "postgres",
        "-d", parsed.path.lstrip("/"),
        "--no-password",
        "--single-transaction",
    ]

    logger.info("Restoring via psql...")
    result = subprocess.run(cmd, input=sql_bytes, capture_output=True, env=env)

    if result.returncode != 0:
        logger.error("psql failed (exit %d): %s", result.returncode, result.stderr.decode()[:1000])
        sys.exit(1)

    logger.info("Restore completed successfully.")
    if result.stdout:
        output = result.stdout.decode()[:1000]
        logger.info("psql output (truncated):\n%s", output)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Son-of-Mervan database restore CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python scripts/restore.py list\n"
            "  python scripts/restore.py restore daily/son-of-mervan-2026-04-06.sql.gz --dry-run\n"
            "  python scripts/restore.py restore daily/son-of-mervan-2026-04-06.sql.gz --yes\n"
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list", help="List available backups in R2")

    restore_p = sub.add_parser("restore", help="Restore a specific backup from R2")
    restore_p.add_argument(
        "key",
        help="R2 object key, e.g. daily/son-of-mervan-2026-04-06.sql.gz",
    )
    restore_p.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would happen without making any changes",
    )
    restore_p.add_argument(
        "--yes", "-y",
        action="store_true",
        help="Skip the interactive confirmation prompt",
    )

    args = parser.parse_args()
    dispatch = {"list": cmd_list, "restore": cmd_restore}
    dispatch[args.command](args)


if __name__ == "__main__":
    main()
