"""Small recording-only dataset for the team's fork, never a scoring fixture.

Two identities share a synthetic caller hint so the already-deployed browser
and inbound SIP demo can exercise either person without changing telephony.
Name and full DOB must still select exactly one patient in the bot.
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from typing import TYPE_CHECKING

from clinic_mock.booking_fixtures import local_start, resolve_base_date
from clinic_mock.schemas import Appointment, Patient, PatientRef, PatientVerify, Slot

if TYPE_CHECKING:
    from clinic_mock.store import Store

CALLER_NUMBER = "0912345600"
CLINIC_ID = "cl_vinmec"
PROVIDER_ID = "pr_vinmec_1"
FREE_SLOT_ID = "slot_91d2"
# Existing allowlisted appointment aliases avoid any voice-worker deployment.
# appointment, patient, full name, DOB, original clock, department, occupied slot
PEOPLE = (
    (
        "apt_00417",
        "pt_3391",
        "Nguyễn Tuấn Đức",
        "2000-07-31",
        "15:30",
        "Nội tổng quát",
        "slot_77aa",
    ),
    (
        "apt_eval_07",
        "pt_eval_07",
        "Lê Thị Mỹ Linh",
        "1990-01-09",
        "16:30",
        "Cơ xương khớp",
        "slot_eval_07",
    ),
)


def recording_date(configured: str) -> date:
    """Pin the recording day, or default to tomorrow in Vietnam on each seed."""
    try:
        return resolve_base_date(configured)
    except ValueError as exc:
        raise ValueError("MOCK_RECORDING_BASE_DATE must use YYYY-MM-DD") from exc


def seed_recording(db: Store, tenant_id: str, base: date) -> None:
    """Populate an empty recording store with two occupied and one free slot."""
    for appointment_id, patient_id, name, dob, clock, department, occupied in PEOPLE:
        patient = Patient(
            patient_id=patient_id,
            tenant_id=tenant_id,
            display_name=name,
            phone=CALLER_NUMBER,
            dob=dob,
            verify=PatientVerify(full_name=name, dob=dob),
        )
        db.patients[patient_id] = patient
        start = local_start(base, 0, clock)
        db.appointments[appointment_id] = Appointment(
            appointment_id=appointment_id,
            tenant_id=tenant_id,
            slot_id=occupied,
            provider_id=PROVIDER_ID,
            status="SCHEDULED",
            clinic_id=CLINIC_ID,
            starts_at=start.isoformat(),
            ends_at=(start + timedelta(minutes=30)).isoformat(),
            department=department,
            patient=PatientRef(
                patient_id=patient_id,
                display_name=name,
                verify=patient.verify,
            ),
            version=1,
            attempt_count=0,
        )
    start = local_start(base, 0, "15:00")
    db.slots[FREE_SLOT_ID] = Slot(
        slot_id=FREE_SLOT_ID,
        tenant_id=tenant_id,
        clinic_id=CLINIC_ID,
        provider_id=PROVIDER_ID,
        start_time=start.isoformat(),
        end_time=(start + timedelta(minutes=30)).isoformat(),
    )


if __name__ == "__main__":
    from clinic_mock.config import RecordingFixtureSettings
    from clinic_mock.store import CANONICAL_TENANT, Store

    store = Store()
    base = recording_date(RecordingFixtureSettings().RECORDING_BASE_DATE)
    seed_recording(store, CANONICAL_TENANT, base)
    print(
        json.dumps(
            {
                "base_date": base.isoformat(),
                "patients": [p.model_dump() for p in store.patients.values()],
                "appointments": [a.model_dump() for a in store.appointments.values()],
                "slots": [s.model_dump() for s in store.slots.values()],
                "empty_date": (base + timedelta(days=1)).isoformat(),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
