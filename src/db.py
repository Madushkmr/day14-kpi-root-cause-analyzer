"""SQLite schema + CRUD for the KPI root-cause analyzer.

Two tables:
  - daily_facts: the raw multi-dimensional daily rows (loaded by ingest.py)
  - analysis_runs: stored results of each root-cause decomposition run,
    so past reports can be revisited from the dashboard/API without
    re-running the analysis.
"""
import json
import sqlite3
from contextlib import contextmanager

DB_PATH = "rootcause.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS daily_facts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    period TEXT NOT NULL CHECK(period IN ('baseline', 'current')),
    region TEXT NOT NULL,
    channel TEXT NOT NULL,
    product_category TEXT NOT NULL,
    customer_segment TEXT NOT NULL,
    revenue REAL NOT NULL,
    units INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_facts_period ON daily_facts(period);
CREATE INDEX IF NOT EXISTS idx_facts_region ON daily_facts(region);

CREATE TABLE IF NOT EXISTS analysis_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    metric TEXT NOT NULL,
    baseline_total REAL NOT NULL,
    current_total REAL NOT NULL,
    pct_change REAL NOT NULL,
    tree_json TEXT NOT NULL,
    narrative TEXT NOT NULL
);
"""


# NOTE: db_path defaults are resolved to the module-level DB_PATH *inside*
# each function body (not as a `db_path=DB_PATH` default argument), so that
# tests can monkeypatch `db.DB_PATH` and have every function pick up the
# override. A `db_path=DB_PATH` default argument would freeze the value at
# import time and ignore later monkeypatching.


@contextmanager
def get_conn(db_path=None):
    conn = sqlite3.connect(db_path or DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db(db_path=None):
    with get_conn(db_path) as conn:
        conn.executescript(SCHEMA)


def clear_facts(db_path=None):
    with get_conn(db_path) as conn:
        conn.execute("DELETE FROM daily_facts")


def insert_facts(rows, db_path=None):
    """rows: iterable of dicts with keys matching daily_facts columns
    (except id)."""
    with get_conn(db_path) as conn:
        conn.executemany(
            """INSERT INTO daily_facts
               (date, period, region, channel, product_category, customer_segment, revenue, units)
               VALUES (:date, :period, :region, :channel, :product_category, :customer_segment, :revenue, :units)""",
            rows,
        )


def fetch_facts(db_path=None):
    with get_conn(db_path) as conn:
        cur = conn.execute("SELECT * FROM daily_facts")
        return [dict(r) for r in cur.fetchall()]


def save_run(metric, baseline_total, current_total, pct_change, tree, narrative, db_path=None):
    with get_conn(db_path) as conn:
        cur = conn.execute(
            """INSERT INTO analysis_runs
               (metric, baseline_total, current_total, pct_change, tree_json, narrative)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (metric, baseline_total, current_total, pct_change, json.dumps(tree), narrative),
        )
        return cur.lastrowid


def list_runs(db_path=None):
    with get_conn(db_path) as conn:
        cur = conn.execute(
            "SELECT id, created_at, metric, baseline_total, current_total, pct_change FROM analysis_runs ORDER BY id DESC"
        )
        return [dict(r) for r in cur.fetchall()]


def get_run(run_id, db_path=None):
    with get_conn(db_path) as conn:
        cur = conn.execute("SELECT * FROM analysis_runs WHERE id = ?", (run_id,))
        row = cur.fetchone()
        if row is None:
            return None
        result = dict(row)
        result["tree"] = json.loads(result.pop("tree_json"))
        return result
