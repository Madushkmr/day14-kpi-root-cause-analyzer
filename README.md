# Day 14 — KPI Root-Cause / Driver Analyzer

Day 14 of a daily AI-app series (BI focus). A Flask REST API + dashboard that answers the question every BI analyst gets asked after a metric moves: **"why?"** Given a KPI that changed between a baseline period and a current period, it recursively decomposes the change across configurable dimensions (region, channel, product category, customer segment) to find which specific segments actually drove it, statistically tests whether each segment's shift is real or noise, and writes a plain-English root-cause narrative.

## Why this matters for BI work

Dashboards are good at telling you *that* revenue dropped 5% week-over-week. They're much worse at telling you *why* — and "why" is what a VP actually asks in the meeting. Analysts do this today by hand: pivot by region, eyeball it, pivot by channel within the worst region, eyeball it again, and so on, usually without ever checking whether the "worst" segment's drop is actually statistically distinguishable from normal day-to-day variance.

This tool automates that manual drill-down process:

- **Additive contribution / driver-tree decomposition** — because each dimension's values are a disjoint partition of the data, child segment changes sum exactly to the parent's change. That makes it a transparent, auditable decomposition rather than an opaque ML attribution score.
- **Statistical significance testing at every node** (Welch's t-test on daily baseline-vs-current values) — so a big-looking dollar swing that's actually within normal noise gets flagged as such instead of being presented as a confirmed root cause.
- **Natural-language narrative generation** — walks the greedy "biggest mover" path down the tree and writes the finding as a sentence, the way an analyst would explain it in a standup.
- **Config-driven dimensions** (`config/dimensions.yaml`) — point it at a different dataset by changing the dimension list and thresholds, no code changes required.

## Complexity tier

This is a step up from Day 13's three-parallel-stats-modules design: instead of running independent tests side-by-side, Day 14 introduces a **recursive greedy search algorithm** (the contribution tree walks itself deeper based on what it finds at each level, up to a configurable depth and contribution-share threshold) combined with significance testing *at every level of the recursion* and an NLG layer that narrates the discovered path. It's a multi-component app: Flask REST API + interactive drill-down dashboard, SQLite persistence of full historical runs (not just the latest), a CSV ingestion pipeline, a pytest suite covering the algorithm and the API, and a Dockerfile.

## Architecture

```
day14-kpi-root-cause-analyzer/
├── app.py                    # Flask app: REST API + dashboard routes
├── seed.py                   # one-shot script to load sample_data into SQLite
├── make_sample_data.py       # regenerates sample_data/sales_daily.csv (fixed seed)
├── config/
│   └── dimensions.yaml       # dimension drill-down order + thresholds
├── src/
│   ├── db.py                 # SQLite schema + CRUD (daily_facts, analysis_runs)
│   ├── ingest.py             # CSV -> SQLite loader (splits dates into baseline/current)
│   ├── decomposition.py      # recursive greedy contribution-tree algorithm
│   ├── significance.py       # Welch's t-test per segment
│   └── narrative.py          # walks the tree, generates the plain-English report
├── templates/
│   ├── dashboard.html        # dark-mode dashboard shell, run history, controls
│   └── _run.html             # recursive Jinja macro rendering the drill-down tree
├── sample_data/
│   └── sales_daily.csv       # 6,480 rows: 3 regions x 3 channels x 4 categories x 3 segments x 60 days
├── tests/
│   ├── test_decomposition.py # algorithm correctness on a small hand-checkable dataset
│   └── test_api.py           # Flask test-client coverage of every endpoint
├── requirements.txt
└── Dockerfile
```

**Data flow:** CSV → `ingest.load_csv()` splits dates into baseline/current halves and loads `daily_facts` in SQLite → `decomposition.decompose()` recursively partitions the filtered rows by each configured dimension, computing totals, change, and significance at every node → `narrative.generate()` walks the resulting tree's biggest-mover path into a written explanation → the full tree + narrative are persisted to `analysis_runs` and served as JSON / rendered in the dashboard.

## The decomposition algorithm

1. At the root, compute `baseline_total`, `current_total`, and `change` for all data.
2. If max depth is reached or there are no more dimensions to drill into, stop.
3. Otherwise split the current subset by the next dimension in the config order. Every value of that dimension is a disjoint slice, so children's changes sum exactly to the parent's change.
4. Rank children by `|change|` descending. Any child whose share of the parent's change is ≥ `min_contribution_share` is treated as a driver and recursed into; everything else is still reported (as `other_segments`) but not expanded further.
5. At every node — root and every child — run a Welch's t-test comparing daily baseline values to daily current values, so a segment can be flagged `insufficient_data`, "noise? (not significant)", or "significant" independently of how large its dollar change looks.

## Sample dataset

`sample_data/sales_daily.csv` is synthetic (`make_sample_data.py`, fixed seed 42): 60 days of daily revenue across 3 regions × 3 channels × 4 product categories × 3 customer segments (6,480 rows), split into a 30-day baseline period and a 30-day current period. A root cause is deliberately injected: **North America / Retail / Electronics / Enterprise** revenue drops ~45% in the current period; every other combination only moves with random noise (~±8%/day). Running the analyzer with `max_depth: 4` in the config recovers exactly that path with p < 0.0001 at every level — this is verified in `tests/test_decomposition.py` against a smaller hand-built dataset, and manually confirmed against the full sample data during development.

## Running it

```bash
cd day14-kpi-root-cause-analyzer
pip install -r requirements.txt

python seed.py      # loads sample_data/sales_daily.csv into SQLite (rootcause.db)
python app.py        # starts the dashboard on http://localhost:5000
```

Open `http://localhost:5000`, click **Run new analysis** (optionally adjusting max depth / contribution-share threshold in the sidebar), and browse the narrative + drill-down tree. Past runs are listed in the sidebar and can be revisited without re-running the analysis.

### REST API

```bash
# Current dimension config
curl localhost:5000/api/config

# Run a new decomposition (optional overrides: max_depth, min_contribution_share, min_sample_rows, alpha)
curl -X POST localhost:5000/api/analyze \
  -H 'Content-Type: application/json' \
  -d '{"max_depth": 4}'

# List past runs
curl localhost:5000/api/runs

# Get one run's full tree + narrative
curl localhost:5000/api/runs/1
```

### Tests

```bash
pytest tests/ -v
```

### Docker

```bash
docker build -t kpi-root-cause-analyzer .
docker run -p 5000:5000 kpi-root-cause-analyzer
```

## Notes / limitations

- The default config (`config/dimensions.yaml`) sets `max_depth: 3`, so the dashboard's default run stops at `product_category` rather than drilling into `customer_segment`, where the sample data's injected root cause actually lives. Bump `max_depth` to `4` (via the sidebar control or the API) to see the full path — this is intentional, to demonstrate that the depth/threshold knobs are real config, not hardcoded.
- Significance testing uses daily aggregated totals per segment as the sample unit (consistent with only having daily-grain data), the same practical approximation Day 13 used for revenue-per-user.
- This is a demo/portfolio project with synthetic data, not a production experimentation or attribution system — real-world driver analysis would also need to handle non-additive metrics (ratios, percentages) and interaction effects between dimensions, which this additive-partition approach does not model.
