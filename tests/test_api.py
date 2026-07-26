"""Flask test-client tests for the REST API. Uses a temporary SQLite file
(via the src.db module's db_path parameter) loaded with a couple of
synthetic rows so tests don't depend on sample_data or leave rootcause.db
behind.
"""
import os
import tempfile

import pytest

import app as app_module
from src import db


@pytest.fixture
def client(monkeypatch):
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    monkeypatch.setattr(db, "DB_PATH", path)

    db.init_db(path)
    rows = []
    for d, period, mult in [("2026-01-01", "baseline", 1.0), ("2026-01-02", "baseline", 1.0),
                             ("2026-01-03", "baseline", 1.0), ("2026-01-04", "baseline", 1.0),
                             ("2026-01-05", "baseline", 1.0), ("2026-02-01", "current", 0.5),
                             ("2026-02-02", "current", 0.5), ("2026-02-03", "current", 0.5),
                             ("2026-02-04", "current", 0.5), ("2026-02-05", "current", 0.5)]:
        rows.append({
            "date": d, "period": period, "region": "East", "channel": "Online",
            "product_category": "Electronics", "customer_segment": "Consumer",
            "revenue": 100 * mult, "units": 10,
        })
    db.insert_facts(rows, path)

    app_module.app.config["TESTING"] = True
    with app_module.app.test_client() as c:
        yield c

    os.remove(path)


def test_config_endpoint(client):
    res = client.get("/api/config")
    assert res.status_code == 200
    data = res.get_json()
    assert "dimensions" in data
    assert data["metric"] == "revenue"


def test_analyze_and_list_and_get_run(client):
    res = client.post("/api/analyze", json={})
    assert res.status_code == 201
    result = res.get_json()
    assert result["baseline_total"] == 500
    assert result["current_total"] == 250
    assert "narrative" in result
    assert "tree" in result

    res = client.get("/api/runs")
    assert res.status_code == 200
    runs = res.get_json()
    assert len(runs) == 1

    run_id = runs[0]["id"]
    res = client.get(f"/api/runs/{run_id}")
    assert res.status_code == 200
    assert res.get_json()["id"] == run_id


def test_get_missing_run_404(client):
    res = client.get("/api/runs/9999")
    assert res.status_code == 404


def test_dashboard_renders(client):
    client.post("/api/analyze", json={})
    res = client.get("/")
    assert res.status_code == 200
    assert b"Root-Cause" in res.data
