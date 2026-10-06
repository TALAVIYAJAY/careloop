import json
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class ClinicalDirective(BaseModel):
    id: str
    trigger_condition: str
    directive_text: str
    category: str
    target_subagent: str = "TRIAGE_AND_RED_FLAG_AGENT"
    status: str = "ACTIVE"  # ACTIVE | CANDIDATE | QUARANTINED
    canary_verification_score: Optional[float] = None
    shadow_verification_notes: Optional[str] = None
    created_at_iso: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class DirectiveStore:
    """
    Registry for dynamic clinical directives learned from evaluation failures.
    Maintains clean, compact policies injected into the agent system prompt.
    Includes automated consolidation and canary verification gating.
    """

    def __init__(self, persistence_file: Optional[str] = None):
        self.persistence_file = persistence_file
        self.directives: List[ClinicalDirective] = []
        if persistence_file:
            self._load()

    def add_directive(self, directive: ClinicalDirective) -> None:
        # Prevent exact duplicate directives
        for i, d in enumerate(self.directives):
            if d.id == directive.id or d.directive_text.strip() == directive.directive_text.strip():
                self.directives[i] = directive
                if self.persistence_file:
                    self._save()
                return
        self.directives.append(directive)
        if self.persistence_file:
            self._save()

    def list_directives(self) -> List[ClinicalDirective]:
        return list(self.directives)

    def get_active_directives(self) -> List[ClinicalDirective]:
        return [d for d in self.directives if d.status == "ACTIVE"]

    def get_prompt_strings(self) -> List[str]:
        # Only inject ACTIVE promoted directives into agent prompts
        active = self.get_active_directives()
        return [f"[{d.id} - {d.target_subagent}] {d.directive_text}" for d in active]

    def update_directive_status(
        self,
        directive_id: str,
        status: str,
        canary_score: Optional[float] = None,
        notes: Optional[str] = None
    ) -> None:
        for d in self.directives:
            if d.id == directive_id:
                d.status = status
                if canary_score is not None:
                    d.canary_verification_score = canary_score
                if notes is not None:
                    d.shadow_verification_notes = notes
                break
        if self.persistence_file:
            self._save()

    def consolidate_directives(self) -> List[ClinicalDirective]:
        """
        Automated Directive Pruning & De-duplication:
        Merges redundant rules targeting the same sub-agent to eliminate prompt bloat.
        """
        consolidated = []
        seen_keys = set()
        for d in self.directives:
            key = (d.target_subagent, d.category)
            if key not in seen_keys:
                seen_keys.add(key)
                consolidated.append(d)
        self.directives = consolidated
        if self.persistence_file:
            self._save()
        return self.directives

    def clear(self) -> None:
        self.directives = []
        if self.persistence_file:
            self._save()

    def _save(self) -> None:
        if self.persistence_file:
            with open(self.persistence_file, "w", encoding="utf-8") as f:
                json.dump([d.model_dump() for d in self.directives], f, indent=2)

    def _load(self) -> None:
        if self.persistence_file:
            try:
                with open(self.persistence_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.directives = [ClinicalDirective(**d) for d in data]
            except (FileNotFoundError, json.JSONDecodeError):
                self.directives = []
