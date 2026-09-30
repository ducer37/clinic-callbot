"""The optional benchmark pack must not alter the default scoring fixtures."""

from clinic_mock.store import db, seed_default
from tests.conftest import AUTH_A, write_headers


def test_week2_pack_is_opt_in_and_resettable(client, monkeypatch):
    monkeypatch.delenv("MOCK_WEEK2_FIXTURES", raising=False)
    seed_default()
    assert "apt_eval_02" not in db.appointments

    monkeypatch.setenv("MOCK_WEEK2_FIXTURES", "1")
    seed_default()
    state = client.get("/_harness/state", headers=AUTH_A).json()
    appointments = {item["appointment_id"]: item for item in state["appointments"]}
    assert len(appointments) == 12
    assert appointments["apt_00417"]["patient"]["verify"]["full_name"] == "Nguyễn Văn A"
    assert appointments["apt_eval_02"]["patient"]["verify"]["dob"] == "1983-03-14"
    assert appointments["apt_eval_03"]["status"] == "BOOKED"
    assert appointments["apt_eval_10"]["patient"]["patient_id"] == "pt_eval_03"
    assert appointments["apt_eval_11"]["confirmed_via"] == "callbot"
    assert appointments["apt_eval_12"]["attempt_count"] == 1
    assert not any(slot["slot_id"].startswith("slot_eval_") for slot in state["slots"])

    reset = client.post("/_harness/reset", headers=AUTH_A)
    assert reset.status_code == 200
    assert client.get("/v1/appointments/apt_eval_10", headers=AUTH_A).status_code == 200

    monkeypatch.delenv("MOCK_WEEK2_FIXTURES")
    seed_default()
    assert "apt_eval_02" not in db.appointments


def test_reset_restores_changed_fixture_and_removes_runtime_records(client, monkeypatch):
    monkeypatch.setenv("MOCK_WEEK2_FIXTURES", "1")
    seed_default()
    before = client.get("/_harness/state", headers=AUTH_A).json()
    changed = client.post(
        "/v1/appointments/apt_eval_02/confirm",
        headers={**AUTH_A, **write_headers(version=1)},
    )
    assert changed.status_code == 200
    assert changed.json()["status"] == "CONFIRMED"
    assert changed.json()["version"] == 2
    created = client.post(
        "/_harness/patients",
        headers=AUTH_A,
        json={
            "display_name": "Synthetic test",
            "phone": "0900000099",
            "dob": "1990-01-01",
            "verify": {"full_name": "Synthetic test", "dob": "1990-01-01"},
        },
    )
    assert created.status_code == 201
    patient_id = created.json()["patient_id"]
    snapshot = client.post("/_harness/snapshot", headers=AUTH_A)
    assert snapshot.status_code == 200
    assert db.writelog.entries

    assert client.post("/_harness/reset", headers=AUTH_A).status_code == 200
    assert patient_id not in db.patients
    assert not db.snapshots
    assert not db.writelog.entries
    assert client.get("/_harness/state", headers=AUTH_A).json() == before


def test_startup_recreates_optional_pack_from_an_empty_store(client, monkeypatch):
    monkeypatch.setenv("MOCK_WEEK2_FIXTURES", "1")
    db.reset()
    with client:
        state = client.get("/_harness/state", headers=AUTH_A).json()
        appointments = {item["appointment_id"] for item in state["appointments"]}
        assert appointments == {"apt_00417", *[f"apt_eval_{i:02}" for i in range(2, 13)]}
