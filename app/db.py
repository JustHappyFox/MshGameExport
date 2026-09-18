"""Очередь задач на sqlite. Одна таблица, без внешних зависимостей."""
from __future__ import annotations

import json
import sqlite3
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id            TEXT PRIMARY KEY,
    user_id       INTEGER NOT NULL,
    username      TEXT,
    status        TEXT NOT NULL DEFAULT 'queued',
    stage         TEXT NOT NULL DEFAULT 'в очереди',
    progress      INTEGER NOT NULL DEFAULT 0,
    input_path    TEXT NOT NULL,
    input_name    TEXT,
    input_size    INTEGER NOT NULL DEFAULT 0,
    output_path   TEXT,
    output_size   INTEGER NOT NULL DEFAULT 0,
    report        TEXT,
    error         TEXT,
    created_at    REAL NOT NULL,
    started_at    REAL,
    finished_at   REAL,
    updated_at    REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS jobs_status_created ON jobs(status, created_at);
CREATE INDEX IF NOT EXISTS jobs_user_created ON jobs(user_id, created_at DESC);
"""


def _connect() -> sqlite3.Connection:
    config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(config.DB_PATH), timeout=30, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


@contextmanager
def db() -> Iterator[sqlite3.Connection]:
    conn = _connect()
    try:
        yield conn
    finally:
        conn.close()


def init() -> None:
    with db() as conn:
        conn.executescript(SCHEMA)


def _row(r: sqlite3.Row | None) -> dict[str, Any] | None:
    if r is None:
        return None
    d = dict(r)
    if d.get("report"):
        try:
            d["report"] = json.loads(d["report"])
        except json.JSONDecodeError:
            d["report"] = None
    return d


def create_job(user_id: int, username: str | None, input_path: Path,
               input_name: str, input_size: int) -> str:
    job_id = uuid.uuid4().hex
    now = time.time()
    with db() as conn:
        conn.execute(
            "INSERT INTO jobs (id, user_id, username, input_path, input_name,"
            " input_size, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?)",
            (job_id, user_id, username, str(input_path), input_name, input_size, now, now),
        )
    return job_id


def get_job(job_id: str) -> dict | None:
    with db() as conn:
        return _row(conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone())


def list_jobs(user_id: int, limit: int = 20) -> list[dict]:
    with db() as conn:
        rows = conn.execute(
            "SELECT * FROM jobs WHERE user_id=? ORDER BY created_at DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
    return [_row(r) for r in rows]


def queue_position(job_id: str) -> int:
    """Сколько задач впереди этой (0 = следующая на обработку)."""
    with db() as conn:
        row = conn.execute("SELECT created_at, status FROM jobs WHERE id=?", (job_id,)).fetchone()
        if not row or row["status"] != "queued":
            return 0
        return conn.execute(
            "SELECT COUNT(*) FROM jobs WHERE status='queued' AND created_at < ?",
            (row["created_at"],),
        ).fetchone()[0]


def claim_next() -> dict | None:
    """Атомарно забирает следующую задачу из очереди."""
    now = time.time()
    with db() as conn:
        conn.execute("BEGIN IMMEDIATE")
        try:
            row = conn.execute(
                "SELECT * FROM jobs WHERE status='queued' ORDER BY created_at LIMIT 1"
            ).fetchone()
            if row is None:
                conn.execute("COMMIT")
                return None
            conn.execute(
                "UPDATE jobs SET status='processing', stage='подготовка', started_at=?,"
                " updated_at=? WHERE id=?",
                (now, now, row["id"]),
            )
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
        return _row(conn.execute("SELECT * FROM jobs WHERE id=?", (row["id"],)).fetchone())


def set_progress(job_id: str, progress: int, stage: str) -> None:
    with db() as conn:
        conn.execute(
            "UPDATE jobs SET progress=?, stage=?, updated_at=? WHERE id=?",
            (max(0, min(100, progress)), stage, time.time(), job_id),
        )


def finish_job(job_id: str, output_path: Path, output_size: int, report: dict) -> None:
    now = time.time()
    with db() as conn:
        conn.execute(
            "UPDATE jobs SET status='done', stage='готово', progress=100, output_path=?,"
            " output_size=?, report=?, error=NULL, finished_at=?, updated_at=? WHERE id=?",
            (str(output_path), output_size, json.dumps(report, ensure_ascii=False),
             now, now, job_id),
        )


def fail_job(job_id: str, error: str) -> None:
    now = time.time()
    with db() as conn:
        conn.execute(
            "UPDATE jobs SET status='error', stage='ошибка', error=?, finished_at=?,"
            " updated_at=? WHERE id=?",
            (error[:2000], now, now, job_id),
        )


def requeue_stale(older_than: float = 3600.0) -> int:
    """Возвращает в очередь задачи, зависшие после падения воркера."""
    cutoff = time.time() - older_than
    with db() as conn:
        cur = conn.execute(
            "UPDATE jobs SET status='queued', stage='в очереди', progress=0"
            " WHERE status='processing' AND updated_at < ?",
            (cutoff,),
        )
        return cur.rowcount


def expired_jobs(hours: int) -> list[dict]:
    cutoff = time.time() - hours * 3600
    with db() as conn:
        rows = conn.execute(
            "SELECT * FROM jobs WHERE created_at < ? AND status IN ('done','error')",
            (cutoff,),
        ).fetchall()
    return [_row(r) for r in rows]


def delete_job(job_id: str) -> None:
    with db() as conn:
        conn.execute("DELETE FROM jobs WHERE id=?", (job_id,))
