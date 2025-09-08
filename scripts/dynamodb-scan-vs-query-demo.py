#!/usr/bin/env python3
"""Benchmark DynamoDB Scan vs Query (single GSI vs bucketed GSI).

This script measures wall-clock performance and read capacity consumption
(RCUs) when fetching *the same logical dataset* via three strategies:

1) Scan: Full Table
   Filter: begins_with(id, <prefix>) AND (active filter if requested)

2) GSI: Single Partition
   Index: connection_name == <prefix>, optional Filter: active true/false
   If --legacy-workers > 1 and the GSI has SK=id_hash_bin (Binary),
   the query is range-split by the first byte of id_hash_bin into W
   disjoint ranges (W = legacy-workers). Each worker issues a Query
   with Key(...).between(Binary(start), Binary(end)).

3) GSI: Bucketed Scatter-Gather
   Prefer sparse active-only GSI (PK=active_bucket) when --active true,
   otherwise PK=cn_bucket (+ optional active filter). Fan out over 256 buckets.

Features
- --no-progress: disable progress bars (CI-friendly)
- --active {true,false,all}: control active filter across all tests
- --projection: ALL (default) or list of attributes (comma/space separated)
- Perf knobs: retry mode/attempts, HTTP pool size, timeouts, retry stats
- Indeterminate bars (Single/Bucketed) are force-completed with final counts.

Assumptions
- Table PK: id (string), where prefix up to the last '|' is connection_name
- Attribute: active (bool)
- Legacy GSI:    PK=connection_name, SK=id_hash_bin (Binary, sha256, 32 bytes)
- Bucketed GSI:  PK=cn_bucket
- Active-only GSI (preferred if present): PK=active_bucket
"""

from __future__ import annotations

import argparse
import math
import queue
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

import boto3
from boto3.dynamodb.conditions import Attr, Key
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


# ----------------------------- Datatypes -------------------------------- #

@dataclass
class TestResult:
    """Aggregated metrics for a single test run."""
    code: str  # 'SCAN' | 'SINGLE' | 'BUCKETED'
    name: str  # Display name
    items: int = 0
    pages: int = 0
    rcus: Decimal = Decimal("0")
    seconds: float = 0.0
    errors: int = 0
    error_by_code: Dict[str, int] = field(default_factory=dict)
    note: str = ""
    # Retry stats (only when --show-retry-stats)
    sdk_retries: int = 0
    retry_by_code: Dict[str, int] = field(default_factory=dict)


# ----------------------------- Helpers ---------------------------------- #

# Retry reasons that usually indicate throttling/soft failures. Helpful for
# hints in the summary table.
RETRYABLE_CODES = {
    "ProvisionedThroughputExceededException",
    "ThrottlingException",
    "RequestLimitExceeded",
    "InternalServerError",
    "ServiceUnavailable",
    "LimitExceededException",
    "TransactionInProgressException",
    "RequestTimeout",
}


def _make_boto3(
    region: Optional[str],
    profile: Optional[str],
    retry_attempts: int,
    retry_mode: str,
    max_pool_connections: int,
    connect_timeout: Optional[float],
    read_timeout: Optional[float],
):
    """Create DynamoDB resource/client with connection/retry tuning."""
    if profile:
        session = boto3.Session(profile_name=profile, region_name=region)
    else:
        session = boto3.Session(region_name=region)

    cfg_kwargs = {
        "retries": {"max_attempts": retry_attempts, "mode": retry_mode},
        "max_pool_connections": max_pool_connections,
    }
    if connect_timeout is not None:
        cfg_kwargs["connect_timeout"] = float(connect_timeout)
    if read_timeout is not None:
        cfg_kwargs["read_timeout"] = float(read_timeout)

    cfg = Config(**cfg_kwargs)
    res = session.resource("dynamodb", config=cfg)
    cli = session.client("dynamodb", config=cfg)
    return res, cli


def _describe_table(client, table_name: str) -> dict:
    """Wrapper for DescribeTable that returns the 'Table' dict."""
    return client.describe_table(TableName=table_name)["Table"]


def _has_index(table_desc: dict, name: str) -> bool:
    """Return True if the given GSI name exists on the table."""
    for g in table_desc.get("GlobalSecondaryIndexes", []) or []:
        if g.get("IndexName") == name:
            return True
    return False


def _progress_columns(label: str, color: str) -> List:
    """Standard Rich progress columns used across all tests."""
    return [
        SpinnerColumn(),
        TextColumn(f"[bold {color}]{label}[/]"),
        BarColumn(),
        MofNCompleteColumn(),
        TextColumn("{task.description}"),
        TimeElapsedColumn(),
        TimeRemainingColumn(),
    ]


def _color_for(code: str) -> str:
    """Map test code to a stable color for the progress bars."""
    return {"SCAN": "blue", "SINGLE": "yellow", "BUCKETED": "green"}.get(
        code, "blue"
    )


def _add_error(tr: TestResult, code: str) -> None:
    """Increment error counters on the TestResult."""
    tr.errors += 1
    tr.error_by_code[code] = tr.error_by_code.get(code, 0) + 1


def _format_decimal(d: Decimal) -> str:
    """Format Decimal without scientific notation for nicer tables."""
    return f"{d.normalize()}" if d == d.to_integral() else f"{d}"


def _worker_desc(wi: int, workers: int, extra: Optional[str] = None) -> str:
    """Friendly worker label: 'worker i/N — <extra>'."""
    base = f"worker {wi+1}/{workers}"
    return f"{base} — {extra}" if extra else base


# -- Progress shim for --no-progress ------------------------------------- #

class DummyProgress:
    """No-op replacement for Rich Progress (for CI)."""

    def __init__(self):
        self._next = 1

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def add_task(self, description: str, total: Optional[int] = None) -> int:
        tid = self._next
        self._next += 1
        return tid

    def update(self, task_id: int, **kwargs):
        pass

    def stop_task(self, task_id: int):
        pass


def make_progress(columns: List, console: Console, no_progress: bool):
    """Return a Rich Progress or a DummyProgress depending on flag."""
    return DummyProgress() if no_progress else Progress(*columns, console=console)


# -- Projection helpers --------------------------------------------------- #

def parse_projection_arg(
    val: Optional[str],
) -> Tuple[str, Optional[Dict[str, str]], Optional[str]]:
    """
    Parse --projection argument.

    Returns:
        (label, ExpressionAttributeNames, ProjectionExpression)
        If 'ALL', returns (label='ALL', None, None).
    """
    if not val or val.strip().upper() == "ALL":
        return "ALL", None, None
    # Split on commas/whitespace and filter empties.
    names = [x for x in re.split(r"[,\s]+", val.strip()) if x]
    if not names:
        return "ALL", None, None
    # Build safe aliases (#p0, #p1, ...) to avoid reserved words.
    ean = {f"#p{i}": n for i, n in enumerate(names)}
    proj_expr = ",".join(ean.keys())
    label = ",".join(names)
    return label, ean, proj_expr


def apply_projection(
    params: Dict,
    ean: Optional[Dict[str, str]],
    proj_expr: Optional[str],
) -> None:
    """
    Merge ProjectionExpression and ExpressionAttributeNames into request params.

    Notes:
        - Projection controls returned attributes, not RCUs consumed.
        - We merge with any user-provided ExpressionAttributeNames to avoid
          clobbering filter/condition aliases.
    """
    if not proj_expr or not ean:
        return
    merged = dict(params.get("ExpressionAttributeNames") or {})
    merged.update(ean)
    params["ExpressionAttributeNames"] = merged
    params["ProjectionExpression"] = proj_expr


# -- Active filter helpers ------------------------------------------------ #

def parse_active_mode(val: str) -> str:
    """Normalize --active input to 'true'|'false'|'all'."""
    v = (val or "true").lower()
    return v if v in ("true", "false", "all") else "true"


def build_active_filter_expr(active_mode: str):
    """Return a ConditionExpression for 'active' or None for 'all'."""
    if active_mode == "true":
        return Attr("active").eq(True)
    if active_mode == "false":
        return Attr("active").eq(False)
    return None  # 'all' → no active filter


# ---- SDK retry counters (enabled by --show-retry-stats) ---------------- #

def _register_retry_handlers(client, counter) -> List[Tuple[str, object]]:
    """
    Attach botocore 'needs-retry' event handlers to count SDK retries.

    The handler is defensive and must never raise. We register both
    'needs-retry.dynamodb.*' and 'needs-retry.dynamodb' to cover botocore
    version differences.
    """
    handlers: List[Tuple[str, object]] = []

    def handler(event_name, **kwargs):
        # Metrics-only: swallow any unexpected shapes from botocore.
        try:
            code = None
            ex = kwargs.get("caught_exception") or kwargs.get("exception")
            resp = kwargs.get("response")
            if ex is not None:
                try:
                    code = getattr(ex, "response", {}).get(
                        "Error", {}
                    ).get("Code")
                except Exception:
                    code = None
                if not code:
                    code = ex.__class__.__name__
            elif resp:
                code = (resp.get("Error") or {}).get("Code")
            counter["total"] += 1
            if code:
                counter["by_code"][code] = counter["by_code"].get(code, 0) + 1
        except Exception:
            pass

    for ev in ("needs-retry.dynamodb.*", "needs-retry.dynamodb"):
        try:
            client.meta.events.register(ev, handler)
            handlers.append((ev, handler))
        except Exception:
            # Registration is best-effort; ignore failures.
            pass
    return handlers


def _unregister_retry_handlers(client, handlers: List[Tuple[str, object]]) -> None:
    """Detach previously registered retry event handlers."""
    for ev, h in handlers:
        try:
            client.meta.events.unregister(ev, h)
        except Exception:
            pass


# ----------------------------- Single GSI range-split helpers ----------- #

def _byte_ranges_for_workers(workers: int) -> List[Optional[Tuple[int, int]]]:
    """
    Create first-byte ranges for W workers over 0x00..0xFF.

    If W > 256, only the first 256 workers get ranges; the rest are None.
    Ranges are disjoint and contiguous.
    """
    w_eff = min(max(1, workers), 256)
    ranges: List[Optional[Tuple[int, int]]] = []
    for i in range(workers):
        if i >= w_eff:
            ranges.append(None)
            continue
        start_b = (256 * i) // w_eff
        end_b = (256 * (i + 1)) // w_eff - 1
        ranges.append((start_b, end_b))
    return ranges


def _range_label(r: Optional[Tuple[int, int]]) -> str:
    """Human-friendly hex label for a first-byte range."""
    if not r:
        return "range --"
    a, b = r
    return f"range {a:02X}..{b:02X}"


def _binary_bounds_for_first_byte_range(
    r: Tuple[int, int]
) -> Tuple[Binary, Binary]:
    """
    Build inclusive Binary start/end values for a 32-byte SK from a
    first-byte range (sb..eb).
    """
    sb, eb = r
    start = bytes([sb]) + b"\x00" * 31
    end = bytes([eb]) + b"\xFF" * 31
    return Binary(start), Binary(end)


# ----------------------------- Tests ------------------------------------ #

def run_scan_test(
    table_res,
    table_cli,
    table_name: str,
    prefix: str,
    segments: int,
    page_limit: Optional[int],
    console: Console,
    show_retry_stats: bool,
    client_for_hooks,
    resource_client_for_hooks,
    no_progress: bool,
    active_mode: str,
    proj_ean: Optional[Dict[str, str]],
    proj_expr: Optional[str],
    proj_label: str,
) -> TestResult:
    """
    Run a parallel Scan across N segments with a server-side FilterExpression.

    Notes:
        - Filters do not reduce RCUs (applied after items are read).
        - We attempt to keep shard bars realistic by using ItemCount / segments.
    """
    # Hook retry counters (if requested)
    retry_counter = {"total": 0, "by_code": {}}
    h1: List[Tuple[str, object]] = []
    h2: List[Tuple[str, object]] = []
    if show_retry_stats:
        h1 = _register_retry_handlers(client_for_hooks, retry_counter)
        h2 = _register_retry_handlers(resource_client_for_hooks, retry_counter)

    try:
        desc = _describe_table(table_cli, table_name)
        item_count = int(desc.get("ItemCount", 0)) if desc else 0
        per_seg_total = (
            math.ceil(item_count / max(1, segments)) if item_count else None
        )

        tr = TestResult(code="SCAN", name="Scan: Full Table")
        color = _color_for(tr.code)
        label = tr.name

        with make_progress(_progress_columns(label, color), console, no_progress) as prog:
            overall = prog.add_task(f"{label}: overall", total=item_count or None)
            shard_tasks = [
                prog.add_task(f"segment {i+1}/{segments}", total=per_seg_total)
                for i in range(max(1, segments))
            ]

            # Build filter: begins_with(id, prefix) [+ optional active==...]
            id_prefix_expr = Attr("id").begins_with(prefix)
            active_expr = build_active_filter_expr(active_mode)
            combined_filter = (
                id_prefix_expr & active_expr if active_expr else id_prefix_expr
            )

            def worker(seg: int, task_id: int) -> Tuple[int, int, Decimal, int]:
                """Scan one segment to completion, tracking items/pages/RCUs."""
                items = 0
                pages = 0
                rcus = Decimal("0")
                errors = 0
                last_key = None
                while True:
                    params = {
                        "Segment": seg,
                        "TotalSegments": segments,
                        "ReturnConsumedCapacity": "TOTAL",
                        "FilterExpression": combined_filter,
                    }
                    if page_limit:
                        params["Limit"] = int(page_limit)
                    if last_key:
                        params["ExclusiveStartKey"] = last_key
                    apply_projection(params, proj_ean, proj_expr)
                    try:
                        resp = table_res.scan(**params)
                    except (ClientError, BotoCoreError):
                        errors += 1
                        break

                    pages += 1
                    rcus += Decimal(
                        str(
                            (resp.get("ConsumedCapacity") or {}).get(
                                "CapacityUnits", 0
                            )
                        )
                    )
                    batch = resp.get("Items", []) or []
                    items += len(batch)

                    # Advance bars by ScannedCount for a more realistic feel.
                    scanned_now = int(resp.get("ScannedCount", len(batch)))
                    prog.update(task_id, advance=max(scanned_now, 1))
                    prog.update(overall, advance=max(scanned_now, 1))

                    last_key = resp.get("LastEvaluatedKey")
                    if not last_key:
                        break

                # Force-complete shard bar to avoid partial visual leftovers.
                if per_seg_total is not None:
                    prog.update(task_id, completed=per_seg_total)
                else:
                    prog.stop_task(task_id)
                return (items, pages, rcus, errors)

            start = time.perf_counter()
            with ThreadPoolExecutor(max_workers=max(1, segments)) as pool:
                futs = [
                    pool.submit(worker, i, shard_tasks[i])
                    for i in range(max(1, segments))
                ]
                for fut in as_completed(futs):
                    items, pages, rcus, errs = fut.result()
                    tr.items += items
                    tr.pages += pages
                    tr.rcus += rcus
                    tr.errors += errs

            # Force-complete overall, regardless of DescribeTable accuracy.
            if item_count:
                prog.update(overall, completed=item_count)
            else:
                prog.stop_task(overall)

            tr.seconds = time.perf_counter() - start

        if show_retry_stats:
            tr.sdk_retries = retry_counter["total"]
            tr.retry_by_code = dict(retry_counter["by_code"])
        tr.note = (
            "Filter=begins_with(id,prefix)"
            f"{' & active=='+active_mode if active_mode!='all' else ''}; "
            f"Projection={proj_label}"
        )
        return tr
    finally:
        if show_retry_stats:
            _unregister_retry_handlers(client_for_hooks, h1)
            _unregister_retry_handlers(resource_client_for_hooks, h2)


def run_single_query_test(
    table_res,
    index_name: str,
    prefix: str,
    workers: int,
    page_limit: Optional[int],
    console: Console,
    show_retry_stats: bool,
    client_for_hooks,
    resource_client_for_hooks,
    no_progress: bool,
    active_mode: str,
    proj_ean: Optional[Dict[str, str]],
    proj_expr: Optional[str],
    proj_label: str,
) -> TestResult:
    """
    Run a Query on the legacy GSI (single partition by connection_name).

    - If workers == 1: normal Query, no sort-key bounds.
    - If workers > 1: split SK=id_hash_bin by first byte into W disjoint ranges
      and assign one range per worker via Key.between(start,end).

    This improves client-side overlap (lower wall time) but still hits one
    physical partition (no extra server-side throughput).
    """
    retry_counter = {"total": 0, "by_code": {}}
    h1: List[Tuple[str, object]] = []
    h2: List[Tuple[str, object]] = []
    if show_retry_stats:
        h1 = _register_retry_handlers(client_for_hooks, retry_counter)
        h2 = _register_retry_handlers(resource_client_for_hooks, retry_counter)

    try:
        tr = TestResult(code="SINGLE", name="GSI: Single Partition")
        color = _color_for(tr.code)
        label = tr.name

        workers = max(1, workers)
        ranges = _byte_ranges_for_workers(workers)
        active_expr = build_active_filter_expr(active_mode)

        with make_progress(_progress_columns(label, color), console, no_progress) as prog:
            overall = prog.add_task(f"{label}: overall", total=None)
            worker_tasks = [
                prog.add_task(
                    f"{_worker_desc(i, workers, _range_label(ranges[i]))}",
                    total=None,
                )
                for i in range(workers)
            ]
            worker_items = [0] * workers  # for force-complete visuals

            def one_worker(wi: int, task_id: int) -> Tuple[int, int, Decimal, int]:
                """Query one disjoint SK range to completion."""
                items = 0
                pages = 0
                rcus = Decimal("0")
                errors = 0
                last_key = None

                # Workers beyond 256 get no range; they no-op.
                wr = ranges[wi]
                if wr is None:
                    prog.update(task_id, total=0, completed=0)
                    return (0, 0, Decimal("0"), 0)

                # SK bounds for this worker's byte slice
                sk_start, sk_end = _binary_bounds_for_first_byte_range(wr)

                while True:
                    kce = (
                        Key("connection_name").eq(prefix)
                        & Key("id_hash_bin").between(sk_start, sk_end)
                    )
                    params = {
                        "IndexName": index_name,
                        "KeyConditionExpression": kce,
                        "ReturnConsumedCapacity": "TOTAL",
                    }
                    if active_expr and active_mode in ("true", "false"):
                        params["FilterExpression"] = active_expr
                    if page_limit:
                        params["Limit"] = int(page_limit)
                    if last_key:
                        params["ExclusiveStartKey"] = last_key
                    apply_projection(params, proj_ean, proj_expr)

                    try:
                        resp = table_res.query(**params)
                    except (ClientError, BotoCoreError):
                        errors += 1
                        break

                    pages += 1
                    rcus += Decimal(
                        str(
                            (resp.get("ConsumedCapacity") or {}).get(
                                "CapacityUnits", 0
                            )
                        )
                    )
                    batch = resp.get("Items", []) or []
                    items += len(batch)
                    worker_items[wi] += len(batch)

                    prog.update(task_id, advance=len(batch))
                    prog.update(overall, advance=len(batch))

                    last_key = resp.get("LastEvaluatedKey")
                    if not last_key:
                        break

                # Force-complete this worker bar for clean visuals.
                wi_items = worker_items[wi]
                prog.update(task_id, total=wi_items or 0, completed=wi_items or 0)
                return (items, pages, rcus, errors)

            start = time.perf_counter()
            with ThreadPoolExecutor(max_workers=workers) as pool:
                futs = [
                    pool.submit(one_worker, i, worker_tasks[i])
                    for i in range(workers)
                ]
                for fut in as_completed(futs):
                    items, pages, rcus, errs = fut.result()
                    tr.items += items
                    tr.pages += pages
                    tr.rcus += rcus
                    tr.errors += errs

            # Overall bar set to final totals when known.
            prog.update(overall, total=tr.items or 0, completed=tr.items or 0)
            tr.seconds = time.perf_counter() - start

        if show_retry_stats:
            tr.sdk_retries = retry_counter["total"]
            tr.retry_by_code = dict(retry_counter["by_code"])

        # Note string with split info and projection/active mode.
        w_eff = min(workers, 256)
        active_note = (
            f"; active=={active_mode}" if active_mode in ("true", "false") else ""
        )
        tr.note = (
            f"GSI={index_name} (PK=connection_name, SK=id_hash_bin) — "
            f"range-split by first byte into {w_eff} worker(s){active_note}; "
            f"Projection={proj_label}"
        )
        return tr
    finally:
        if show_retry_stats:
            _unregister_retry_handlers(client_for_hooks, h1)
            _unregister_retry_handlers(resource_client_for_hooks, h2)


def run_bucketed_query_test(
    table_res,
    table_cli,
    table_name: str,
    prefix: str,
    bucket_index: str,
    bucket_index_active: str,
    bucket_workers: int,
    page_limit: Optional[int],
    console: Console,
    show_retry_stats: bool,
    client_for_hooks,
    resource_client_for_hooks,
    no_progress: bool,
    active_mode: str,
    proj_ean: Optional[Dict[str, str]],
    proj_expr: Optional[str],
    proj_label: str,
) -> TestResult:
    """
    Run a scatter-gather query across 256 precomputed bucket keys.

    - If an active-only GSI exists and --active true: use PK=active_bucket
      (sparse index, no active filter needed).
    - Else: use PK=cn_bucket and optionally Filter active true/false.

    This fans out across many physical partitions for higher max throughput.
    """
    retry_counter = {"total": 0, "by_code": {}}
    h1: List[Tuple[str, object]] = []
    h2: List[Tuple[str, object]] = []
    if show_retry_stats:
        h1 = _register_retry_handlers(client_for_hooks, retry_counter)
        h2 = _register_retry_handlers(resource_client_for_hooks, retry_counter)

    try:
        # Select index based on active mode and availability.
        desc = _describe_table(table_cli, table_name)
        has_active_index = _has_index(desc, bucket_index_active)
        use_active = (active_mode == "true") and has_active_index

        index_name = bucket_index_active if use_active else bucket_index
        pk_attr = "active_bucket" if use_active else "cn_bucket"
        active_expr = None
        if not use_active:
            # For non-sparse index, add active filter only when requested.
            active_expr = build_active_filter_expr(active_mode)

        tr = TestResult(code="BUCKETED", name="GSI: Bucketed Scatter-Gather")
        color = _color_for(tr.code)
        label = tr.name

        # Precompute all bucket partition keys for this connection prefix.
        suffixes = [f"{i:02x}" for i in range(256)]
        bucket_keys = [f"{prefix}#{sfx}" for sfx in suffixes]

        # Work queue is static; each worker pops one PK at a time.
        q: queue.Queue[str] = queue.Queue()
        for pk in bucket_keys:
            q.put(pk)

        workers = max(1, bucket_workers)
        with make_progress(_progress_columns(label, color), console, no_progress) as prog:
            overall = prog.add_task(f"{label}: overall", total=None)
            worker_tasks = [
                prog.add_task(f"{_worker_desc(i, workers, 'bucket --')}", total=None)
                for i in range(workers)
            ]
            worker_items = [0] * workers  # for force-complete visuals

            def one_worker(wi: int, task_id: int) -> Tuple[int, int, Decimal, int]:
                """Query many buckets (different PKs) sequentially."""
                items = 0
                pages = 0
                rcus = Decimal("0")
                errors = 0

                while not q.empty():
                    try:
                        pk = q.get_nowait()
                    except queue.Empty:
                        break

                    # Show which bucket this worker is processing.
                    prog.update(
                        task_id,
                        description=_worker_desc(wi, workers, f"bucket {pk[-2:]}"),
                    )

                    last_key = None
                    try:
                        while True:
                            params = {
                                "IndexName": index_name,
                                "KeyConditionExpression": Key(pk_attr).eq(pk),
                                "ReturnConsumedCapacity": "TOTAL",
                            }
                            if active_expr is not None:
                                params["FilterExpression"] = active_expr
                            if page_limit:
                                params["Limit"] = int(page_limit)
                            if last_key:
                                params["ExclusiveStartKey"] = last_key
                            apply_projection(params, proj_ean, proj_expr)
                            try:
                                resp = table_res.query(**params)
                            except (ClientError, BotoCoreError):
                                errors += 1
                                break

                            pages += 1
                            rcus += Decimal(
                                str(
                                    (resp.get("ConsumedCapacity") or {}).get(
                                        "CapacityUnits", 0
                                    )
                                )
                            )
                            batch = resp.get("Items", []) or []
                            items += len(batch)
                            worker_items[wi] += len(batch)

                            prog.update(task_id, advance=len(batch))
                            prog.update(overall, advance=len(batch))

                            last_key = resp.get("LastEvaluatedKey")
                            if not last_key:
                                break
                    except Exception as exc:
                        # Keep going even if a single bucket fails unexpectedly.
                        errors += 1
                        if console and args_global_verbose() > 0:
                            console.print(
                                f"[red]ERROR[/] {type(exc).__name__}: {exc} "
                                f"on bucket [cyan]{pk[-2:]}[/]"
                            )
                    finally:
                        q.task_done()

                # Mark done & force-complete this worker bar.
                prog.update(task_id, description=_worker_desc(wi, workers, "done"))
                wi_items = worker_items[wi]
                prog.update(task_id, total=wi_items or 0, completed=wi_items or 0)
                return (items, pages, rcus, errors)

            start = time.perf_counter()
            with ThreadPoolExecutor(max_workers=workers) as pool:
                futs = [
                    pool.submit(one_worker, i, worker_tasks[i])
                    for i in range(workers)
                ]
                for fut in as_completed(futs):
                    items, pages, rcus, errs = fut.result()
                    tr.items += items
                    tr.pages += pages
                    tr.rcus += rcus
                    tr.errors += errs

            # Overall bar set to final totals when known.
            prog.update(overall, total=tr.items or 0, completed=tr.items or 0)
            tr.seconds = time.perf_counter() - start

        if show_retry_stats:
            tr.sdk_retries = retry_counter["total"]
            tr.retry_by_code = dict(retry_counter["by_code"])
        mode_note = "active-only GSI" if use_active else "cn_bucket GSI"
        act_note = (
            f"active=={active_mode}" if active_mode in ("true", "false")
            else "active=all"
        )
        tr.note = (
            f"GSI={index_name} (PK={pk_attr}, {mode_note}); "
            f"{act_note}; Projection={proj_label}"
        )
        return tr
    finally:
        if show_retry_stats:
            _unregister_retry_handlers(client_for_hooks, h1)
            _unregister_retry_handlers(resource_client_for_hooks, h2)


# ----------------------------- Main & Report ---------------------------- #

def _comparison_table(
    console: Console, results: List[TestResult], show_retry_stats: bool
) -> None:
    """Render a summary table and any error/retry breakdowns."""
    title = "Scan vs Query Comparison"
    tbl = Table(title=title, expand=True)
    tbl.add_column("Test")
    tbl.add_column("Items", justify="right")
    tbl.add_column("RCUs", justify="right")
    tbl.add_column("Pages", justify="right")
    tbl.add_column("Seconds", justify="right")
    tbl.add_column("Items/sec", justify="right")
    tbl.add_column("Pages/sec", justify="right")
    if show_retry_stats:
        tbl.add_column("SDK Retries", justify="right")
        tbl.add_column("Top Retry Reason")

    for r in results:
        items_per_sec = (r.items / r.seconds) if r.seconds > 0 else 0.0
        pages_per_sec = (r.pages / r.seconds) if r.seconds > 0 else 0.0
        row = [
            r.name,
            f"{r.items:,}",
            _format_decimal(r.rcus),
            f"{r.pages:,}",
            f"{r.seconds:,.2f}",
            f"{items_per_sec:,.1f}",
            f"{pages_per_sec:,.1f}",
        ]
        if show_retry_stats:
            top_reason = ""
            if r.retry_by_code:
                top_reason = max(r.retry_by_code.items(), key=lambda kv: kv[1])[0]
            row.extend([f"{r.sdk_retries:,}", top_reason])
        tbl.add_row(*row)
    console.print(tbl)

    # Per-test error details (useful when throttled or misconfigured).
    for r in results:
        if r.errors:
            subt = Table(title=f"{r.name} Error Breakdown", expand=True)
            subt.add_column("Error code")
            subt.add_column("Count", justify="right")
            for code, cnt in sorted(
                r.error_by_code.items(), key=lambda x: (-x[1], x[0])
            ):
                subt.add_row(code, f"{cnt:,}")
            console.print(subt)

    # Gentle hints when we detect SDK retries for throttle-like codes.
    if show_retry_stats:
        throttled = any(
            any(code in RETRYABLE_CODES for code in r.retry_by_code)
            for r in results
        )
        if throttled:
            console.print(
                "\n[yellow]Hints:[/]\n"
                "• Consider --retry-mode adaptive\n"
                "• Try adjusting --bucket-workers up/down from your sweet spot\n"
                "• Set --max-pool-connections ≥ workers\n"
                "• Watch CloudWatch: ReadThrottleEvents, SuccessfulRequestLatency, "
                "ConsumedReadCapacityUnits\n"
            )


def _parse_tests_arg(val: Optional[str]) -> List[str]:
    """Parse --tests into canonical codes: ['SCAN','SINGLE','BUCKETED']."""
    if not val:
        return ["SCAN", "SINGLE", "BUCKETED"]
    raw = val.replace(",", " ").split()
    mapped = []
    alias = {
        "scan": "SCAN",
        "single": "SINGLE",
        "legacy": "SINGLE",
        "gsi": "SINGLE",
        "bucketed": "BUCKETED",
        "bkt": "BUCKETED",
    }
    for t in raw:
        key = alias.get(t.lower())
        if key:
            mapped.append(key)
    out = []
    for m in mapped:
        if m not in out:
            out.append(m)
    return out or ["SCAN", "SINGLE", "BUCKETED"]


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    """Define and parse CLI arguments."""
    p = argparse.ArgumentParser(
        description="Benchmark DynamoDB Scan vs GSI Query (single vs bucketed)"
    )
    p.add_argument("--table-name", required=True, help="DynamoDB table name")
    p.add_argument("--region", default=None, help="AWS region")
    p.add_argument("--profile", default=None, help="AWS profile")
    p.add_argument(
        "--prefix",
        required=True,
        help="Connection name prefix, e.g., 'ad|Mozilla-LDAP'",
    )
    p.add_argument(
        "--tests",
        default=None,
        help=(
            "Which tests to run (default: all). "
            "Choices: scan, single|legacy|gsi, bucketed|bkt. "
            "Examples: '--tests scan bucketed' or '--tests scan,legacy'"
        ),
    )
    p.add_argument(
        "--scan-segments",
        type=int,
        default=8,
        help="Parallel scan segments (workers for Scan)",
    )
    p.add_argument(
        "--legacy-index",
        default="temp-identity-vault-connection",
        help="Legacy/single GSI name (PK=connection_name, SK=id_hash_bin)",
    )
    p.add_argument(
        "--legacy-workers",
        type=int,
        default=1,
        help="Single GSI query workers; >1 enables SK range splitting",
    )
    p.add_argument(
        "--bucket-index",
        default="temp-identity-vault-cn-bucket",
        help="Bucketed GSI name (PK=cn_bucket)",
    )
    p.add_argument(
        "--bucket-index-active",
        default="temp-identity-vault-cn-bucket-active",
        help="Active-only bucketed GSI (PK=active_bucket)",
    )
    p.add_argument(
        "--bucket-workers",
        type=int,
        default=32,
        help="Concurrent bucket workers (fan-out)",
    )
    p.add_argument(
        "--page-limit",
        type=int,
        default=None,
        help="Optional per-call Limit for scan/query (for demos)",
    )
    p.add_argument(
        "--retry-max-attempts",
        type=int,
        default=10,
        help="Botocore standard retry max_attempts",
    )
    p.add_argument(
        "--retry-mode",
        choices=["standard", "adaptive"],
        default="standard",
        help="Retry mode",
    )
    p.add_argument(
        "--max-pool-connections",
        type=int,
        default=None,
        help="Max HTTP connections (default: max(32, bucket_workers))",
    )
    p.add_argument(
        "--connect-timeout", type=float, default=None, help="Connect timeout (s)"
    )
    p.add_argument("--read-timeout", type=float, default=None, help="Read timeout (s)")
    p.add_argument(
        "--show-retry-stats",
        action="store_true",
        help="Track SDK retry counts and reasons (botocore hooks)",
    )
    p.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="Increase verbosity; prints tracebacks on test errors",
    )
    p.add_argument(
        "--abort-after-errors",
        type=int,
        default=1000,
        help="Abort after N errors across a test (default 1000)",
    )

    # CI/projection/active controls
    p.add_argument(
        "--no-progress", action="store_true", help="Disable progress bars (CI)"
    )
    p.add_argument(
        "--active",
        choices=["true", "false", "all"],
        default="true",
        help="Filter on active status: true, false, or all (no filter)",
    )
    p.add_argument(
        "--projection",
        default="ALL",
        help="Projection attributes: ALL (default) or comma/space list",
    )
    return p.parse_args(argv)


# Simple global accessor to check verbosity inside workers without
# threading arg plumbing. Set once in main().
_GLOBAL_VERBOSE = 0


def args_global_verbose() -> int:
    """Return current verbosity level (0,1,2,...) for worker log checks."""
    return _GLOBAL_VERBOSE


def main(argv: Optional[List[str]] = None) -> int:
    """Entrypoint: parse args, run selected tests, print comparison table."""
    global _GLOBAL_VERBOSE
    args = parse_args(argv)
    _GLOBAL_VERBOSE = args.verbose

    console = Console(highlight=False)

    # Default for pool size depends on bucket_workers to avoid HTTP starvation.
    max_pool = args.max_pool_connections or max(32, args.bucket_workers)
    active_mode = parse_active_mode(args.active)
    proj_label, proj_ean, proj_expr = parse_projection_arg(args.projection)

    # Build clients with tuned retry/connection settings.
    try:
        ddb_res, ddb_cli = _make_boto3(
            args.region,
            args.profile,
            args.retry_max_attempts,
            args.retry_mode,
            max_pool,
            args.connect_timeout,
            args.read_timeout,
        )
    except (BotoCoreError, ClientError) as exc:
        console.print(f"[red]Failed to create DynamoDB session:[/] {exc}")
        return 2

    table_res = ddb_res.Table(args.table_name)
    # Resource uses its own client; we hook both for retry stats when enabled.
    resource_client_for_hooks = ddb_res.meta.client
    selected = _parse_tests_arg(args.tests)

    results: List[TestResult] = []

    # --- Test: Scan: Full Table ---
    if "SCAN" in selected:
        try:
            results.append(
                run_scan_test(
                    table_res=table_res,
                    table_cli=ddb_cli,
                    table_name=args.table_name,
                    prefix=args.prefix,
                    segments=args.scan_segments,
                    page_limit=args.page_limit,
                    console=console,
                    show_retry_stats=args.show_retry_stats,
                    client_for_hooks=ddb_cli,
                    resource_client_for_hooks=resource_client_for_hooks,
                    no_progress=args.no_progress,
                    active_mode=active_mode,
                    proj_ean=proj_ean,
                    proj_expr=proj_expr,
                    proj_label=proj_label,
                )
            )
        except Exception as exc:
            if args.verbose:
                console.print("[red]Unhandled exception in SCAN test[/]")
                console.print_exception(show_locals=False)
            r = TestResult(code="SCAN", name="Scan: Full Table")
            r.errors = 1
            r.error_by_code[type(exc).__name__] = 1
            r.note = f"Scan failed: {exc}"
            results.append(r)

    # --- Test: GSI: Single Partition ---
    if "SINGLE" in selected:
        try:
            results.append(
                run_single_query_test(
                    table_res=table_res,
                    index_name=args.legacy_index,
                    prefix=args.prefix,
                    workers=args.legacy_workers,
                    page_limit=args.page_limit,
                    console=console,
                    show_retry_stats=args.show_retry_stats,
                    client_for_hooks=ddb_cli,
                    resource_client_for_hooks=resource_client_for_hooks,
                    no_progress=args.no_progress,
                    active_mode=active_mode,
                    proj_ean=proj_ean,
                    proj_expr=proj_expr,
                    proj_label=proj_label,
                )
            )
        except Exception as exc:
            if args.verbose:
                console.print("[red]Unhandled exception in SINGLE test[/]")
                console.print_exception(show_locals=False)
            r = TestResult(code="SINGLE", name="GSI: Single Partition")
            r.errors = 1
            r.error_by_code[type(exc).__name__] = 1
            r.note = f"Single query failed: {exc}"
            results.append(r)

    # --- Test: GSI: Bucketed Scatter-Gather ---
    if "BUCKETED" in selected:
        try:
            results.append(
                run_bucketed_query_test(
                    table_res=table_res,
                    table_cli=ddb_cli,
                    table_name=args.table_name,
                    prefix=args.prefix,
                    bucket_index=args.bucket_index,
                    bucket_index_active=args.bucket_index_active,
                    bucket_workers=args.bucket_workers,
                    page_limit=args.page_limit,
                    console=console,
                    show_retry_stats=args.show_retry_stats,
                    client_for_hooks=ddb_cli,
                    resource_client_for_hooks=resource_client_for_hooks,
                    no_progress=args.no_progress,
                    active_mode=active_mode,
                    proj_ean=proj_ean,
                    proj_expr=proj_expr,
                    proj_label=proj_label,
                )
            )
        except Exception as exc:
            if args.verbose:
                console.print("[red]Unhandled exception in BUCKETED test[/]")
                console.print_exception(show_locals=False)
            r = TestResult(code="BUCKETED", name="GSI: Bucketed Scatter-Gather")
            r.errors = 1
            r.error_by_code[type(exc).__name__] = 1
            r.note = f"Bucketed query failed: {exc}"
            results.append(r)

    # --- Comparison ---
    if results:
        _comparison_table(console, results, args.show_retry_stats)
    else:
        console.print("[red]No tests were selected to run.[/]")

    return 0


if __name__ == "__main__":
    sys.exit(main())

