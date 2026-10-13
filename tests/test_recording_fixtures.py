"""Recording profile retains occupied/free consistency and both full identities."""

from datetime import date, datetime
from itertools import pairwise

import pytest

from clinic_mock.recording_fixtures import CALLER_NUMBER, recording_date, seed_recording
from clinic_mock.store import CANONICAL_TENANT, Store, db, seed_default
from tests.conftest import AUTH_A, AUTH_B, write_headers

BASE = date(2026, 11, 2)


def test_recording_dataset_is_small_future_and_has_no_provider_overlap():
    db = Store()
    seed_recording(db, CANONICAL_TENANT, BASE)
    assert len(db.patients) == len(db.appointments) == 2
    assert len(db.slots) == 1
    assert {p.verify.full_name: p.verify.dob for p in db.patients.values()} == {
        "Nguyễn Tuấn Đức": "2000-07-31",
        "Lê Thị Mỹ Linh": "1990-01-09",
    }
    assert {p.phone for p in db.patients.values()} == {CALLER_NUMBER}
    intervals = [(a.starts_at, a.ends_at) for a in db.appointments.values()] + [
        (s.start_time, s.end_time) for s in db.slots.values()
    ]
    parsed = sorted(
        (datetime.fromisoformat(s), datetime.fromisoformat(e)) for s, e in intervals
    )
    assert all(
        s.date() == BASE and s.utcoffset().total_seconds() == 7 * 3600
        for s, e in parsed
    )
    assert all(e <= next_s for (_, e), (next_s, _) in pairwise(parsed))
    assert all(
        a.status == "SCHEDULED" and a.version == 1 and a.attempt_count == 0
        for a in db.appointments.values()
    )
    assert not ({a.slot_id for a in db.appointments.values()} & db.slots.keys())


@pytest.mark.parametrize("value", ["2026-02-30", "2026-1-2", "02/11/2026", "tomorrow"])
def test_recording_date_rejects_non_iso_or_invalid_dates(value):
    with pytest.raises(ValueError, match="MOCK_RECORDING_BASE_DATE"):
        recording_date(value)


def test_pinned_recording_date_does_not_follow_reset_day():
    assert recording_date("2026-11-02") == BASE


def enable_recording(monkeypatch):
    monkeypatch.setenv("MOCK_RECORDING_FIXTURES", "1")
    monkeypatch.setenv("MOCK_RECORDING_BASE_DATE", BASE.isoformat())
    monkeypatch.setenv("MOCK_WEEK2_FIXTURES", "0")
    monkeypatch.setenv("MOCK_BOOKING_FIXTURES", "0")
    seed_default()


@pytest.mark.parametrize("endpoint", ["/_harness/seed", "/_harness/reset"])
def test_seed_reset_restores_both_people_and_consumed_slot(
    client, monkeypatch, endpoint
):
    enable_recording(monkeypatch)
    before = client.get("/_harness/state", headers=AUTH_A).json()
    assert len(before["patients"]) == 2
    assert len(before["appointments"]) == 2
    assert len(before["slots"]) == 1
    # The shared synthetic phone is only a lookup hint, never identity proof.
    for auth in [AUTH_A, AUTH_B]:
        patients = client.get(
            "/v1/patients", params={"phone": CALLER_NUMBER}, headers=auth
        )
        assert {p["patient_id"] for p in patients.json()["data"]} == {
            "pt_3391",
            "pt_eval_07",
        }
    booked = client.post(
        "/v1/appointments",
        headers={**AUTH_A, **write_headers()},
        json={"patient_id": "pt_eval_07", "slot_id": "slot_91d2"},
    )
    assert booked.status_code == 201
    assert not db.slots
    assert client.post(endpoint, headers=AUTH_A).status_code == 200
    assert client.get("/_harness/state", headers=AUTH_A).json() == before


@pytest.mark.parametrize("appointment_id", ["apt_00417", "apt_eval_07"])
def test_recording_reschedule_releases_original_slot_and_keeps_other_person(
    client, monkeypatch, appointment_id
):
    enable_recording(monkeypatch)
    before = {k: a.model_dump() for k, a in db.appointments.items()}
    old_slot = db.appointments[appointment_id].slot_id
    response = client.post(
        f"/v1/appointments/{appointment_id}/reschedule",
        headers={**AUTH_A, **write_headers(version=1)},
        json={"new_slot_id": "slot_91d2", "requested_by": "patient"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "RESCHEDULED"
    assert response.json()["new_slot_id"] == "slot_91d2"
    assert set(db.slots) == {old_slot}
    other = (set(before) - {appointment_id}).pop()
    assert db.appointments[other].model_dump() == before[other]
    assert len(db.appointments) == 2


def test_recording_exposes_only_requested_day_and_occupied_slots_are_unavailable(
    client, monkeypatch
):
    enable_recording(monkeypatch)
    for day, count in [("2026-11-02", 1), ("2026-11-03", 0)]:
        response = client.get(
            "/v1/slots",
            headers=AUTH_A,
            params={
                "clinic_id": "cl_vinmec",
                "from": f"{day}T00:00:00+07:00",
                "to": f"{day}T23:59:59+07:00",
            },
        )
        assert response.status_code == 200
        assert len(response.json()["data"]) == count
        if count:
            assert (
                response.json()["data"][0]["start_time"] == "2026-11-02T15:00:00+07:00"
            )


@pytest.mark.parametrize("flag", ["MOCK_WEEK2_FIXTURES", "MOCK_BOOKING_FIXTURES"])
def test_conflicting_profile_configuration_does_not_reset_data(monkeypatch, flag):
    before = {k: a.model_dump() for k, a in db.appointments.items()}
    monkeypatch.setenv("MOCK_RECORDING_FIXTURES", "1")
    monkeypatch.setenv(flag, "1")
    with pytest.raises(ValueError, match="packs off"):
        seed_default()
    assert {k: a.model_dump() for k, a in db.appointments.items()} == before
