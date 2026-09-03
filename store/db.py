from __future__ import annotations

import os
import sqlite3
from datetime import datetime
from pathlib import Path

from portals.base import Notice

ROOT = Path(__file__).resolve().parent.parent


def data_dir() -> Path:
    raw = (os.environ.get("DATA_DIR") or "").strip()
    path = Path(raw) if raw else ROOT / "data"
    path.mkdir(parents=True, exist_ok=True)
    return path


def default_db_path() -> Path:
    return data_dir() / "notices.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS notices (
    portal TEXT NOT NULL,
    pid TEXT NOT NULL,
    title TEXT,
    published_on TEXT,
    deadline TEXT,
    notice_type TEXT,
    contracting_rule TEXT,
    organisation TEXT,
    city TEXT,
    nuts TEXT,
    source_platform TEXT,
    cpv TEXT,
    excerpt TEXT,
    project_url TEXT,
    category TEXT,
    match_reason TEXT,
    is_match INTEGER NOT NULL DEFAULT 0,
    run_date TEXT,
    fetched_at TEXT,
    area_m2 REAL,
    capacity_kwp REAL,
    completion_on TEXT,
    value_eur REAL,
    bucket TEXT NOT NULL DEFAULT 'inbox',
    start_on TEXT,
    is_new_build INTEGER,
    has_transformer INTEGER,
    PRIMARY KEY (portal, pid)
);

CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_date TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    listed INTEGER DEFAULT 0,
    matched INTEGER DEFAULT 0,
    errors INTEGER DEFAULT 0,
    note TEXT
);

CREATE INDEX IF NOT EXISTS idx_notices_published ON notices(published_on);
CREATE INDEX IF NOT EXISTS idx_notices_match ON notices(is_match, published_on);
CREATE INDEX IF NOT EXISTS idx_notices_deadline ON notices(deadline);
CREATE INDEX IF NOT EXISTS idx_notices_city ON notices(city);
"""


class Store:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or default_db_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self._migrate()

    def _migrate(self) -> None:
        cols = {row[1] for row in self.conn.execute("PRAGMA table_info(notices)")}
        if "nuts" not in cols:
            self.conn.execute("ALTER TABLE notices ADD COLUMN nuts TEXT")
        if "source_platform" not in cols:
            self.conn.execute("ALTER TABLE notices ADD COLUMN source_platform TEXT")
        if "area_m2" not in cols:
            self.conn.execute("ALTER TABLE notices ADD COLUMN area_m2 REAL")
        if "capacity_kwp" not in cols:
            self.conn.execute("ALTER TABLE notices ADD COLUMN capacity_kwp REAL")
        if "completion_on" not in cols:
            self.conn.execute("ALTER TABLE notices ADD COLUMN completion_on TEXT")
        if "value_eur" not in cols:
            self.conn.execute("ALTER TABLE notices ADD COLUMN value_eur REAL")
        if "bucket" not in cols:
            self.conn.execute("ALTER TABLE notices ADD COLUMN bucket TEXT NOT NULL DEFAULT 'inbox'")
        if "start_on" not in cols:
            self.conn.execute("ALTER TABLE notices ADD COLUMN start_on TEXT")
        if "is_new_build" not in cols:
            self.conn.execute("ALTER TABLE notices ADD COLUMN is_new_build INTEGER")
        if "has_transformer" not in cols:
            self.conn.execute("ALTER TABLE notices ADD COLUMN has_transformer INTEGER")
        self.conn.commit()

    def upsert_notice(self, notice: Notice, run_date: str) -> None:
        self.conn.execute(
            """
            INSERT INTO notices (
                portal, pid, title, published_on, deadline, notice_type,
                contracting_rule, organisation, city, nuts, source_platform, cpv, excerpt, project_url,
                category, match_reason, is_match, run_date, fetched_at,
                area_m2, capacity_kwp, completion_on, value_eur,
                start_on, is_new_build, has_transformer
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(portal, pid) DO UPDATE SET
                title=excluded.title,
                published_on=excluded.published_on,
                deadline=excluded.deadline,
                notice_type=excluded.notice_type,
                contracting_rule=excluded.contracting_rule,
                organisation=excluded.organisation,
                city=excluded.city,
                nuts=excluded.nuts,
                source_platform=excluded.source_platform,
                cpv=excluded.cpv,
                excerpt=excluded.excerpt,
                project_url=excluded.project_url,
                category=excluded.category,
                match_reason=excluded.match_reason,
                is_match=excluded.is_match,
                run_date=excluded.run_date,
                fetched_at=excluded.fetched_at,
                area_m2=excluded.area_m2,
                capacity_kwp=excluded.capacity_kwp,
                completion_on=excluded.completion_on,
                value_eur=excluded.value_eur,
                start_on=COALESCE(excluded.start_on, notices.start_on),
                is_new_build=COALESCE(excluded.is_new_build, notices.is_new_build),
                has_transformer=COALESCE(excluded.has_transformer, notices.has_transformer)
            """,
            (
                notice.portal,
                notice.pid,
                notice.title,
                notice.published_on,
                notice.deadline,
                notice.notice_type,
                notice.contracting_rule,
                notice.organisation,
                notice.city,
                notice.nuts,
                notice.source_platform,
                notice.cpv,
                notice.excerpt,
                notice.project_url,
                notice.category,
                notice.match_reason,
                1 if notice.is_match else 0,
                run_date,
                datetime.now().isoformat(timespec="seconds"),
                notice.area_m2,
                notice.capacity_kwp,
                notice.completion_on,
                notice.value_eur,
                notice.start_on or None,
                (1 if notice.is_new_build else 0) if notice.is_new_build is not None else None,
                (1 if notice.has_transformer else 0) if notice.has_transformer is not None else None,
            ),
        )
        self.conn.commit()

    def start_run(self, run_date: str) -> int:
        cur = self.conn.execute(
            "INSERT INTO runs (run_date, started_at) VALUES (?, ?)",
            (run_date, datetime.now().isoformat(timespec="seconds")),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def finish_run(self, run_id: int, listed: int, matched: int, errors: int, note: str = "") -> None:
        self.conn.execute(
            """
            UPDATE runs SET finished_at=?, listed=?, matched=?, errors=?, note=?
            WHERE id=?
            """,
            (datetime.now().isoformat(timespec="seconds"), listed, matched, errors, note, run_id),
        )
        self.conn.commit()

    def matches(self, published_on: str | None = None, bucket: str = "inbox") -> list[sqlite3.Row]:
        where = ["is_match=1", "COALESCE(bucket, 'inbox')=?"]
        params: list[str] = [bucket]
        if published_on:
            where.append("published_on=?")
            params.append(published_on)
        order = "category, title" if published_on else "published_on DESC, category, title"
        sql = f"SELECT * FROM notices WHERE {' AND '.join(where)} ORDER BY {order}"
        return list(self.conn.execute(sql, params).fetchall())

    def last_run(self) -> sqlite3.Row | None:
        cur = self.conn.execute("SELECT * FROM runs ORDER BY id DESC LIMIT 1")
        return cur.fetchone()

    def delete_notice(self, portal: str, pid: str) -> bool:
        cur = self.conn.execute(
            "DELETE FROM notices WHERE portal=? AND pid=?",
            (portal, pid),
        )
        self.conn.commit()
        return cur.rowcount > 0

    def mark_relevant(self, portal: str, pid: str) -> bool:
        cur = self.conn.execute(
            """
            UPDATE notices SET bucket='relevant'
            WHERE portal=? AND pid=? AND COALESCE(bucket, 'inbox')='inbox'
            """,
            (portal, pid),
        )
        self.conn.commit()
        return cur.rowcount > 0

    def mark_inbox(self, portal: str, pid: str) -> bool:
        cur = self.conn.execute(
            """
            UPDATE notices SET bucket='inbox'
            WHERE portal=? AND pid=? AND COALESCE(bucket, 'inbox')='relevant'
            """,
            (portal, pid),
        )
        self.conn.commit()
        return cur.rowcount > 0

    def relevant_unique(self) -> list[sqlite3.Row]:
        cur = self.conn.execute(
            """
            SELECT * FROM notices
            WHERE COALESCE(bucket, 'inbox')='relevant'
            ORDER BY published_on DESC, category, title
            """
        )
        return dedupe_notice_rows(list(cur.fetchall()))

    def close(self) -> None:
        self.conn.close()

    def matches_unique(self, published_on: str | None = None) -> list[sqlite3.Row]:
        """Treffer ohne doppelte noticeIdentifier / TED-ID (Anzeige)."""
        return dedupe_notice_rows(self.matches(published_on))


def dedupe_notice_rows(rows: list[sqlite3.Row]) -> list[sqlite3.Row]:
    seen: set[str] = set()
    unique: list[sqlite3.Row] = []
    for row in rows:
        keys = [f"{row['portal']}:{row['pid']}", str(row["pid"] or "")]
        rule = str(row["contracting_rule"] or "")
        if rule.startswith("TED "):
            keys.append(rule)
        if any(key and key in seen for key in keys):
            continue
        for key in keys:
            if key:
                seen.add(key)
        unique.append(row)
    return unique
