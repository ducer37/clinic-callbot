"""Opt-in synthetic booking data for the team's disposable demo mock.

No API semantics are changed. Occupied slots exist only as appointments.
Dates are resolved once at startup/seed/reset, never during slot discovery.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from typing import TYPE_CHECKING

from clinic_mock.config import BookingFixtureSettings
from clinic_mock.schemas import Appointment, Patient, PatientRef, PatientVerify, Slot

if TYPE_CHECKING:
    from clinic_mock.store import Store

LOCAL_TZ = timezone(timedelta(hours=7))
CLINIC_ID = "cl_vinmec"
PROVIDER_ID = "pr_booking_demo"
BUSY_SLOT_ID = "slot_booking_busy_0930"
BUSY_APPOINTMENT_ID = "apt_booking_busy_0930"
COMPETING_PATIENT_ID = "pt_booking_competitor"

# First booking date is D. Dedicated providers avoid overlap with canonical/W2.
# Each row: stable slot alias, days after D, local start, clinic.
SLOT_LAYOUT = (
    ("many_0900", 0, "09:00", CLINIC_ID),
    ("many_0915", 0, "09:15", CLINIC_ID),
    ("many_0945", 0, "09:45", CLINIC_ID),
    ("many_1000", 0, "10:00", CLINIC_ID),
    ("many_1015", 0, "10:15", CLINIC_ID),
    ("many_1030", 0, "10:30", CLINIC_ID),
    ("exact_1130", 0, "11:30", CLINIC_ID),
    ("afternoon_1400", 0, "14:00", CLINIC_ID),
    ("afternoon_1430", 0, "14:30", CLINIC_ID),
    ("afternoon_1500", 0, "15:00", CLINIC_ID),
    ("single_1400", 1, "14:00", CLINIC_ID),
    ("two_0900", 2, "09:00", CLINIC_ID),
    ("two_0930", 2, "09:30", CLINIC_ID),
    ("boundary_0700", 4, "07:00", CLINIC_ID),
    ("other_clinic_0900", 4, "09:00", "cl_booking_other"),
)


def resolve_base_date(configured: str | None = None) -> date:
    """First fixture day: explicit ISO date for tests, tomorrow locally for demo."""
    if configured is None:
        configured = BookingFixtureSettings().BOOKING_BASE_DATE
    configured = configured.strip()
    if configured:
        try:
            parsed = date.fromisoformat(configured)
            if parsed.isoformat() != configured:
                raise ValueError("Use YYYY-MM-DD")
            return parsed
        except ValueError as exc:
            raise ValueError("MOCK_BOOKING_BASE_DATE must use YYYY-MM-DD") from exc
    return datetime.now(LOCAL_TZ).date() + timedelta(days=1)


def local_start(base_date: date, offset: int, clock: str) -> datetime:
    day = base_date + timedelta(days=offset)
    return datetime.fromisoformat(f"{day.isoformat()}T{clock}:00").replace(
        tzinfo=LOCAL_TZ
    )


def seed_booking(db: Store, tenant_id: str, base_date: date) -> None:
    """Add free slots and one occupied interval without altering mentor records."""
    patient = Patient(
        patient_id=COMPETING_PATIENT_ID,
        tenant_id=tenant_id,
        display_name="Booking demo",
        phone="0900000191",
        dob="1990-01-01",
        verify=PatientVerify(full_name="Trần Minh Demo", dob="1990-01-01"),
    )
    db.patients[patient.patient_id] = patient
    for alias, offset, clock, clinic in SLOT_LAYOUT:
        start = local_start(base_date, offset, clock)
        slot_id = f"slot_booking_{alias}"
        db.slots[slot_id] = Slot(
            slot_id=slot_id,
            tenant_id=tenant_id,
            clinic_id=clinic,
            provider_id=(PROVIDER_ID if clinic == CLINIC_ID else "pr_booking_other"),
            start_time=start.isoformat(),
            end_time=(start + timedelta(minutes=15)).isoformat(),
        )
    start = local_start(base_date, 0, "09:30")
    db.appointments[BUSY_APPOINTMENT_ID] = Appointment(
        appointment_id=BUSY_APPOINTMENT_ID,
        tenant_id=tenant_id,
        slot_id=BUSY_SLOT_ID,
        provider_id=PROVIDER_ID,
        status="BOOKED",
        clinic_id=CLINIC_ID,
        starts_at=start.isoformat(),
        ends_at=(start + timedelta(minutes=15)).isoformat(),
        department="Tổng quát",
        patient=PatientRef(
            patient_id=patient.patient_id,
            display_name=patient.display_name,
            verify=patient.verify,
        ),
        version=1,
        attempt_count=0,
    )


if __name__ == "__main__":
    # Print a planning manifest without mutating the store or calling the harness.
    base = resolve_base_date()
    print(
        json.dumps(
            {
                "base_date": base.isoformat(),
                "timezone": "+07:00",
                "free_slots": [
                    {
                        "slot_id": f"slot_booking_{alias}",
                        "clinic_id": clinic,
                        "start_time": local_start(base, offset, clock).isoformat(),
                    }
                    for alias, offset, clock, clinic in SLOT_LAYOUT
                ],
                "occupied_start": local_start(base, 0, "09:30").isoformat(),
                "empty_window": {
                    "from": local_start(base, 3, "17:00").isoformat(),
                    "to": local_start(base, 3, "18:00").isoformat(),
                },
            },
            indent=2,
        )
    )
