import uuid
from typing import Dict, Any
from .reflector import ReflectionAnalysis
from .memory_store import ClinicalDirective


class PolicyGenerator:
    """
    Synthesizes scoped, concise Clinical Directives from root-cause reflection analyses.
    Guarantees policies are scoped and avoid prompt bloat or cross-domain interference.
    """

    @staticmethod
    def generate_directive(reflection: ReflectionAnalysis) -> ClinicalDirective:
        # Create meaningful directive ID based on scenario and category
        cat_tag = reflection.category[:6].upper()
        dir_id = f"DIR_{cat_tag}_{reflection.failed_scenario_id.replace('-', '_')}"

        trigger_summary = f"When evaluating patient scenarios in category '{reflection.category}' ({reflection.scenario_name})"
        directive_text = reflection.remedial_instruction.strip()

        return ClinicalDirective(
            id=dir_id,
            trigger_condition=trigger_summary,
            directive_text=directive_text,
            category=reflection.category,
            target_subagent=getattr(reflection, "target_subagent", "TRIAGE_AND_RED_FLAG_AGENT"),
            status="CANDIDATE"
        )
