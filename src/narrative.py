"""Turns a decomposition tree into a plain-English root-cause narrative.

This is the natural-language generation layer: it walks the greedy driver
chain (the biggest mover at each level) and writes a sentence per level,
noting whether each step's change is statistically significant or could be
noise, then closes with a one-line summary of any other secondary drivers
found at the top level.
"""


def _fmt_money(x):
    sign = "-" if x < 0 else ""
    return f"{sign}${abs(x):,.0f}"


def _fmt_pct(x):
    if x is None:
        return "n/a"
    sign = "+" if x >= 0 else ""
    return f"{sign}{x:.1f}%"


def _direction(change):
    return "increased" if change > 0 else "decreased" if change < 0 else "was flat"


def _sig_phrase(node):
    sig = node["significance"]
    if sig["status"] == "insufficient_data":
        return "not enough daily data to confirm statistically"
    if sig["significant"]:
        return f"statistically significant (p={sig['p_value']:.4f})"
    return f"not statistically significant (p={sig['p_value']:.4f}) — could be noise"


def generate(tree, metric="revenue"):
    lines = []
    root = tree
    overall_dir = _direction(root["change"])
    lines.append(
        f"{metric.capitalize()} {overall_dir} {_fmt_pct(root['pct_change'])} "
        f"({_fmt_money(root['baseline_total'])} -> {_fmt_money(root['current_total'])}, "
        f"a change of {_fmt_money(root['change'])}) between the baseline and current periods."
    )

    node = root
    path = []
    while node.get("children"):
        top_children = node["children"]
        top = top_children[0]
        dim = node["dimension_expanded"]
        value = top["filters"][dim]
        path.append((dim, value))
        share_pct = f"{top['share_of_parent_change'] * 100:.0f}%" if top.get("share_of_parent_change") is not None else "n/a"
        lines.append(
            f"Within that, {dim.replace('_', ' ')} = '{value}' accounts for {share_pct} of the change "
            f"({_fmt_money(top['change'])}, {_fmt_pct(top['pct_change'])}), and this shift is {_sig_phrase(top)}."
        )

        if len(top_children) > 1:
            others = ", ".join(
                f"'{c['filters'][dim]}' ({_fmt_money(c['change'])})" for c in top_children[1:]
            )
            lines.append(f"Other notable movers within {dim.replace('_', ' ')} at this level: {others}.")

        node = top

    if path:
        chain = " -> ".join(f"{d}={v}" for d, v in path)
        lines.append(f"Primary root-cause path: {chain}.")
    else:
        lines.append("No single segment stood out as a dominant driver; the change is spread broadly.")

    return " ".join(lines)
