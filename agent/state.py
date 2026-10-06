from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: str  # "user" | "model" | "system" | "tool"
    content: str
    tool_calls: Optional[List[Dict[str, Any]]] = None
    tool_responses: Optional[List[Dict[str, Any]]] = None
    timestamp_iso: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class PatientSession(BaseModel):
    session_id: str
    patient_id: Optional[str] = None
    patient_name: Optional[str] = None
    patient_phone: Optional[str] = None
    identified_specialty: Optional[str] = None
    selected_doctor_id: Optional[str] = None
    selected_doctor_name: Optional[str] = None
    selected_slot_iso: Optional[str] = None
    appointment_id: Optional[str] = None
    active_appointments: List[Dict[str, Any]] = Field(default_factory=list)
    emergency_flag: bool = False
    emergency_details: Optional[str] = None
    booking_status: str = "INTAKE"  # INTAKE | NEGOTIATING | CONFIRMED | ESCALATED | CANCELLED
    messages: List[ChatMessage] = Field(default_factory=list)
    turn_count: int = 0
    metadata: Dict[str, Any] = Field(default_factory=dict)

    def add_appointment(self, appt_dict: Dict[str, Any]) -> None:
        """Adds an appointment to the session's active appointments ledger."""
        self.active_appointments = [a for a in self.active_appointments if a.get("id") != appt_dict.get("id")]
        self.active_appointments.append(appt_dict)
        self.appointment_id = appt_dict.get("id")
        self.selected_slot_iso = appt_dict.get("slot_iso")
        self.selected_doctor_name = appt_dict.get("doctor_name")
        self.booking_status = "CONFIRMED"

    def update_appointment_slot(self, appt_id: str, new_slot_iso: str) -> None:
        for a in self.active_appointments:
            if a.get("id") == appt_id:
                a["slot_iso"] = new_slot_iso
                a["status"] = "CONFIRMED"
        self.appointment_id = appt_id
        self.selected_slot_iso = new_slot_iso

    def add_message(self, role: str, content: str, tool_calls=None, tool_responses=None) -> None:
        self.messages.append(ChatMessage(
            role=role,
            content=content,
            tool_calls=tool_calls,
            tool_responses=tool_responses
        ))
        if role == "user":
            self.turn_count += 1
