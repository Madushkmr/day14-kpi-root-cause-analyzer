"""Day 14 — KPI Root-Cause / Driver Analyzer

Flask REST API + dashboard. See README.md for the full write-up.

Run:
    python seed.py     # load sample_data/sales_daily.csv into SQLite
    python app.py      # start the app on http://localhost:5000
"""
import os

import yaml
from flask import Flask, jsonify, render_template, request

from src import db, decomposition, narrative

app = Flask(__name__)

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config", "dimensions.yaml")


def load_config():
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)


def run_analysis(overrides=None):
    """Runs the decomposition + narrative pipeline against whatever is
    currently in daily_facts, using config/dimensions.yaml as defaults,
    with any request-supplied overrides applied on top. Persists the run
    and returns the stored record dict."""
    cfg = load_config()
    if overrides:
        cfg.update({k: v for k, v in overrides.items() if v is not None})

    facts = db.fetch_facts()
    if not facts:
        raise ValueError("No data loaded. Run `python seed.py` first (or POST /api/ingest).")

    tree = decomposition.decompose(
        facts,
        dimensions=cfg["dimensions"],
        metric=cfg["metric"],
        max_depth=cfg["max_depth"],
        min_contribution_share=cfg["min_contribution_share"],
        min_sample_rows=cfg["min_sample_rows"],
        alpha=cfg["alpha"],
    )
    text = narrative.generate(tree, metric=cfg["metric"])

    run_id = db.save_run(
        metric=cfg["metric"],
        baseline_total=tree["baseline_total"],
        current_total=tree["current_total"],
        pct_change=tree["pct_change"] or 0.0,
        tree=tree,
        narrative=text,
    )
    return db.get_run(run_id)


@app.route("/")
def dashboard():
    db.init_db()
    runs = db.list_runs()
    requested_id = request.args.get("run", type=int)
    if requested_id:
        latest = db.get_run(requested_id)
    elif runs:
        latest = db.get_run(runs[0]["id"])
    else:
        latest = None
    return render_template("dashboard.html", runs=runs, latest=latest, config=load_config())


@app.route("/api/config", methods=["GET"])
def api_config():
    return jsonify(load_config())


@app.route("/api/analyze", methods=["POST"])
def api_analyze():
    db.init_db()
    overrides = request.get_json(silent=True) or {}
    try:
        result = run_analysis(overrides)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(result), 201


@app.route("/api/runs", methods=["GET"])
def api_list_runs():
    db.init_db()
    return jsonify(db.list_runs())


@app.route("/api/runs/<int:run_id>", methods=["GET"])
def api_get_run(run_id):
    db.init_db()
    result = db.get_run(run_id)
    if result is None:
        return jsonify({"error": "run not found"}), 404
    return jsonify(result)


if __name__ == "__main__":
    db.init_db()
    app.run(debug=True, port=5000)
