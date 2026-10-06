import pytest
from clinic_db.database import ClinicDatabase


@pytest.fixture
def db():
    database = ClinicDatabase(db_path=":memory:")
    return database


def test_db_initial_seeding(db):
    doctors = db.list_doctors()
    assert len(doctors) == 4
    specialties = {d.specialty for d in doctors}
    assert "Cardiology" in specialties
    assert "Dermatology" in specialties
    assert "Pediatrics" in specialties
    assert "Orthopedics" in specialties


def test_find_available_slots(db):
    derm_slots = db.find_available_slots(specialty="Dermatology")
    assert len(derm_slots) >= 3
    for s in derm_slots:
        assert s.status == "AVAILABLE"
        assert s.specialty == "Dermatology"


def test_atomic_booking_success(db):
    slots = db.find_available_slots(specialty="Dermatology")
    target_slot = slots[0]

    apt, err = db.book_slot_atomic(
        patient_name="Alice Smith",
        patient_phone="+1-555-0199",
        doctor_id=target_slot.doctor_id,
        slot_iso=target_slot.start_time_iso,
        reason="Skin allergy check"
    )

    assert err is None
    assert apt is not None
    assert apt.patient_name == "Alice Smith"
    assert apt.status == "CONFIRMED"

    # Verify slot is no longer available
    remaining = db.find_available_slots(specialty="Dermatology")
    remaining_times = [s.start_time_iso for s in remaining]
    assert target_slot.start_time_iso not in remaining_times


def test_double_booking_prevention(db):
    slots = db.find_available_slots(specialty="Dermatology")
    target_slot = slots[0]

    # First booking succeeds
    apt1, err1 = db.book_slot_atomic(
        patient_name="Patient 1",
        patient_phone="+1-555-0111",
        doctor_id=target_slot.doctor_id,
        slot_iso=target_slot.start_time_iso,
        reason="First check"
    )
    assert err1 is None

    # Second concurrent booking on same slot MUST fail
    apt2, err2 = db.book_slot_atomic(
        patient_name="Patient 2",
        patient_phone="+1-555-0222",
        doctor_id=target_slot.doctor_id,
        slot_iso=target_slot.start_time_iso,
        reason="Second check"
    )
    assert apt2 is None
    assert "already booked" in err2.lower()


def test_log_emergency_triage(db):
    triage = db.log_emergency_triage(
        reported_symptoms="Severe chest pain and left arm numbness",
        severity="EMERGENCY",
        patient_name="John Doe",
        patient_phone="+1-555-0999"
    )
    assert triage.id.startswith("TRG_")
    assert triage.severity == "EMERGENCY"

    logs = db.get_triage_logs()
    assert len(logs) == 1
    assert logs[0].reported_symptoms == "Severe chest pain and left arm numbness"


def test_reschedule_appointment(db):
    # Seeded existing appointment: APT_ORTH_101
    new_slot = "2026-10-16T14:00:00Z"
    apt, err = db.reschedule_appointment_atomic(
        appointment_id="APT_ORTH_101",
        new_slot_iso=new_slot
    )
    assert err is None
    assert apt.slot_iso == new_slot


def test_cancel_appointment(db):
    # Book a slot first
    slots = db.find_available_slots(specialty="Cardiology")
    target_slot = slots[0]

    apt, err = db.book_slot_atomic(
        patient_name="Cancel Test Patient",
        patient_phone="+1-555-4321",
        doctor_id=target_slot.doctor_id,
        slot_iso=target_slot.start_time_iso,
        reason="Checkup"
    )
    assert err is None
    assert apt is not None

    # Cancel the appointment
    cancelled = db.cancel_appointment(apt.id)
    assert cancelled is True

    # Slot should now be available again
    available_slots = db.find_available_slots(doctor_id=target_slot.doctor_id)
    assert any(s.start_time_iso == target_slot.start_time_iso for s in available_slots)

    # Calling cancel again should return False
    cancelled_again = db.cancel_appointment(apt.id)
    assert cancelled_again is False
