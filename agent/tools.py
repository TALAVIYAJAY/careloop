import json
from typing import Dict, Any, List, Optional
from clinic_db.database import ClinicDatabase


class ClinicToolDispatcher:
    """
    Executes scoped clinical tools against the clinic EHR database.
    Ensures safe parameter validation and returns structured JSON responses.
    """

    def __init__(self, db: Optional[ClinicDatabase] = None):
        self.db = db or ClinicDatabase()

    def search_available_slots(
        self,
        specialty: Optional[str] = None,
        doctor_name: Optional[str] = None,
        date_str: Optional[str] = None,
        doctor_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Search available clinic appointment slots by medical specialty, doctor name, or date (YYYY-MM-DD)."""
        if doctor_id:
            doctor_id = self.db.resolve_doctor_id(doctor_id)
        slots = self.db.find_available_slots(
            specialty=specialty,
            doctor_name=doctor_name,
            doctor_id=doctor_id,
            date_str=date_str
        )
        if not slots and date_str:
            # Check if doctor or specialty has slots on other upcoming dates
            other_date_slots = self.db.find_available_slots(
                specialty=specialty,
                doctor_name=doctor_name,
                doctor_id=doctor_id
            )
            if other_date_slots:
                return {
                    "status": "SUCCESS",
                    "note": f"No slots found on {date_str}, but available on other upcoming dates.",
                    "count": len(other_date_slots),
                    "available_slots": [s.model_dump() for s in other_date_slots]
                }

        if not slots:
            # Let's also fetch all doctors and broader open slots to give helpful alternatives
            docs = self.db.list_doctors(specialty=specialty)
            all_open = self.db.find_available_slots()
            return {
                "status": "NO_SLOTS_FOUND",
                "message": f"No available slots found matching the criteria (Specialty: {specialty}, Doctor: {doctor_name}, Date: {date_str}).",
                "registered_specialists": [d.model_dump() for d in docs],
                "alternative_slots": [s.model_dump() for s in all_open[:8]],
                "available_slots": []
            }

        return {
            "status": "SUCCESS",
            "count": len(slots),
            "available_slots": [s.model_dump() for s in slots]
        }

    def get_or_create_patient(self, name: str, phone: str) -> Dict[str, Any]:
        """Looks up or registers a patient in the Master Patient Index and returns their record and existing appointments."""
        patient = self.db.get_or_create_patient(name=name, phone=phone)
        existing_appts = self.db.get_patient_appointments(patient.id)
        return {
            "status": "SUCCESS",
            "patient": patient.model_dump(),
            "existing_appointments_count": len(existing_appts),
            "existing_appointments": [a.model_dump() for a in existing_appts]
        }

    def get_patient_appointments(self, patient_identifier: str) -> Dict[str, Any]:
        """Retrieves all past and active appointments for a patient by patient_id, phone, or name."""
        appts = self.db.get_patient_appointments(patient_identifier)
        return {
            "status": "SUCCESS",
            "count": len(appts),
            "appointments": [a.model_dump() for a in appts]
        }

    def book_appointment(
        self,
        patient_name: str,
        patient_phone: str,
        doctor_id: str,
        slot_iso: str,
        reason: str,
        session_id: Optional[str] = None,
        visit_type: Optional[str] = "ROUTINE",
        patient_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Atomically books a confirmed appointment slot for a patient, linking to their Master Patient ID."""
        resolved_doc_id = self.db.resolve_doctor_id(doctor_id, slot_iso=slot_iso)
        if resolved_doc_id:
            doctor_id = resolved_doc_id

        appointment, err = self.db.book_slot_atomic(
            patient_name=patient_name,
            patient_phone=patient_phone,
            doctor_id=doctor_id,
            slot_iso=slot_iso,
            reason=reason,
            session_id=session_id,
            visit_type=visit_type,
            patient_id=patient_id
        )
        if err:
            return {
                "status": "BOOKING_FAILED",
                "error": err
            }

        return {
            "status": "SUCCESS",
            "message": "Appointment successfully confirmed.",
            "appointment": appointment.model_dump()
        }

    def reschedule_appointment(
        self,
        appointment_id: str,
        new_slot_iso: str,
        patient_name: Optional[str] = None,
        patient_phone: Optional[str] = None,
        session_id: Optional[str] = None,
        doctor_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Reschedules an existing appointment to a new available slot with security verification."""
        if doctor_id:
            doctor_id = self.db.resolve_doctor_id(doctor_id, slot_iso=new_slot_iso)

        appointment, err = self.db.reschedule_appointment_atomic(
            appointment_id=appointment_id,
            new_slot_iso=new_slot_iso,
            patient_name=patient_name,
            patient_phone=patient_phone,
            session_id=session_id,
            doctor_id=doctor_id
        )
        if err:
            return {
                "status": "RESCHEDULE_FAILED",
                "error": err
            }

        return {
            "status": "SUCCESS",
            "message": "Appointment successfully rescheduled.",
            "appointment": appointment.model_dump()
        }

    def cancel_appointment(
        self,
        appointment_id: str,
        patient_name: Optional[str] = None,
        patient_phone: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Cancels an existing appointment and releases the associated slot."""
        success = self.db.cancel_appointment(appointment_id)
        if not success:
            return {
                "status": "CANCEL_FAILED",
                "error": f"Appointment '{appointment_id}' could not be found or is already cancelled."
            }
        return {
            "status": "SUCCESS",
            "message": f"Appointment '{appointment_id}' has been cancelled successfully and the slot is released.",
            "appointment_id": appointment_id
        }

    def trigger_emergency_escalation(
        self,
        symptoms: str,
        severity: str = "EMERGENCY",
        patient_name: Optional[str] = None,
        patient_phone: Optional[str] = None
    ) -> Dict[str, Any]:
        """Immediately logs a critical emergency triage event and aborts routine scheduling."""
        triage_log = self.db.log_emergency_triage(
            reported_symptoms=symptoms,
            severity=severity,
            patient_name=patient_name,
            patient_phone=patient_phone
        )
        return {
            "status": "EMERGENCY_ESCALATED",
            "triage_id": triage_log.id,
            "instruction": "URGENT CLINICAL OVERRIDE: Advise patient to immediately hang up and call 911 or proceed to nearest emergency room. Do NOT schedule a routine visit.",
            "triage_log": triage_log.model_dump()
        }

    def dispatch(self, tool_name: str, arguments: Dict[str, Any], session_id: Optional[str] = None) -> Dict[str, Any]:
        """Central dispatch method for executing tool calls by name."""
        if tool_name == "search_available_slots":
            return self.search_available_slots(
                specialty=arguments.get("specialty"),
                doctor_name=arguments.get("doctor_name"),
                doctor_id=arguments.get("doctor_id"),
                date_str=arguments.get("date_str")
            )
        elif tool_name == "get_or_create_patient":
            return self.get_or_create_patient(
                name=arguments.get("name", arguments.get("patient_name", "")),
                phone=arguments.get("phone", arguments.get("patient_phone", ""))
            )
        elif tool_name == "get_patient_appointments":
            return self.get_patient_appointments(
                patient_identifier=arguments.get("patient_identifier", arguments.get("patient_id", arguments.get("phone", "")))
            )
        elif tool_name == "book_appointment":
            return self.book_appointment(
                patient_name=arguments.get("patient_name", ""),
                patient_phone=arguments.get("patient_phone", ""),
                doctor_id=arguments.get("doctor_id", ""),
                slot_iso=arguments.get("slot_iso", ""),
                reason=arguments.get("reason", ""),
                session_id=session_id or arguments.get("session_id"),
                visit_type=arguments.get("visit_type", "ROUTINE"),
                patient_id=arguments.get("patient_id")
            )
        elif tool_name == "reschedule_appointment":
            return self.reschedule_appointment(
                appointment_id=arguments.get("appointment_id", ""),
                new_slot_iso=arguments.get("new_slot_iso", ""),
                doctor_id=arguments.get("doctor_id"),
                patient_name=arguments.get("patient_name"),
                patient_phone=arguments.get("patient_phone"),
                session_id=session_id or arguments.get("session_id")
            )
        elif tool_name == "cancel_appointment":
            return self.cancel_appointment(
                appointment_id=arguments.get("appointment_id", ""),
                patient_name=arguments.get("patient_name"),
                patient_phone=arguments.get("patient_phone"),
                session_id=session_id or arguments.get("session_id")
            )
        elif tool_name == "trigger_emergency_escalation":
            return self.trigger_emergency_escalation(
                symptoms=arguments.get("symptoms", ""),
                severity=arguments.get("severity", "EMERGENCY"),
                patient_name=arguments.get("patient_name"),
                patient_phone=arguments.get("patient_phone")
            )
        else:
            return {
                "status": "UNKNOWN_TOOL",
                "error": f"Tool '{tool_name}' is not recognized."
            }


# Tool Declarations Specification for Gemini Function Calling
CLINIC_TOOLS_DECLARATIONS = [
    {
        "name": "search_available_slots",
        "description": "Search available open appointment slots in the clinic by department specialty, doctor name, or specific date (format YYYY-MM-DD).",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "specialty": {
                    "type": "STRING",
                    "description": "Medical specialty (e.g. 'Cardiology', 'Dermatology', 'Pediatrics', 'Orthopedics')."
                },
                "doctor_name": {
                    "type": "STRING",
                    "description": "Name or partial name of preferred doctor (e.g. 'Dr. Chen', 'Dr. Jenkins')."
                },
                "date_str": {
                    "type": "STRING",
                    "description": "Target date filter in ISO format YYYY-MM-DD (e.g. '2026-10-15')."
                }
            }
        }
    },
    {
        "name": "get_or_create_patient",
        "description": "Looks up or creates a patient in the Master Patient Index by name and phone number. Returns patient_id and any existing appointments.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "name": {
                    "type": "STRING",
                    "description": "Full legal name of the patient."
                },
                "phone": {
                    "type": "STRING",
                    "description": "Contact telephone number of the patient."
                }
            },
            "required": ["name", "phone"]
        }
    },
    {
        "name": "get_patient_appointments",
        "description": "Retrieves all current, past, and upcoming appointments for a patient using their patient_id, phone, or name.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "patient_identifier": {
                    "type": "STRING",
                    "description": "Patient ID (e.g. 'PAT_8488862474') or phone number."
                }
            },
            "required": ["patient_identifier"]
        }
    },
    {
        "name": "book_appointment",
        "description": "Confirms and books an available appointment slot in the clinic EHR database. Requires patient full name and phone number.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "patient_name": {
                    "type": "STRING",
                    "description": "Full name of the patient."
                },
                "patient_phone": {
                    "type": "STRING",
                    "description": "Contact telephone number of the patient."
                },
                "doctor_id": {
                    "type": "STRING",
                    "description": "Unique identifier of the doctor (e.g. 'DOC_DERM_01')."
                },
                "slot_iso": {
                    "type": "STRING",
                    "description": "Exact ISO-8601 start time of the chosen slot (e.g. '2026-10-15T10:00:00Z')."
                },
                "reason": {
                    "type": "STRING",
                    "description": "Reason for visit or chief complaint."
                }
            },
            "required": ["patient_name", "patient_phone", "doctor_id", "slot_iso", "reason"]
        }
    },
    {
        "name": "reschedule_appointment",
        "description": "Reschedules an existing confirmed appointment to a new available slot. Requires verified patient identity for security.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "appointment_id": {
                    "type": "STRING",
                    "description": "Unique ID of existing appointment to reschedule (e.g. 'APT_ORTH_101')."
                },
                "new_slot_iso": {
                    "type": "STRING",
                    "description": "Exact ISO-8601 start time of new available slot."
                },
                "doctor_id": {
                    "type": "STRING",
                    "description": "Optional doctor ID if switching to or specifying the physician for the new slot (e.g. 'DOC_ORTH_004')."
                },
                "patient_name": {
                    "type": "STRING",
                    "description": "Full name of the patient requesting reschedule for security verification."
                },
                "patient_phone": {
                    "type": "STRING",
                    "description": "Contact phone of the patient for identity verification."
                }
            },
            "required": ["appointment_id", "new_slot_iso"]
        }
    },
    {
        "name": "cancel_appointment",
        "description": "Cancels an existing confirmed appointment by its appointment ID, releasing the slot back to available in clinic schedule.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "appointment_id": {
                    "type": "STRING",
                    "description": "Unique ID of the appointment to cancel (e.g. 'APT_9E97E528' or 'APT_ORTH_101')."
                },
                "patient_name": {
                    "type": "STRING",
                    "description": "Patient full name for cancellation record."
                }
            },
            "required": ["appointment_id"]
        }
    },
    {
        "name": "trigger_emergency_escalation",
        "description": "CRITICAL EMERGENCY ONLY: Call this tool ONLY for acute life-threatening medical emergencies (e.g. crushing chest pain, difficulty breathing, suspected stroke, severe trauma/uncontrolled bleeding, loss of consciousness). STRICTLY FORBIDDEN FOR ROUTINE ILLNESS: Do NOT call this tool for low fever, mild fever, cold, cough, runny nose, sore throat, mild rash, stomach ache, headache, or routine checkups; for low fever or cold, schedule an outpatient appointment with Dr. Priya Patel in Pediatrics/Primary Care instead.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "symptoms": {
                    "type": "STRING",
                    "description": "Description of acute emergency symptoms reported by patient."
                },
                "severity": {
                    "type": "STRING",
                    "description": "Severity level: 'EMERGENCY' or 'URGENT'."
                },
                "patient_name": {
                    "type": "STRING",
                    "description": "Patient name if known."
                },
                "patient_phone": {
                    "type": "STRING",
                    "description": "Patient phone if known."
                }
            },
            "required": ["symptoms", "severity"]
        }
    }
]
