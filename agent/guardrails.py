import re
from typing import Optional, Dict, Any, List

# Clinical Red-Flag Emergency Keywords (Acute life-threatening presentations)
EMERGENCY_PATTERNS = [
    # Cardiovascular
    r"\b(chest pain|chest tightness|chest pressure|heart attack|crushing chest)\b",
    r"\b(left arm pain|left arm numbness|radiating to (jaw|neck|arm))\b",
    # Respiratory
    r"\b(can'?t breathe|severe shortness of breath|gasping for air|struggling to breathe)\b",
    r"\b(choking|blue lips|throat closing)\b",
    # Neurological / Stroke (FAST)
    r"\b(facial droop|slurred speech|sudden numbness|sudden weakness|cannot move arm)\b",
    r"\b(worst headache of (my )?life|thunderclap headache)\b",
    # Trauma & Anaphylaxis
    r"\b(unconscious|passed out|fainted and won'?t wake up)\b",
    r"\b(severe allergic reaction|anaphylaxis|swollen tongue)\b",
    r"\b(heavy bleeding|coughing up blood|vomiting blood)\b",
]

# Medical Advice / Prescription Probing Keywords
MEDICAL_ADVICE_PATTERNS = [
    r"\b(what (dose|dosage)|how much|how many)\b.*\b(amoxicillin|antibiotics?|ibuprofen|steroids?|prednisone|tylenol|aspirin|paracetamol|medicine|medication|pills?|tablets?|mg|milligrams)\b",
    r"\b(should|can)\s+(i|we)\s+(take|give|use|administer)\b.*\b(amoxicillin|antibiotics?|ibuprofen|steroids?|prednisone|tylenol|aspirin|paracetamol|medicine|medication)\b",
    r"\b(what (dose|dosage)|how much (mg|milligrams|pills|tablets))\b",
    r"\b(should i take|can i take|how much should i give|how much to give)\b",
    r"\b(diagnose me|do i have cancer|what disease do i have|is this contagious)\b",
    r"\b(can you prescribe|write me a prescription|prescribe me|give me a prescription)\b",
]


class GuardrailCheckResult:
    def __init__(self, triggered: bool, category: str, reason: str, recommended_action: str):
        self.triggered = triggered
        self.category = category  # "NONE" | "EMERGENCY_RED_FLAG" | "MEDICAL_ADVICE_REFUSAL"
        self.reason = reason
        self.recommended_action = recommended_action

    def to_dict(self) -> Dict[str, Any]:
        return {
            "triggered": self.triggered,
            "category": self.category,
            "reason": self.reason,
            "recommended_action": self.recommended_action
        }


def evaluate_clinical_guardrails(user_input: str) -> GuardrailCheckResult:
    """
    Evaluates patient input against critical clinical safety rules.
    Prioritizes emergency detection before any scheduling workflows.
    """
    cleaned_text = user_input.lower().strip()

    # 1. Emergency Red Flags Check
    for pattern in EMERGENCY_PATTERNS:
        match = re.search(pattern, cleaned_text)
        if match:
            matched_symptom = match.group(0)
            return GuardrailCheckResult(
                triggered=True,
                category="EMERGENCY_RED_FLAG",
                reason=f"Detected high-acuity emergency presentation: '{matched_symptom}'",
                recommended_action="IMMEDIATE_EMERGENCY_DIVERSION: Halt routine booking, trigger emergency escalation tool, and redirect patient to call 911 or visit the nearest Emergency Department immediately."
            )

    # 2. Medical Advice / Prescription Check
    for pattern in MEDICAL_ADVICE_PATTERNS:
        match = re.search(pattern, cleaned_text)
        if match:
            return GuardrailCheckResult(
                triggered=True,
                category="MEDICAL_ADVICE_REFUSAL",
                reason="Patient is requesting direct medical diagnosis, dosage, or prescription.",
                recommended_action="REFUSE_AND_OFFER_CONSULT: State that as an administrative scheduling assistant you cannot prescribe medications or provide diagnoses; offer to schedule an appointment with a licensed doctor."
            )

    return GuardrailCheckResult(
        triggered=False,
        category="NONE",
        reason="No immediate safety guardrail triggered.",
        recommended_action="PROCEED_NORMAL_FLOW"
    )
