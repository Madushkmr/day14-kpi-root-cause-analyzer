"""Unit tests for the contribution-tree decomposition algorithm and the
significance test helper. Uses a small synthetic fact set (not the full
sample_data CSV) so the expected numbers are easy to verify by hand.
"""
from src import decomposition, significance


def make_facts():
    """3 regions x 2 channels, 6 days baseline + 6 days current.
    'East' region takes a clean, consistent drop in the current period;
    everything else stays flat -> East should be identified as the driver."""
    facts = []
    days = [f"2026-01-{i:02d}" for i in range(1, 7)]
    days_cur = [f"2026-02-{i:02d}" for i in range(1, 7)]

    for d in days:
        for region, base in [("East", 100), ("West", 100), ("North", 100)]:
            for channel in ["Online", "Retail"]:
                facts.append(
                    {"date": d, "period": "baseline", "region": region, "channel": channel, "revenue": base}
                )
    for d in days_cur:
        for region, cur in [("East", 40), ("West", 100), ("North", 100)]:
            for channel in ["Online", "Retail"]:
                facts.append(
                    {"date": d, "period": "current", "region": region, "channel": channel, "revenue": cur}
                )
    return facts


def test_root_totals():
    facts = make_facts()
    tree = decomposition.decompose(facts, dimensions=["region", "channel"], metric="revenue", max_depth=2)
    # baseline: 3 regions * 2 channels * 6 days * 100 = 3600
    assert tree["baseline_total"] == 3600
    # current: East 40*2*6=480, West 100*2*6=1200, North 100*2*6=1200 -> 2880
    assert tree["current_total"] == 2880
    assert tree["change"] == -720


def test_driver_identified_as_east():
    facts = make_facts()
    tree = decomposition.decompose(
        facts, dimensions=["region", "channel"], metric="revenue", max_depth=2, min_contribution_share=0.15
    )
    assert tree["dimension_expanded"] == "region"
    assert len(tree["children"]) >= 1
    top_driver = tree["children"][0]
    assert top_driver["filters"]["region"] == "East"
    # East's change should be the full -720 (West/North are flat)
    assert top_driver["change"] == -720
    assert top_driver["share_of_parent_change"] == 1.0


def test_flat_regions_not_expanded_as_drivers():
    facts = make_facts()
    tree = decomposition.decompose(
        facts, dimensions=["region", "channel"], metric="revenue", max_depth=2, min_contribution_share=0.15
    )
    driver_regions = {c["filters"]["region"] for c in tree["children"]}
    assert "West" not in driver_regions
    assert "North" not in driver_regions
    other_values = {o["value"] for o in tree["other_segments"]}
    assert {"West", "North"} == other_values


def test_max_depth_stops_recursion():
    facts = make_facts()
    tree = decomposition.decompose(facts, dimensions=["region", "channel"], metric="revenue", max_depth=1)
    assert tree["dimension_expanded"] == "region"
    for child in tree["children"]:
        # depth limit reached: children should not themselves have been expanded further
        assert child["dimension_expanded"] is None
        assert child["children"] == []


def test_significance_flags_clear_signal():
    baseline = [100] * 6
    current = [40] * 6
    result = significance.test_segment(baseline, current, alpha=0.05, min_sample_rows=5)
    assert result["status"] == "ok"
    assert result["significant"] is True


def test_significance_insufficient_data():
    result = significance.test_segment([100, 90], [40, 45], alpha=0.05, min_sample_rows=5)
    assert result["status"] == "insufficient_data"
    assert result["significant"] is False
