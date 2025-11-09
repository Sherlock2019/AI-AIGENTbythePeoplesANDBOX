from fastapi.testclient import TestClient

from app import app

client = TestClient(app)


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert "cases" in resp.json()


def test_solve_pipeline():
    payload = {
        "problem": "Service fails in WSL with getpwuid error",
        "context": "PATH has UnLockCatch; Python 3.10; Ubuntu 20.04",
    }
    resp = client.post("/solve", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body["plan"]["assumptions"]
    assert body["strategy"]
    assert body["new_case"]["id"].startswith("CASE-")
