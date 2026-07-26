"""Recursive greedy contribution-tree decomposition.

This is the core "root cause analysis" algorithm: given a metric that moved
between a baseline period and a current period, and an ordered list of
dimensions to drill into (e.g. region -> channel -> product_category ->
customer_segment), it figures out *which* segments explain the change.

Algorithm (additive contribution / "driver tree" analysis):
  1. At the current node, compute baseline_total, current_total, and change
     for the filtered subset of facts.
  2. If we've hit max_depth or run out of dimensions, stop (leaf node).
  3. Otherwise, split the subset by the next unused dimension. Each value of
     that dimension is a disjoint partition of the rows, so the children's
     changes sum exactly to the parent's change (that's what makes this an
     "additive" decomposition, as opposed to a black-box ML attribution).
  4. Rank children by |change| descending. Any child whose share of the
     parent's total change is >= min_contribution_share is treated as a
     "driver" and gets recursed into (greedy: follow the biggest movers).
     Children below the threshold are still reported (so the full picture is
     visible) but are not expanded further.
  5. At every node, run a significance test (Welch's t-test on daily
     baseline vs. current values within that filtered subset) so a big
     dollar swing that's actually just day-to-day noise gets flagged rather
     than presented as a confirmed driver.

This mirrors what BI tools call "driver analysis" / "contribution analysis"
/ metric-tree drill-down — decomposing *why* a KPI moved rather than just
detecting *that* it moved.
"""
from . import significance


def _matches(row, filters):
    return all(row[k] == v for k, v in filters.items())


def _totals(facts, filters, metric):
    baseline_total = sum(r[metric] for r in facts if r["period"] == "baseline" and _matches(r, filters))
    current_total = sum(r[metric] for r in facts if r["period"] == "current" and _matches(r, filters))
    return baseline_total, current_total


def _daily_series(facts, filters, period, metric):
    by_date = {}
    for r in facts:
        if r["period"] != period or not _matches(r, filters):
            continue
        by_date[r["date"]] = by_date.get(r["date"], 0.0) + r[metric]
    return list(by_date.values())


def _label(filters):
    if not filters:
        return "All data"
    return ", ".join(f"{k}={v}" for k, v in filters.items())


def _node_stats(facts, filters, metric, alpha, min_sample_rows, parent_change=None):
    baseline_total, current_total = _totals(facts, filters, metric)
    change = current_total - baseline_total
    pct_change = (change / baseline_total * 100) if baseline_total else None

    base_series = _daily_series(facts, filters, "baseline", metric)
    cur_series = _daily_series(facts, filters, "current", metric)
    sig = significance.test_segment(base_series, cur_series, alpha=alpha, min_sample_rows=min_sample_rows)

    node = {
        "label": _label(filters),
        "filters": dict(filters),
        "baseline_total": round(baseline_total, 2),
        "current_total": round(current_total, 2),
        "change": round(change, 2),
        "pct_change": round(pct_change, 2) if pct_change is not None else None,
        "significance": sig,
    }
    if parent_change is not None and parent_change != 0:
        node["share_of_parent_change"] = round(change / parent_change, 4)
    else:
        node["share_of_parent_change"] = None
    return node, change


def decompose(
    facts,
    dimensions,
    metric="revenue",
    max_depth=3,
    min_contribution_share=0.15,
    min_sample_rows=5,
    alpha=0.05,
    filters=None,
    depth=0,
    parent_change=None,
):
    filters = filters or {}
    remaining_dims = [d for d in dimensions if d not in filters]

    node, change = _node_stats(facts, filters, metric, alpha, min_sample_rows, parent_change)
    node["dimension_expanded"] = None
    node["children"] = []
    node["other_segments"] = []

    if depth >= max_depth or not remaining_dims:
        return node

    next_dim = remaining_dims[0]
    subset = [r for r in facts if _matches(r, filters)]
    values = sorted({r[next_dim] for r in subset})

    child_summaries = []
    for value in values:
        child_filters = dict(filters, **{next_dim: value})
        _, child_change = _node_stats(subset, child_filters, metric, alpha, min_sample_rows, change)
        child_summaries.append((value, child_change))

    child_summaries.sort(key=lambda vc: abs(vc[1]), reverse=True)
    node["dimension_expanded"] = next_dim

    for value, child_change in child_summaries:
        share = (child_change / change) if change else 0
        child_filters = dict(filters, **{next_dim: value})
        is_driver = change != 0 and abs(share) >= min_contribution_share
        if is_driver:
            child_node = decompose(
                subset,
                dimensions,
                metric=metric,
                max_depth=max_depth,
                min_contribution_share=min_contribution_share,
                min_sample_rows=min_sample_rows,
                alpha=alpha,
                filters=child_filters,
                depth=depth + 1,
                parent_change=change,
            )
            node["children"].append(child_node)
        else:
            node["other_segments"].append(
                {
                    "value": value,
                    "change": round(child_change, 2),
                    "share_of_parent_change": round(share, 4) if change else None,
                }
            )

    return node
