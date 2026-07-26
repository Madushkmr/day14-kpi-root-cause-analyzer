"""One-shot script: loads sample_data/sales_daily.csv into SQLite.

    python seed.py
"""
from src import ingest

if __name__ == "__main__":
    count, baseline_dates, current_dates = ingest.load_csv("sample_data/sales_daily.csv")
    print(f"Loaded {count} rows into rootcause.db")
    print(f"Baseline period: {baseline_dates[0]} .. {baseline_dates[-1]} ({len(baseline_dates)} days)")
    print(f"Current period:  {current_dates[0]} .. {current_dates[-1]} ({len(current_dates)} days)")
