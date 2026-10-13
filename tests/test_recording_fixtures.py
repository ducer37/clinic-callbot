"""Recording profile retains occupied/free consistency and both full identities."""

from datetime import date, datetime
from itertools import pairwise

import pytest

from clinic_mock.recording_fixtures import CALLER_NUMBER, recording_date, seed_recording
from clinic_mock.store import CANONICAL_TENANT, Store

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
