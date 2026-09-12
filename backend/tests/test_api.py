"""/api/verify 接口测试:状态码、结论形状、422 整批拒绝。"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def r(slot, cid, cat) -> dict:
    return {"slot": slot, "container_id": cid, "category": cat}


def test_health():
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_verify_empty_batch():
    resp = client.post("/api/verify", json={"rows": []})
    assert resp.status_code == 200
    assert resp.json() == {"results": []}


def test_verify_pass_and_fail_slots():
    resp = client.post(
        "/api/verify",
        json={
            "rows": [
                r(3, "A1", "A"),
                r(3, "B1", "B"),  # A-B 禁配
                r(1, "N1", "N"),
                r(1, "N2", "N"),
            ]
        },
    )
    assert resp.status_code == 200
    data = resp.json()["results"]
    assert [item["slot"] for item in data] == [1, 3]
    assert data[0]["ok"] is True
    assert data[0]["conflicts"] == []
    assert data[1]["ok"] is False
    assert data[1]["conflicts"] == [["A1", "B1"]]


def test_422_duplicate_id_returns_row_indices():
    resp = client.post(
        "/api/verify",
        json={"rows": [r(1, "DUP", "A"), r(2, "DUP", "B")]},
    )
    assert resp.status_code == 422
    detail = resp.json()["detail"]
    assert isinstance(detail, list)
    assert {e["code"] for e in detail} == {"duplicate_id"}
    assert {e["index"] for e in detail} == {0, 1}


def test_422_unknown_category():
    resp = client.post("/api/verify", json={"rows": [r(1, "C1", "X")]})
    assert resp.status_code == 422
    assert resp.json()["detail"][0]["code"] == "unknown_category"


def test_422_duplicate_assignment():
    resp = client.post(
        "/api/verify",
        json={"rows": [r(5, "C1", "A"), r(5, "C1", "B")]},
    )
    assert resp.status_code == 422
    codes = {e["code"] for e in resp.json()["detail"]}
    assert "duplicate_assignment" in codes
    assert "duplicate_id" in codes


def test_422_over_capacity():
    rows = [r(9, f"C{i}", "N") for i in range(5)]
    resp = client.post("/api/verify", json={"rows": rows})
    assert resp.status_code == 422
    detail = resp.json()["detail"]
    assert {e["code"] for e in detail} == {"slot_over_capacity"}
    assert len(detail) == 5


def test_422_mixed_field_errors_keep_indices():
    resp = client.post(
        "/api/verify",
        json={
            "rows": [
                r(1, "GOOD", "N"),
                {"slot": 0, "container_id": "C2", "category": "A"},
                r(3, "C3", "?"),
                "not-an-object",
            ]
        },
    )
    assert resp.status_code == 422
    by_index: dict[int, set[str]] = {}
    for e in resp.json()["detail"]:
        by_index.setdefault(e["index"], set()).add(e["code"])
    assert by_index == {
        1: {"bad_slot"},
        2: {"unknown_category"},
        3: {"row_format"},
    }


def test_boundary_slots_accepted():
    resp = client.post(
        "/api/verify",
        json={"rows": [r(1, "C1", "A"), r(99, "C2", "B")]},
    )
    assert resp.status_code == 200
    assert [item["slot"] for item in resp.json()["results"]] == [1, 99]
