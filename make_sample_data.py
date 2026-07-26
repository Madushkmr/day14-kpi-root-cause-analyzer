"""
Generates sample_data/sales_daily.csv: synthetic multi-dimensional daily
sales data across two 30-day periods (baseline vs. current), with a
deliberately injected root cause so the decomposition engine has a real
signal to find (North America / Retail / Electronics / Enterprise drops
hard in the current period; everything else only moves with noise).

Run once to regenerate the committed sample data:
    python make_sample_data.py
"""
import csv
import random
from datetime import date, timedelta

random.seed(42)

REGIONS = ["North America", "Europe", "APAC"]
CHANNELS = ["Retail", "Online", "Wholesale"]
CATEGORIES = ["Electronics", "Apparel", "Home Goods", "Grocery"]
SEGMENTS = ["Consumer", "SMB", "Enterprise"]

BASELINE_START = date(2026, 5, 1)
CURRENT_START = date(2026, 6, 1)
PERIOD_DAYS = 30

# The injected root cause: this combination takes a sustained revenue hit
# in the current period. Contribution-tree decomposition should surface it.
ROOT_CAUSE = {
    "region": "North America",
    "channel": "Retail",
    "product_category": "Electronics",
    "customer_segment": "Enterprise",
}
ROOT_CAUSE_DROP = 0.55  # current-period revenue multiplier for the affected slice


def base_revenue(region, channel, category, segment):
    """Deterministic-ish per-combo daily revenue baseline so combos differ."""
    key = f"{region}|{channel}|{category}|{segment}"
    h = sum(ord(c) for c in key)
    return 400 + (h % 900)  # roughly $400-$1300/day baseline


def gen_period(start_date, is_current):
    rows = []
    for d in range(PERIOD_DAYS):
        day = start_date + timedelta(days=d)
        for region in REGIONS:
            for channel in CHANNELS:
                for category in CATEGORIES:
                    for segment in SEGMENTS:
                        mean = base_revenue(region, channel, category, segment)
                        is_root_cause_slice = (
                            region == ROOT_CAUSE["region"]
                            and channel == ROOT_CAUSE["channel"]
                            and category == ROOT_CAUSE["product_category"]
                            and segment == ROOT_CAUSE["customer_segment"]
                        )
                        if is_current and is_root_cause_slice:
                            mean *= ROOT_CAUSE_DROP
                        # mild general noise everywhere (+/- ~8%)
                        noise = random.gauss(1.0, 0.08)
                        revenue = round(max(mean * noise, 0), 2)
                        units = max(int(revenue / random.uniform(15, 45)), 0)
                        rows.append(
                            [
                                day.isoformat(),
                                region,
                                channel,
                                category,
                                segment,
                                revenue,
                                units,
                            ]
                        )
    return rows


def main():
    rows = gen_period(BASELINE_START, is_current=False) + gen_period(
        CURRENT_START, is_current=True
    )
    out_path = "sample_data/sales_daily.csv"
    with open(out_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "date",
                "region",
                "channel",
                "product_category",
                "customer_segment",
                "revenue",
                "units",
            ]
        )
        writer.writerows(rows)
    print(f"Wrote {len(rows)} rows to {out_path}")


if __name__ == "__main__":
    main()
