import logging
from typing import Dict, Any, List, Optional
from pydantic import BaseModel

from clinic_db.database import ClinicDatabase
from .state import PatientSession
from .tools import ClinicToolDispatcher
from .subagents import TriageSubAgent, ComplianceSubAgent, SchedulingSubAgent, SubAgentExecutionResult

logger = logging.getLogger("careloop.orchestrator")


class AgentManifestItem(BaseModel):
    id: str
    name: str
    role: str
    level: str  # ORCHESTRATOR | PRIMARY | SUBAGENT | META
    mandate: str
    authority_scope: str
    status: str = "ONLINE"


class ClinicalOrchestrator:
    """
    Hierarchical Clinical Agent Orchestrator.
    Directs patient dialogues between the Main Receptionist Agent (Sarah) and specialized
    clinical sub-agents (Triage Surveillance, Compliance Gate, and EHR Capacity).
    Enforces clinical preemption, identity verification, and multi-thread session isolation.
    """

    def __init__(
        self,
        db: Optional[ClinicDatabase] = None,
        model_name: Optional[str] = None,
        api_key: Optional[str] = None,
        dynamic_directives: Optional[List[str]] = None
    ):
        self.db = db or ClinicDatabase()
        self.tool_dispatcher = ClinicToolDispatcher(db=self.db)
        self.dynamic_directives = dynamic_directives or []

        # Initialize specialized clinical frontline sub-agents
        self.triage_subagent = TriageSubAgent(tool_dispatcher=self.tool_dispatcher)
        self.compliance_subagent = ComplianceSubAgent(tool_dispatcher=self.tool_dispatcher)
        self.scheduling_subagent = SchedulingSubAgent(tool_dispatcher=self.tool_dispatcher)

        # Primary Conversational Receptionist Agent (Sarah)
        from .clinic_agent import ClinicAgent
        self.receptionist_agent = ClinicAgent(
            db=self.db,
            model_name=model_name,
            api_key=api_key,
            dynamic_directives=self.dynamic_directives
        )

    def update_directives(self, directives: List[str]) -> None:
        """Propagates updated clinical directives down to frontline agents."""
        self.dynamic_directives = directives
        self.receptionist_agent.update_directives(directives)

    def process_turn(self, session: PatientSession, user_input: str) -> str:
        """
        Executes hierarchical turn routing:
        1. Triage Surveillance: Detects acute emergencies with hard preemption power.
        2. Compliance Gate: Verifies clinical scope and patient identity boundaries.
        3. Primary Receptionist: Executes conversational reasoning, slot proposals, and booking.
        """
        # Step 1: Surveillance & Safety Preemption Check
        triage_result = self.triage_subagent.evaluate_and_intercept(session, user_input)
        if triage_result.preempted and triage_result.response_text:
            logger.info(f"Turn preempted by {self.triage_subagent.name}: {triage_result.metadata.get('reason')}")
            return triage_result.response_text

        # Step 2: Scope Defense & Medical Advice Refusal Check
        compliance_result = self.compliance_subagent.evaluate_scope_defense(session, user_input)
        if compliance_result.handled and compliance_result.response_text:
            logger.info(f"Turn handled by {self.compliance_subagent.name}: Clinical scope refusal.")
            return compliance_result.response_text

        # Step 3: Operational Core Execution via Primary Receptionist (Sarah) & Scheduling Sub-Agent
        return self.receptionist_agent.handle_turn(session, user_input)

    def get_agent_manifest(self) -> List[AgentManifestItem]:
        """Returns the full hierarchical agent taxonomy for the front-desk EHR UI."""
        return [
            AgentManifestItem(
                id="orch_01",
                name="Clinical Agent Orchestrator",
                role="Session & Pipeline Supervisor",
                level="ORCHESTRATOR",
                mandate="Coordinates conversation routing, thread state management, and trace logging for self-improvement.",
                authority_scope="Full Pipeline Routing & Session Isolation",
                status="ONLINE"
            ),
            AgentManifestItem(
                id="rec_sarah_01",
                name="Sarah (AI Medical Receptionist)",
                role="Primary Patient-Facing Agent",
                level="PRIMARY",
                mandate="Empathetic patient communication, symptom elicitation, slot presentation, and arrival guidance.",
                authority_scope="Patient Dialogue Synthesis (Non-Prescriptive)",
                status="ONLINE"
            ),
            AgentManifestItem(
                id="sub_triage_01",
                name="Triage & Red-Flag Sub-Agent",
                role="Clinical Safety Surveillance",
                level="SUBAGENT",
                mandate="Surveillance for acute chest pain, dyspnea, and stroke indicators. Preempts routine booking to 911/ER.",
                authority_scope="Hard Emergency Preemption & Triage Escalation",
                status="ONLINE"
            ),
            AgentManifestItem(
                id="sub_sched_01",
                name="EHR Scheduling & Capacity Sub-Agent",
                role="Clinic Capacity & Resource Manager",
                level="SUBAGENT",
                mandate="Provider roster negotiation, tokenized physician matching, atomic slot reservation, and MPI record linking.",
                authority_scope="ACID Slot Mutations & Calendar Locks",
                status="ONLINE"
            ),
            AgentManifestItem(
                id="sub_comp_01",
                name="Compliance & Security Sub-Agent",
                role="HIPAA Security & Scope Defense",
                level="SUBAGENT",
                mandate="Identity credential matching before reschedules/cancellations and strict refusal of medication advice.",
                authority_scope="HIPAA Verification & Clinical Boundary Gate",
                status="ONLINE"
            ),
            AgentManifestItem(
                id="meta_sup_01",
                name="Self-Improvement Meta-Supervisor",
                role="Autonomous Quality & Governance",
                level="META",
                mandate="Post-run failure attribution, sub-agent directive synthesis, shadow canary gating, and non-regression verification.",
                authority_scope="Directive Policy Generation & Canary Promotion",
                status="ONLINE"
            )
        ]
