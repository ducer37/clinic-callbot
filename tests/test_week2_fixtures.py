"""The optional benchmark pack must not alter the default scoring fixtures."""

from clinic_mock.store import db, seed_default
from tests.conftest import AUTH_A


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
