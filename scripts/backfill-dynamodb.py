#!/usr/bin/env python3
"""Augment items with bucketed GSI attributes for higher read fan-out.

This script is used to backfill the CIS DynamoDB with attriubtes that support
a use of search queries for both a single and multiple partition throughput.

- connection_name (S): derived from the `id` prefix up to the last '|'
- id_hash_bin (B): 32-byte SHA-256 of 'id' (binary)
- bucket_hex2  (S): first byte of id_hash_bin as two hex chars: '00'..'ff'
- cn_bucket    (S): "{connection_name}#{bucket_hex2}"
- active_bucket(S): present only when active==True (equals cn_bucket);
                    removed when not active

Operations:
- backfill (default): add/update attributes if missing or incorrect
- remove: remove the attributes (including `connection_name`) if present
- verify: report items needing changes

The script uses a Parallel Scan with N segments and shows per-segment and
overall progress via Rich. Updates are idempotent and guarded with a
ConditionExpression to avoid accidental upserts.

Example:

    python backfill-dynamodb.py \
      --table-name temp-identity-vault-2 \
      --region us-east-1 \
      --segments 8 \
      --op backfill

Notes:
- AWS auth is picked up from env, profile, or SSO session.
- Consumed capacity is recorded for scans and updates.
"""

from __future__ import annotations

import argparse
import hashlib
import math
import os
import sys
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Dict, Optional, Tuple

import boto3
from boto3.dynamodb.types import Binary
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError
from rich.console import Console
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)
from rich.table import Table


# ------------------------------ Data types ------------------------------- #

NEW_ATTRS = (
    "connection_name",
    "id_hash_bin",
    "bucket_hex2",
    "cn_bucket",
    "active_bucket",
)


@dataclass
class Metrics:
    seen: int = 0
    updated: int = 0
    would_fix: int = 0
    errors: int = 0
    scan_pages: int = 0
    scan_rcus: Decimal = Decimal("0")
    update_cus: Decimal = Decimal("0")
    error_by_code: Dict[str, int] = field(default_factory=dict)

    def merge(self, other: "Metrics") -> None:
        self.seen += other.seen
        self.updated += other.updated
        self.would_fix += other.would_fix
        self.errors += other.errors
        self.scan_pages += other.scan_pages
        self.scan_rcus += other.scan_rcus
        self.update_cus += other.update_cus
        for k, v in other.error_by_code.items():
            self.error_by_code[k] = self.error_by_code.get(k, 0) + v


# ------------------------------ Helpers --------------------------------- #

def derive_connection_name_from_id(item_id: str) -> str:
    """Return prefix before the last '|' in id; if none, return whole id."""
    if not item_id:
        return ""
    pos = item_id.rfind("|")
    if pos == -1:
        return item_id
    return item_id[:pos]


def _as_bytes(val) -> Optional[bytes]:
    if val is None:
        return None
    if isinstance(val, (bytes, bytearray, memoryview)):
        return bytes(val)
    try:
        if isinstance(val, Binary):
            return bytes(val)
    except Exception:
        pass
    return None


def compute_bucket_fields(
    item: Dict,
) -> Tuple[bytes, str, str, Optional[str], str]:
    """Compute id_hash_bin, bucket_hex2, cn_bucket, active_bucket (or None),
    and canonical connection_name from id.
    """
    item_id = item.get("id", "")
    if not item_id:
        raise ValueError("Item missing 'id'")

    h_bin = hashlib.sha256(item_id.encode("utf-8")).digest()
    bucket_hex2 = h_bin[:1].hex()  # '00'..'ff'

    # Always build cn_bucket from canonical connection_name
    cn_canonical = derive_connection_name_from_id(item_id)
    cn_bucket = f"{cn_canonical}#{bucket_hex2}"

    is_active = bool(item.get("active", False))
    active_bucket = cn_bucket if is_active else None

    return h_bin, bucket_hex2, cn_bucket, active_bucket, cn_canonical


def build_update_for_item(
    item: Dict, *, remove_mode: bool = False
) -> Optional[Dict]:
    """Build minimal UpdateItem kwargs for this item, or None if noop."""
    key_id = item.get("id")
    if not key_id:
        return None

    if remove_mode:
        names: Dict[str, str] = {}
        remove_clauses = []
        for a in NEW_ATTRS:
            if a in item:
                alias = f"#{a}"
                names[alias] = a
                remove_clauses.append(alias)
        if not remove_clauses:
            return None
        update_expr = "REMOVE " + ", ".join(remove_clauses)
        return {
            "Key": {"id": key_id},
            "UpdateExpression": update_expr,
            "ExpressionAttributeNames": names if names else None,
            "ConditionExpression": "attribute_exists(#id)",
            "ExpressionAttributeNames_additional": {"#id": "id"},
        }

    try:
        h_bin, bucket_hex2, cn_bucket, active_bucket, cn_canonical = (
            compute_bucket_fields(item)
        )
    except Exception:
        return None

    names: Dict[str, str] = {}
    values: Dict[str, object] = {}

    set_clauses = []
    remove_clauses = []

    # connection_name must match canonical
    if item.get("connection_name") != cn_canonical:
        names["#connection_name"] = "connection_name"
        values[":connection_name"] = cn_canonical
        set_clauses.append("#connection_name = :connection_name")

    # Compare binary by bytes
    existing_bin = _as_bytes(item.get("id_hash_bin"))
    if existing_bin != h_bin:
        names["#id_hash_bin"] = "id_hash_bin"
        values[":id_hash_bin"] = Binary(h_bin)
        set_clauses.append("#id_hash_bin = :id_hash_bin")

    if item.get("bucket_hex2") != bucket_hex2:
        names["#bucket_hex2"] = "bucket_hex2"
        values[":bucket_hex2"] = bucket_hex2
        set_clauses.append("#bucket_hex2 = :bucket_hex2")

    if item.get("cn_bucket") != cn_bucket:
        names["#cn_bucket"] = "cn_bucket"
        values[":cn_bucket"] = cn_bucket
        set_clauses.append("#cn_bucket = :cn_bucket")

    if active_bucket is not None:
        if item.get("active_bucket") != active_bucket:
            names["#active_bucket"] = "active_bucket"
            values[":active_bucket"] = active_bucket
            set_clauses.append("#active_bucket = :active_bucket")
    else:
        if "active_bucket" in item:
            names["#active_bucket"] = "active_bucket"
            remove_clauses.append("#active_bucket")

    if not set_clauses and not remove_clauses:
        return None

    parts = []
    if set_clauses:
        parts.append("SET " + ", ".join(set_clauses))
    if remove_clauses:
        parts.append("REMOVE " + ", ".join(remove_clauses))
    update_expr = " ".join(parts)

    kw: Dict[str, object] = {
        "Key": {"id": key_id},
        "UpdateExpression": update_expr,
        "ConditionExpression": "attribute_exists(#id)",
        "ExpressionAttributeNames_additional": {"#id": "id"},
    }
    if names:
        kw["ExpressionAttributeNames"] = names
    if values:
        kw["ExpressionAttributeValues"] = values
    return kw


def apply_update(
    table,
    update_kwargs: Dict,
    *,
    dry_run: bool = False,
) -> Tuple[Decimal, Optional[Dict]]:
    """Execute UpdateItem. Return (consumed capacity, error info or None)."""
    if not update_kwargs:
        return Decimal("0"), None

    # Merge extra EANs if present
    ean = update_kwargs.get("ExpressionAttributeNames", {})
    extra = update_kwargs.pop("ExpressionAttributeNames_additional", {})
    if extra:
        ean = {**ean, **extra}
        update_kwargs["ExpressionAttributeNames"] = ean

    if dry_run:
        return Decimal("0"), None

    try:
        resp = table.update_item(
            ReturnValues="NONE",
            ReturnConsumedCapacity="TOTAL",
            **update_kwargs,
        )
        cc = resp.get("ConsumedCapacity") or {}
        cu = Decimal(str(cc.get("CapacityUnits", 0)))
        return cu, None
    except ClientError as exc:
        return Decimal("0"), {
            "code": exc.response.get("Error", {}).get("Code", "ClientError"),
            "message": exc.response.get("Error", {}).get("Message", str(exc)),
        }
    except BotoCoreError as exc:
        return Decimal("0"), {"code": "BotoCoreError", "message": str(exc)}


# ------------------------------ UI helpers ------------------------------- #

def _op_style(op: str) -> Tuple[str, str]:
    """Return (label, color) for the progress header based on --op."""
    if op == "backfill":
        return ("backfill", "blue")
    if op == "verify":
        return ("verify", "yellow")
    if op == "remove":
        return ("remove", "red")
    return (op, "blue")


def _summarize_errors(console: Console, error_by_code: Dict[str, int]) -> None:
    if not error_by_code:
        return
    tbl = Table(title="Error Breakdown", expand=True)
    tbl.add_column("Error code")
    tbl.add_column("Count", justify="right")
    for code, cnt in sorted(error_by_code.items(), key=lambda x: (-x[1], x[0])):
        tbl.add_row(code, f"{cnt:,}")
    console.print(tbl)


def _format_update_expr_for_log(update_kwargs: Dict) -> str:
    if not update_kwargs:
        return "<none>"
    ue = update_kwargs.get("UpdateExpression", "")
    ean = list((update_kwargs.get("ExpressionAttributeNames") or {}).keys())
    eav = update_kwargs.get("ExpressionAttributeValues") or {}
    parts = [f"UpdateExpression={ue!r}"]
    if ean:
        parts.append(f"EAN={sorted(ean)!r}")
    if eav:
        red = {}
        for k, v in eav.items():
            if isinstance(v, Binary):
                red[k] = f"Binary({len(bytes(v))} bytes)"
            elif isinstance(v, (bytes, bytearray, memoryview)):
                red[k] = f"bytes({len(v)})"
            else:
                s = str(v)
                red[k] = s if len(s) <= 32 else s[:29] + "..."
        parts.append(f"EAV={red!r}")
    return "; ".join(parts)


# ------------------------------ Workers --------------------------------- #

def process_item(
    table,
    item: Dict,
    args: argparse.Namespace,
    metrics: Metrics,
    console: Console,
    stop_event: threading.Event,
    shared_err_counter: Dict[str, object],
) -> None:
    metrics.seen += 1
    if stop_event.is_set():
        return

    try:
        if args.op == "remove":
            upd = build_update_for_item(item, remove_mode=True)
            cu, err = apply_update(table, upd, dry_run=args.dry_run)
            if err:
                metrics.errors += 1
                code = err.get("code", "Error")
                metrics.error_by_code[code] = metrics.error_by_code.get(code, 0) + 1
                if args.verbose:
                    if args.verbose > 1 or shared_err_counter["printed"] < 10:
                        item_id = item.get("id", "<no-id>")
                        console.print(
                            f"[red]ERROR[/] {code}: {err.get('message','')} "
                            f"on id=[cyan]{item_id}[/]"
                        )
                        if args.log_update_expr:
                            console.print(
                                f"        { _format_update_expr_for_log(upd) }"
                            )
                        shared_err_counter["printed"] += 1
                with shared_err_counter["lock"]:
                    shared_err_counter["count"] += 1
                    if shared_err_counter["count"] >= args.abort_after_errors:
                        stop_event.set()
                return
            metrics.update_cus += cu
            metrics.updated += 1
            return

        # backfill / verify
        upd = build_update_for_item(item, remove_mode=False)
        if args.op == "verify":
            if upd:
                metrics.would_fix += 1
            return

        cu, err = apply_update(table, upd, dry_run=args.dry_run)
        if err:
            metrics.errors += 1
            code = err.get("code", "Error")
            metrics.error_by_code[code] = metrics.error_by_code.get(code, 0) + 1
            if args.verbose:
                if args.verbose > 1 or shared_err_counter["printed"] < 10:
                    item_id = item.get("id", "<no-id>")
                    console.print(
                        f"[red]ERROR[/] {code}: {err.get('message','')} "
                        f"on id=[cyan]{item_id}[/]"
                    )
                    if args.log_update_expr:
                        console.print(
                            f"        { _format_update_expr_for_log(upd) }"
                        )
                    shared_err_counter["printed"] += 1
            with shared_err_counter["lock"]:
                shared_err_counter["count"] += 1
                if shared_err_counter["count"] >= args.abort_after_errors:
                    stop_event.set()
            return

        metrics.update_cus += cu
        if upd:
            metrics.updated += 1

    except Exception as exc:  # catch-all to surface unexpected issues
        metrics.errors += 1
        code = type(exc).__name__
        metrics.error_by_code[code] = metrics.error_by_code.get(code, 0) + 1
        if args.verbose:
            item_id = item.get("id", "<no-id>")
            console.print(
                f"[red]ERROR[/] {code}: {exc} on id=[cyan]{item_id}[/]"
            )
        with shared_err_counter["lock"]:
            shared_err_counter["count"] += 1
            if shared_err_counter["count"] >= args.abort_after_errors:
                stop_event.set()
        return


def scan_segment(
    table,
    segment: int,
    total_segments: int,
    args: argparse.Namespace,
    progress: Progress,
    overall_task: int,
    seg_task: int,
    per_seg_total: Optional[int],
    console: Console,
    stop_event: threading.Event,
    shared_err_counter: Dict[str, object],
) -> Metrics:
    metrics = Metrics()
    key = None

    while not stop_event.is_set():
        params = {
            "Segment": segment,
            "TotalSegments": total_segments,
            "ReturnConsumedCapacity": "TOTAL",
        }
        if args.page_limit:
            params["Limit"] = int(args.page_limit)
        if key:
            params["ExclusiveStartKey"] = key

        resp = table.scan(**params)

        metrics.scan_pages += 1
        cc = resp.get("ConsumedCapacity") or {}
        cu = Decimal(str(cc.get("CapacityUnits", 0)))
        metrics.scan_rcus += cu

        items = resp.get("Items", [])
        for it in items:
            if stop_event.is_set():
                break
            process_item(
                table, it, args, metrics, console, stop_event, shared_err_counter
            )

        scanned_now = int(resp.get("ScannedCount", len(items)))
        progress.update(seg_task, advance=max(scanned_now, 1))
        progress.update(overall_task, advance=max(scanned_now, 1))

        key = resp.get("LastEvaluatedKey")
        if not key:
            break

    # Force-complete this segment bar so UI shows 100% for the shard
    if per_seg_total is not None:
        progress.update(seg_task, completed=per_seg_total)
    else:
        progress.stop_task(seg_task)

    return metrics


# --------------------------------- Main --------------------------------- #

def _make_boto3(region: Optional[str], profile: Optional[str]):
    if profile:
        session = boto3.Session(profile_name=profile, region_name=region)
    else:
        session = boto3.Session(region_name=region)
    cfg = Config(retries={"max_attempts": 10, "mode": "standard"})
    return session.resource("dynamodb", config=cfg), session.client(
        "dynamodb", config=cfg
    )


def _describe_item_count(ddb_client, table_name: str) -> int:
    desc = ddb_client.describe_table(TableName=table_name)
    return int(desc["Table"].get("ItemCount", 0))


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=(
            "Backfill/remove/verify attributes for bucketed GSIs, including "
            "connection_name."
        )
    )
    p.add_argument("--table-name", required=True, help="DynamoDB table name")
    p.add_argument("--region", default=None, help="AWS region")
    p.add_argument("--profile", default=None, help="AWS profile")
    p.add_argument("--segments", type=int, default=8,
                   help="Parallel scan segments")
    p.add_argument("--page-limit", type=int, default=None,
                   help="Optional per-page Limit for scan")
    p.add_argument("--op", choices=["backfill", "remove", "verify"],
                   default="backfill",
                   help="Operation: backfill new attrs, remove, or verify")
    p.add_argument("--dry-run", action="store_true",
                   help="Log actions but do not write")
    p.add_argument("-v", "--verbose", action="count", default=0,
                   help="Increase verbosity (use -vv for very verbose)")
    p.add_argument("--abort-after-errors", type=int, default=1000,
                   help="Abort after N errors across all threads (default 1000)")
    p.add_argument("--log-update-expr", action="store_true",
                   help="Log UpdateExpression for failed items (redacted)")
    return p.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    args = parse_args(argv)
    console = Console(highlight=False)

    # Explicit banner when dry-run is enabled
    if args.dry_run:
        console.print(
            "[yellow bold]DRY-RUN ENABLED[/]: No writes will be performed "
            "(even for backfill/remove)."
        )

    try:
        ddb_res, ddb_cli = _make_boto3(args.region, args.profile)
    except (BotoCoreError, ClientError) as exc:
        console.print(f"[red]Failed to create DynamoDB session:[/] {exc}")
        return 2

    table = ddb_res.Table(args.table_name)
    item_count = _describe_item_count(ddb_cli, args.table_name)
    total = item_count or None
    per_seg_total = (
        math.ceil(item_count / max(1, args.segments)) if item_count else None
    )

    label, color = _op_style(args.op)
    columns = [
        SpinnerColumn(),
        TextColumn(f"[bold {color}]{label}[/]"),
        BarColumn(),
        MofNCompleteColumn(),
        TextColumn("{task.description}"),
        TimeElapsedColumn(),
        TimeRemainingColumn(),
    ]

    stop_event = threading.Event()
    shared_err_counter = {"count": 0, "lock": threading.Lock(), "printed": 0}

    with Progress(*columns, console=console) as progress:
        overall_task = progress.add_task(f"{label}: overall", total=total)
        seg_tasks = [
            progress.add_task(
                f"segment {i+1}/{args.segments}", total=per_seg_total
            )
            for i in range(max(1, args.segments))
        ]

        start = time.perf_counter()
        totals = Metrics()
        with ThreadPoolExecutor(max_workers=max(1, args.segments)) as pool:
            futs = [
                pool.submit(
                    scan_segment,
                    table,
                    i,
                    max(1, args.segments),
                    args,
                    progress,
                    overall_task,
                    seg_tasks[i],
                    per_seg_total,
                    console,
                    stop_event,
                    shared_err_counter,
                )
                for i in range(max(1, args.segments))
            ]
            for fut in as_completed(futs):
                segm = fut.result()
                totals.merge(segm)

        # Force-complete overall bar
        if total is not None:
            progress.update(overall_task, completed=total)
        else:
            progress.stop_task(overall_task)

        duration = time.perf_counter() - start

    op_label = {"backfill": "Backfill", "verify": "Verify", "remove": "Remove"}[
        args.op
    ]
    title = f"{op_label} Summary" + (" [DRY-RUN]" if args.dry_run else "")
    t = Table(title=title, expand=True)
    t.add_column("Metric")
    t.add_column("Value", justify="right")
    t.add_row("Operation", args.op)
    t.add_row("Dry run", "True" if args.dry_run else "False")
    t.add_row("Items seen", f"{totals.seen:,}")
    if args.op == "verify":
        t.add_row("Items needing fix", f"{totals.would_fix:,}")
    else:
        t.add_row("Items updated", f"{totals.updated:,}")
    t.add_row("Errors", f"{totals.errors:,}")
    t.add_row("Scan pages", f"{totals.scan_pages:,}")
    t.add_row("Scan RCUs", f"{totals.scan_rcus}")
    t.add_row("Update CUs", f"{totals.update_cus}")
    t.add_row("Duration (s)", f"{duration:,.2f}")

    console.print()
    console.print(t)

    # Error breakdown table if any
    if totals.errors:
        _summarize_errors(console, totals.error_by_code)

    # If aborted early, call that out
    if stop_event.is_set() and shared_err_counter["count"] >= args.abort_after_errors:
        console.print(
            f"[red]Aborted after reaching --abort-after-errors="
            f"{args.abort_after_errors}."
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())

