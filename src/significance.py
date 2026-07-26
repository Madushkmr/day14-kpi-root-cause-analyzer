"""Statistical significance testing for a single segment's baseline-vs-current
daily values, so the decomposition engine can distinguish a real driver from
noise before it gets top billing in the narrative.

Uses Welch's t-test (unequal variance) on the daily revenue samples for the
segment in each period. Falls back to "insufficient_data" when either period
doesn't have enough daily observations to trust a t-test.
"""
from scipy import stats


def test_segment(baseline_values, current_values, alpha=0.05, min_sample_rows=5):
    n_base, n_cur = len(baseline_values), len(current_values)
    if n_base < min_sample_rows or n_cur < min_sample_rows:
        return {
            "status": "insufficient_data",
            "p_value": None,
            "significant": False,
            "n_baseline": n_base,
            "n_current": n_cur,
        }

    t_stat, p_value = stats.ttest_ind(current_values, baseline_values, equal_var=False)
    return {
        "status": "ok",
        "t_statistic": round(float(t_stat), 4),
        "p_value": round(float(p_value), 6),
        "significant": bool(p_value < alpha),
        "n_baseline": n_base,
        "n_current": n_cur,
    }
