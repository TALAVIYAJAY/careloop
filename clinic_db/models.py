from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class Doctor(BaseModel):
    id: str
    name: str
    specialty: str
    room_number: str
    bio: str


class AppointmentSlot(BaseModel):
    id: str
    doctor_id: str
    doctor_name: str
    specialty: str
    start_time_iso: str
    end_time_iso: str
    status: str = "AVAILABLE"  # AVAILABLE | BOOKED | BLOCKED
    booked_patient_name: Optional[str] = None
    booked_patient_phone: Optional[str] = None


class Patient(BaseModel):
    id: str
    name: str
    phone: str
    created_at_iso: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    notes: Optional[str] = None


class Appointment(BaseModel):
    id: str
    patient_id: Optional[str] = None
    patient_name: str
    patient_phone: str
    doctor_id: str
    doctor_name: str
    specialty: str
    slot_iso: str
    reason: str
    status: str = "CONFIRMED"  # CONFIRMED | CANCELLED | RESCHEDULED
    visit_type: str = "ROUTINE"  # ROUTINE | MULTI_CHECKUP | FOLLOWUP
    created_at_iso: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    session_id: Optional[str] = None


class TriageLog(BaseModel):
    id: str
    patient_id: Optional[str] = None
    patient_name: Optional[str] = None
    patient_phone: Optional[str] = None
    reported_symptoms: str
    severity: str  # EMERGENCY | URGENT | ROUTINE
    action_taken: str
    timestamp_iso: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
