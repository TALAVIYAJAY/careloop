import logging
from typing import Dict, Any, List, Optional, Tuple
from pydantic import BaseModel, Field

from clinic_db.database import ClinicDatabase
from .state import PatientSession
from .tools import ClinicToolDispatcher
from .guardrails import evaluate_clinical_guardrails, GuardrailCheckResult

logger = logging.getLogger("careloop.subagents")


class SubAgentExecutionResult(BaseModel):
    handled: bool = False
    preempted: bool = False
    agent_name: str
    action_type: str = "PASS_THROUGH"
    response_text: Optional[str] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None
    tool_responses: Optional[List[Dict[str, Any]]] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class TriageSubAgent:
    """
    Sub-Agent: Clinical Triage & Red-Flag Surveillance.
    Mandate: Continuous clinical surveillance for acute cardiovascular, respiratory,
             or neurological emergencies. Has hard preemption authority to divert to 911/ER.
    """
    name = "Triage & Red-Flag Sub-Agent"
    role_key = "TRIAGE_AND_RED_FLAG_AGENT"

    def __init__(self, tool_dispatcher: ClinicToolDispatcher):
        self.tool_dispatcher = tool_dispatcher

    def evaluate_and_intercept(
        self,
        session: PatientSession,
        user_input: str,
        guardrail_result: Optional[GuardrailCheckResult] = None
    ) -> SubAgentExecutionResult:
        gr = guardrail_result or evaluate_clinical_guardrails(user_input)

        if gr.triggered and gr.category == "EMERGENCY_RED_FLAG":
            # Hard emergency preemption
            triage_res = self.tool_dispatcher.trigger_emergency_escalation(
                symptoms=gr.reason,
                severity="EMERGENCY",
                patient_name=session.patient_name,
                patient_phone=session.patient_phone
            )
            session.emergency_flag = True
            session.booking_status = "ESCALATED"

            msg = (
                "⚠️ **URGENT CLINICAL ALERT: IMMEDIATE EMERGENCY CARE REQUIRED**\n\n"
                f"Based on the critical symptoms described (*{gr.reason}*), this presentation requires "
                "immediate emergency medical attention. Outpatient clinic visits cannot manage acute emergencies.\n\n"
                "• **Action Required:** Please hang up and call **911** or proceed directly to your nearest **Emergency Department** immediately.\n"
                "• **Clinic Notice:** Our on-duty clinical triage team has been alerted of this event."
            )

            tc = [{"name": "trigger_emergency_escalation", "args": {"symptoms": gr.reason, "severity": "EMERGENCY"}}]
            tr = [{"name": "trigger_emergency_escalation", "output": triage_res}]

            session.add_message(
                role="model",
                content=msg,
                tool_calls=tc,
                tool_responses=tr
            )

            return SubAgentExecutionResult(
                handled=True,
                preempted=True,
                agent_name=self.name,
                action_type="EMERGENCY_PREEMPTION",
                response_text=msg,
                tool_calls=tc,
                tool_responses=tr,
                metadata={"reason": gr.reason, "triage_id": triage_res.get("triage_event", {}).get("id")}
            )

        # If current turn is not an emergency, clear the emergency flag and resume routine intake
        session.emergency_flag = False
        if session.booking_status == "ESCALATED":
            session.booking_status = "INTAKE"

        return SubAgentExecutionResult(
            handled=False,
            agent_name=self.name,
            action_type="NORMAL_OBSERVATION"
        )


class ComplianceSubAgent:
    """
    Sub-Agent: HIPAA Security Compliance & Medical Scope Defense.
    Mandate: Enforces identity verification before appointment changes and defends
             clinical scope by refusing medication dosages and diagnostic prescriptions.
    """
    name = "Compliance & Security Sub-Agent"
    role_key = "COMPLIANCE_AND_SECURITY_AGENT"

    def __init__(self, tool_dispatcher: ClinicToolDispatcher):
        self.tool_dispatcher = tool_dispatcher

    def evaluate_scope_defense(
        self,
        session: PatientSession,
        user_input: str,
        guardrail_result: Optional[GuardrailCheckResult] = None
    ) -> SubAgentExecutionResult:
        gr = guardrail_result or evaluate_clinical_guardrails(user_input)

        if gr.triggered and gr.category == "MEDICAL_ADVICE_REFUSAL":
            msg = (
                "I am an administrative scheduling coordinator for CareLoop Clinic, so I cannot diagnose medical conditions "
                "or prescribe medication dosages. I would be happy to schedule an appointment with one of our licensed physicians "
                "who can conduct a formal examination and prescribe appropriate treatments. Would you like me to find an available consultation opening?"
            )
            session.add_message(role="model", content=msg)
            return SubAgentExecutionResult(
                handled=True,
                preempted=False,
                agent_name=self.name,
                action_type="SCOPE_DEFENSE_REFUSAL",
                response_text=msg,
                metadata={"reason": gr.reason}
            )

        return SubAgentExecutionResult(
            handled=False,
            agent_name=self.name,
            action_type="COMPLIANT"
        )

    def verify_reschedule_credentials(
        self,
        session: PatientSession,
        appointment_id: str,
        provided_name: Optional[str] = None,
        provided_phone: Optional[str] = None
    ) -> Tuple[bool, str]:
        """Validates that caller credentials match the EHR appointment before allowing changes."""
        appt = self.tool_dispatcher.db.get_appointment(appointment_id)
        if not appt:
            return False, f"Appointment ID '{appointment_id}' was not found in our records."

        caller_name = (provided_name or session.patient_name or "").strip().lower()
        caller_phone = (provided_phone or session.patient_phone or "").strip()

        # If name or phone matches recorded appointment
        appt_name = appt.patient_name.strip().lower()
        appt_phone = appt.patient_phone.strip()

        if caller_name and (caller_name in appt_name or appt_name in caller_name):
            return True, "Identity verified by patient name."

        clean_caller_digits = "".join(filter(str.isdigit, caller_phone))
        clean_appt_digits = "".join(filter(str.isdigit, appt_phone))
        if clean_caller_digits and clean_appt_digits and (clean_caller_digits in clean_appt_digits or clean_appt_digits in clean_caller_digits):
            return True, "Identity verified by contact phone."

        return False, f"Security verification failed: Caller identity does not match patient records for {appointment_id}."


class SchedulingSubAgent:
    """
    Sub-Agent: EHR Capacity & Provider Scheduling.
    Mandate: Provider rosters, capacity matching, tokenized physician lookup, atomic slot reservation,
             and Master Patient Index (MPI) linking.
    """
    name = "EHR Scheduling & Capacity Sub-Agent"
    role_key = "EHR_SCHEDULING_AGENT"

    def __init__(self, tool_dispatcher: ClinicToolDispatcher):
        self.tool_dispatcher = tool_dispatcher

    def search_slots(self, specialty: Optional[str] = None, doctor_name: Optional[str] = None, date_str: Optional[str] = None) -> Dict[str, Any]:
        return self.tool_dispatcher.search_available_slots(specialty=specialty, doctor_name=doctor_name, date_str=date_str)

    def book_slot(self, patient_name: str, patient_phone: str, doctor_id: str, slot_iso: str, reason: str, session_id: Optional[str] = None, patient_id: Optional[str] = None) -> Dict[str, Any]:
        return self.tool_dispatcher.book_appointment(
            patient_name=patient_name,
            patient_phone=patient_phone,
            doctor_id=doctor_id,
            slot_iso=slot_iso,
            reason=reason,
            session_id=session_id,
            patient_id=patient_id
        )

    def reschedule_slot(self, appointment_id: str, new_slot_iso: str, patient_name: Optional[str] = None, patient_phone: Optional[str] = None, session_id: Optional[str] = None, doctor_id: Optional[str] = None) -> Dict[str, Any]:
        return self.tool_dispatcher.reschedule_appointment(
            appointment_id=appointment_id,
            new_slot_iso=new_slot_iso,
            patient_name=patient_name,
            patient_phone=patient_phone,
            session_id=session_id,
            doctor_id=doctor_id
        )
