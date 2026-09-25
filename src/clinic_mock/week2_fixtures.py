"""Synthetic Week 2 benchmark records; enabled only on a dedicated local mock."""

from __future__ import annotations

from datetime import datetime, timedelta

from clinic_mock.schemas import Appointment, Patient, PatientRef, PatientVerify

PATIENTS = [
    ("02", "Nguyễn Văn A", "1983-03-14"),
    ("03", "Nguyễn Thị Mai", "1985-04-12"),
    ("04", "Nguyễn Thị Mai", "1985-04-21"),
    ("05", "Trần Văn Nam", "1972-11-03"),
    ("06", "Trần Văn Nam", "1982-11-03"),
    ("07", "Lê Thị Mỹ Linh", "1990-01-09"),
    ("08", "Đỗ Quốc Việt", "1968-12-31"),
    ("09", "Phạm Minh Anh", "1985-04-12"),
]

# alias, patient, status, clinic, local start, department, version
APPOINTMENTS = [
    ("02", "02", "SCHEDULED", "c_001", "2026-10-15T09:05:00+07:00", "Tim mạch", 1),
    ("03", "03", "BOOKED", "c_002", "2026-10-16T10:45:00+07:00", "Da liễu", 1),
    ("04", "04", "SCHEDULED", "c_001", "2026-10-17T14:15:00+07:00", "Tai Mũi Họng", 2),
    ("05", "05", "SCHEDULED", "c_002", "2026-10-18T08:30:00+07:00", "Nội tổng quát", 4),
    ("06", "06", "SCHEDULED", "cl_vinmec", "2026-10-19T16:05:00+07:00", "Mắt", 1),
    ("07", "07", "SCHEDULED", "c_001", "2026-10-20T11:20:00+07:00", "Cơ xương khớp", 2),
    ("08", "08", "BOOKED", "c_002", "2026-10-21T13:40:00+07:00", "Tổng quát", 1),
    (
        "09",
        "09",
        "SCHEDULED",
        "cl_vinmec",
        "2026-10-22T09:50:00+07:00",
        "Tai Mũi Họng",
        4,
    ),
    ("10", "03", "SCHEDULED", "c_001", "2026-10-23T15:10:00+07:00", "Tim mạch", 3),
    ("11", "05", "CONFIRMED", "c_002", "2026-10-24T08:30:00+07:00", "Nội tổng quát", 2),
    (
        "12",
        "07",
        "UNREACHABLE",
        "c_001",
        "2026-10-25T11:20:00+07:00",
        "Cơ xương khớp",
        2,
    ),
]

PROVIDER_BY_CLINIC = {
    "c_001": "pr_456",
    "c_002": "pr_789",
    "cl_vinmec": "pr_vinmec_1",
}


def seed_week2(db, tenant_id: str) -> None:
    """Add deterministic, occupied records without changing canonical fixtures."""
    for suffix, full_name, dob in PATIENTS:
        patient_id = f"pt_eval_{suffix}"
        db.patients[patient_id] = Patient(
            patient_id=patient_id,
            tenant_id=tenant_id,
            display_name=f"{full_name.split()[-1]} {full_name[0]}.",
            phone=f"09000000{suffix}",
            dob=dob,
            verify=PatientVerify(full_name=full_name, dob=dob),
        )

    for (
        suffix,
        patient_suffix,
        status,
        clinic_id,
        starts_at,
        department,
        version,
    ) in APPOINTMENTS:
        patient = db.patients[f"pt_eval_{patient_suffix}"]
        start = datetime.fromisoformat(starts_at)
        appointment_id = f"apt_eval_{suffix}"
        db.appointments[appointment_id] = Appointment(
            appointment_id=appointment_id,
            tenant_id=tenant_id,
            slot_id=f"slot_eval_{suffix}",
            provider_id=PROVIDER_BY_CLINIC[clinic_id],
            status=status,
            clinic_id=clinic_id,
            starts_at=starts_at,
            ends_at=(start + timedelta(minutes=30)).isoformat(),
            department=department,
            patient=PatientRef(
                patient_id=patient.patient_id,
                display_name=patient.display_name,
                verify=patient.verify,
            ),
            confirmed_at=("2026-10-23T10:00:00+07:00" if suffix == "11" else None),
            confirmed_via=("callbot" if suffix == "11" else None),
            unreachable_reason=("NO_ANSWER" if suffix == "12" else None),
            attempt_count=(1 if suffix == "12" else 0),
            version=version,
        )
