"""CSV -> SQLite loader for daily multi-dimensional sales facts.

Assigns each row to the 'baseline' or 'current' period by date: the first
half of distinct dates (chronologically) is baseline, the second half is
current. This keeps the loader generic to any two-period CSV rather than
hardcoding specific calendar dates.
"""
import csv

from . import db


def load_csv(path, db_path=db.DB_PATH):
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    if not rows:
        raise ValueError(f"No rows found in {path}")

    dates = sorted({r["date"] for r in rows})
    midpoint = len(dates) // 2
    baseline_dates = set(dates[:midpoint])

    facts = []
    for r in rows:
        period = "baseline" if r["date"] in baseline_dates else "current"
        facts.append(
            {
                "date": r["date"],
                "period": period,
                "region": r["region"],
                "channel": r["channel"],
                "product_category": r["product_category"],
                "customer_segment": r["customer_segment"],
                "revenue": float(r["revenue"]),
                "units": int(r["units"]),
            }
        )

    db.init_db(db_path)
    db.clear_facts(db_path)
    db.insert_facts(facts, db_path)
    return len(facts), sorted(baseline_dates), sorted(set(dates) - baseline_dates)
