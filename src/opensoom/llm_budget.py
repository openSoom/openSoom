"""Persistent, shared bounds for product-model tests (not Codex Goal tokens)."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator


class BudgetExhausted(RuntimeError):
    """No further provider request is allowed within this test batch."""


class BudgetConfigurationError(RuntimeError):
    """A saved allowance cannot be reset or silently enlarged."""


@dataclass(frozen=True)
class BudgetLimits:
    batch_id: str = "opensoom-hackathon-2026-11-18"
    max_requests: int = 100
    max_tokens: int = 250_000

    def __post_init__(self) -> None:
        if not self.batch_id or self.max_requests <= 0 or self.max_tokens <= 0:
            raise ValueError("A named batch and positive finite limits are required")


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


class SharedBudget:
    """SQLite reservations include all workers, retries and resumed processes.

    A request is charged at reservation time. Unknown provider usage keeps the
    full conservative token reservation charged. Reopening the file preserves
    counters; changing limits requires an explicit new authorized batch, not a
    constructor argument that happens to be larger.
    """

    def __init__(self, path: str | Path, limits: BudgetLimits | None = None):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS configuration (
                    singleton INTEGER PRIMARY KEY CHECK(singleton = 1),
                    limits_json TEXT NOT NULL, created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS reservations (
                    id TEXT PRIMARY KEY, run_id TEXT NOT NULL,
                    reserved_tokens INTEGER NOT NULL CHECK(reserved_tokens >= 0),
                    charged_tokens INTEGER NOT NULL CHECK(charged_tokens >= 0),
                    state TEXT NOT NULL, created_at TEXT NOT NULL,
                    settled_at TEXT
                );
                """
            )
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT limits_json FROM configuration WHERE singleton=1").fetchone()
            if row is None:
                if limits is None:
                    raise BudgetConfigurationError("Configure a finite shared budget before live calls")
                conn.execute(
                    "INSERT INTO configuration VALUES (1, ?, ?)",
                    (json.dumps(asdict(limits), sort_keys=True), now()),
                )
                self.limits = limits
            else:
                saved = BudgetLimits(**json.loads(row[0]))
                if limits is not None and limits != saved:
                    raise BudgetConfigurationError("Saved test allowance cannot be reset or changed automatically")
                self.limits = saved
            conn.commit()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path, timeout=15, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout=15000")
        try:
            yield conn
        except BaseException:
            if conn.in_transaction:
                conn.rollback()
            raise
        finally:
            conn.close()

    def reserve(self, reservation_id: str, run_id: str, tokens: int) -> dict:
        if not reservation_id or not run_id or tokens <= 0:
            raise ValueError("Reservation ID, run ID and positive token bound are required")
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            if conn.execute("SELECT 1 FROM reservations WHERE state='provider_usage_exceeded_reservation'").fetchone():
                raise BudgetConfigurationError("A provider usage discrepancy requires investigation before more live calls")
            if conn.execute("SELECT 1 FROM reservations WHERE id=?", (reservation_id,)).fetchone():
                raise BudgetConfigurationError("A provider request reservation cannot be reused")
            count, charged = conn.execute(
                "SELECT COUNT(*), COALESCE(SUM(charged_tokens),0) FROM reservations"
            ).fetchone()
            if count >= self.limits.max_requests or charged + tokens > self.limits.max_tokens:
                raise BudgetExhausted("Shared live-test allowance exhausted; continue non-model work")
            conn.execute(
                "INSERT INTO reservations VALUES (?, ?, ?, ?, 'reserved', ?, NULL)",
                (reservation_id, run_id, tokens, tokens, now()),
            )
            conn.commit()
        return self.snapshot()

    def settle(self, reservation_id: str, actual_tokens: int | None) -> dict:
        if actual_tokens is not None and actual_tokens < 0:
            raise ValueError("Usage cannot be negative")
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT * FROM reservations WHERE id=?", (reservation_id,)).fetchone()
            if row is None:
                raise BudgetConfigurationError("Cannot settle an unreserved provider request")
            if row["state"] != "reserved":
                raise BudgetConfigurationError("A reservation can be settled only once")
            charged = row["reserved_tokens"] if actual_tokens is None else actual_tokens
            state = "unknown_usage" if actual_tokens is None else "settled"
            if actual_tokens is not None and actual_tokens > row["reserved_tokens"]:
                state = "provider_usage_exceeded_reservation"
            conn.execute(
                "UPDATE reservations SET charged_tokens=?, state=?, settled_at=? WHERE id=?",
                (charged, state, now(), reservation_id),
            )
            conn.commit()
        result = self.snapshot()
        if state == "provider_usage_exceeded_reservation":
            raise BudgetConfigurationError("Provider usage exceeded the conservative reservation; investigate before more live calls")
        return result

    def snapshot(self) -> dict:
        with self._connect() as conn:
            row = conn.execute(
                """SELECT COUNT(*) AS requests, COALESCE(SUM(charged_tokens),0) AS charged,
                COALESCE(SUM(CASE WHEN state='reserved' THEN charged_tokens ELSE 0 END),0) AS reserved,
                COALESCE(SUM(CASE WHEN state='reserved' THEN 1 ELSE 0 END),0) AS pending,
                COALESCE(SUM(CASE WHEN state='provider_usage_exceeded_reservation' THEN 1 ELSE 0 END),0) AS exceeded
                FROM reservations"""
            ).fetchone()
        return {
            **asdict(self.limits),
            "requests_consumed": row["requests"],
            "tokens_charged": row["charged"],
            "tokens_reserved": row["reserved"],
            "pending_requests": row["pending"],
            "requests_remaining": max(0, self.limits.max_requests - row["requests"]),
            "tokens_remaining": max(0, self.limits.max_tokens - row["charged"]),
            "requires_investigation": bool(row["exceeded"]),
        }


def conservative_token_reservation(payload: dict, max_output_tokens: int) -> int:
    """UTF-8 payload bytes plus framing/output bound; provider usage settles it."""
    return len(json.dumps(payload, ensure_ascii=False).encode("utf-8")) + 1024 + max_output_tokens
