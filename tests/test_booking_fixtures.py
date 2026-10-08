"""Exercise the optional pack through real discovery, booking and reset APIs."""

from datetime import date, datetime, timedelta

import pytest
from clinic_mock import booking_fixtures
from clinic_mock.booking_fixtures import (
    BUSY_APPOINTMENT_ID,
    BUSY_SLOT_ID,
    COMPETING_PATIENT_ID,
    LOCAL_TZ,
)
from clinic_mock.store import db, seed_default

from tests.conftest import AUTH_A, AUTH_B, write_headers

BASE = date(2026, 11, 2)


def enable_pack(monkeypatch):
    monkeypatch.setenv("MOCK_BOOKING_FIXTURES", "1")
    monkeypatch.setenv("MOCK_BOOKING_BASE_DATE", BASE.isoformat())
    seed_default()


def discover(
    client, offset, start="00:00", end="23:59", clinic="cl_vinmec", auth=AUTH_A
):
    day = BASE + timedelta(days=offset)
    response = client.get(
        "/v1/slots",
        params={
            "clinic_id": clinic,
            "from": f"{day}T{start}:00+07:00",
            "to": f"{day}T{end}:00+07:00",
        },
        headers=auth,
    )
    assert response.status_code == 200
    return response.json()["data"]


def test_pack_disabled_preserves_defaults_and_can_be_removed(client, monkeypatch):
    monkeypatch.delenv("MOCK_BOOKING_FIXTURES", raising=False)
    seed_default()
    before = client.get("/_harness/state", headers=AUTH_A).json()
    assert not any(key.startswith("slot_booking_") for key in db.slots)
    enable_pack(monkeypatch)
    assert BUSY_APPOINTMENT_ID in db.appointments
    monkeypatch.setenv("MOCK_BOOKING_FIXTURES", "0")
    assert client.post("/_harness/reset", headers=AUTH_A).json() == {"reset": True}
    assert client.get("/_harness/state", headers=AUTH_A).json() == before


def test_busy_time_has_real_available_neighbors_but_cannot_be_booked(
    client, monkeypatch
):
    enable_pack(monkeypatch)
    # Exercise an explicit API window; GET's upper bound is exclusive.
    slots = discover(client, 0, "09:00", "10:00")
    assert [
        datetime.fromisoformat(s["start_time"]).strftime("%H:%M") for s in slots
    ] == ["09:00", "09:15", "09:45"]
    assert BUSY_SLOT_ID not in db.slots
    busy = client.get(f"/v1/appointments/{BUSY_APPOINTMENT_ID}", headers=AUTH_A)
    assert busy.status_code == 200
    assert busy.json()["status"] == "BOOKED"
    response = client.post(
        "/v1/appointments",
        headers={**AUTH_A, **write_headers()},
        json={"patient_id": "pt_3391", "slot_id": BUSY_SLOT_ID},
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_more_choices_sparse_windows_and_clinic_filter(client, monkeypatch):
    enable_pack(monkeypatch)
    assert len(discover(client, 0, "09:00", "11:00")) == 6
    assert len(discover(client, 0, "11:00", "12:00")) == 1
    assert [
        datetime.fromisoformat(slot["start_time"]).strftime("%H:%M")
        for slot in discover(client, 0, "12:00", "18:00")
    ] == ["14:00", "14:30", "15:00"]
    assert len(discover(client, 1, "13:30", "14:30")) == 1
    assert len(discover(client, 2, "09:00", "10:00")) == 2
    assert discover(client, 3, "17:00", "18:00") == []
    assert len(discover(client, 4, "07:00", "07:15")) == 1
    other = discover(client, 4, clinic="cl_booking_other")
    assert len(other) == 1
    assert other[0]["clinic_id"] == "cl_booking_other"
    # The canonical demo caller still uniquely resolves to the original patient.
    patients = client.get(
        "/v1/patients", params={"phone": "0912345600"}, headers=AUTH_A
    ).json()["data"]
    assert [p["patient_id"] for p in patients] == ["pt_3391"]


def test_boundary_is_discoverable_with_equivalent_utc_window(client, monkeypatch):
    enable_pack(monkeypatch)
    day = BASE + timedelta(days=4)
    response = client.get(
        "/v1/slots",
        params={
            "clinic_id": "cl_vinmec",
            "from": f"{day}T00:00:00Z",
            "to": f"{day}T00:15:00Z",
        },
        headers=AUTH_A,
    )
    assert response.status_code == 200
    assert [s["slot_id"] for s in response.json()["data"]] == [
        "slot_booking_boundary_0700"
    ]


@pytest.mark.parametrize("endpoint", ["/_harness/reset", "/_harness/seed"])
def test_booking_replay_and_reset_restore_entire_baseline(
    client, monkeypatch, endpoint
):
    enable_pack(monkeypatch)
    before = client.get("/_harness/state", headers=AUTH_A).json()
    slots = discover(client, 0)
    body = {"patient_id": "pt_3391", "slot_id": slots[0]["slot_id"]}
    headers = {**AUTH_A, **write_headers()}
    booked = client.post("/v1/appointments", headers=headers, json=body)
    assert booked.status_code == 201
    appointment = booked.json()
    assert appointment["status"] == "BOOKED"
    assert appointment["version"] == 1
    assert appointment["attempt_count"] == 0
    assert body["slot_id"] not in {s["slot_id"] for s in discover(client, 0)}
    replay = client.post("/v1/appointments", headers=headers, json=body)
    assert replay.status_code == 201
    assert replay.json() == appointment
    after = client.get("/_harness/state", headers=AUTH_A).json()
    assert len(after["appointments"]) == len(before["appointments"]) + 1
    assert client.post(endpoint, headers=AUTH_A).status_code == 200
    assert client.get("/_harness/state", headers=AUTH_A).json() == before
    # Reset does not clear upstream's separate idempotency cache. New run = new key.
    new_booking = client.post(
        "/v1/appointments", headers={**AUTH_A, **write_headers()}, json=body
    )
    assert new_booking.status_code == 201
    assert new_booking.json()["appointment_id"] != appointment["appointment_id"]


def test_competing_booking_consumes_an_already_discovered_slot(client, monkeypatch):
    enable_pack(monkeypatch)
    offered = discover(client, 0, "09:00", "10:00")
    chosen = offered[1]["slot_id"]
    race = client.post(
        "/v1/appointments",
        headers={**AUTH_A, **write_headers()},
        json={"patient_id": COMPETING_PATIENT_ID, "slot_id": chosen},
    )
    assert race.status_code == 201
    response = client.post(
        "/v1/appointments",
        headers={**AUTH_A, **write_headers()},
        json={"patient_id": "pt_3391", "slot_id": chosen},
    )
    assert response.status_code == 404
    remaining = discover(client, 0, "09:00", "10:00")
    assert chosen not in {s["slot_id"] for s in remaining}
    assert len(remaining) == 2


def test_pack_coexists_with_week2_and_has_no_provider_overlap(client, monkeypatch):
    monkeypatch.setenv("MOCK_WEEK2_FIXTURES", "1")
    enable_pack(monkeypatch)
    assert "apt_eval_02" in db.appointments
    assert db.appointments["apt_00417"].version == 3
    intervals = [
        (s.clinic_id, s.provider_id, s.start_time, s.end_time)
        for s in db.slots.values()
    ] + [
        (a.clinic_id, a.provider_id, a.starts_at, a.ends_at)
        for a in db.appointments.values()
    ]
    for clinic, provider, start, end in intervals:
        if not provider.startswith("pr_booking_"):
            continue
        start_dt, end_dt = datetime.fromisoformat(start), datetime.fromisoformat(end)
        overlaps = [
            row
            for row in intervals
            if row[0:2] == (clinic, provider)
            and datetime.fromisoformat(row[2]) < end_dt
            and datetime.fromisoformat(row[3]) > start_dt
        ]
        assert len(overlaps) == 1
    assert discover(client, 0, auth=AUTH_A) == discover(client, 0, auth=AUTH_B)


def test_startup_loads_pack_from_empty_store(client, monkeypatch):
    monkeypatch.setenv("MOCK_BOOKING_FIXTURES", "1")
    monkeypatch.setenv("MOCK_BOOKING_BASE_DATE", BASE.isoformat())
    db.reset()
    with client:
        assert len(discover(client, 0, "09:00", "11:00")) == 6
        assert BUSY_APPOINTMENT_ID in db.appointments


def test_demo_date_uses_vietnam_tomorrow_at_utc_day_boundary(monkeypatch):
    monkeypatch.delenv("MOCK_BOOKING_BASE_DATE", raising=False)

    class FrozenDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            # 20:00 UTC = 03:00 on the next local day.
            return datetime.fromisoformat("2026-10-08T20:00:00+00:00").astimezone(tz)

    monkeypatch.setattr(booking_fixtures, "datetime", FrozenDatetime)
    assert booking_fixtures.resolve_base_date() == date(2026, 10, 10)
    assert booking_fixtures.local_start(BASE, 0, "09:00").tzinfo == LOCAL_TZ


def test_dotenv_settings_and_environment_override_are_reloaded_on_seed(
    client, monkeypatch, tmp_path
):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("MOCK_BOOKING_FIXTURES", raising=False)
    monkeypatch.delenv("MOCK_BOOKING_BASE_DATE", raising=False)
    (tmp_path / ".env").write_text(
        "MOCK_BOOKING_FIXTURES=1\nMOCK_BOOKING_BASE_DATE=2026-11-02\n",
        encoding="utf-8",
    )
    seed_default()
    assert len(discover(client, 0, "09:00", "11:00")) == 6
    monkeypatch.setenv("MOCK_BOOKING_BASE_DATE", "2026-11-03")
    assert client.post("/_harness/reset", headers=AUTH_A).status_code == 200
    assert discover(client, 0, "09:00", "11:00") == []
    assert len(discover(client, 1, "09:00", "11:00")) == 6
    monkeypatch.setenv("MOCK_BOOKING_FIXTURES", "0")
    seed_default()
    assert BUSY_APPOINTMENT_ID not in db.appointments


@pytest.mark.parametrize("value", ["tomorrow", "2026-02-30", "20261102"])
def test_bad_config_is_rejected_before_seed_clears_store(monkeypatch, value):
    before = dict(db.slots)
    monkeypatch.setenv("MOCK_BOOKING_FIXTURES", "1")
    monkeypatch.setenv("MOCK_BOOKING_BASE_DATE", value)
    with pytest.raises(ValueError, match="MOCK_BOOKING_BASE_DATE"):
        seed_default()
    assert db.slots == before
