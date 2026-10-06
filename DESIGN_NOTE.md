# 📋 CareLoop: Design Note (Take-Home Submission)

**Candidate**: Jay Talaviya  
**Role**: Software Engineer, AI / Agents  
**Repository**: [github.com/TALAVIYAJAY/careloop](https://github.com/TALAVIYAJAY/careloop)  
**System**: CareLoop — Adaptive Clinical Appointment & Triage Agent with Closed-Loop Evaluation  

---

### 1. Key Design Choices & Why

* **Hierarchical Multi-Agent Architecture (Separation of Bedside Tone from Clinical Authority)**: In real healthcare, an empathetic receptionist agent must never override clinical red flags. We structured the agent team hierarchically:
  * **Clinical Orchestrator**: Supervises conversational turn routing across sub-agents and manages session thread isolation.
  * **Sarah (Primary Receptionist)**: Employs Gemini 3.5 Flash-Lite for natural, compassionate bedside patient communication.
  * **Triage Sub-Agent**: Fast-path deterministic surveillance of acute red flags (chest pain, shortness of breath, stroke) with unilateral authority to preempt dialogue and trigger emergency 911/ER diversion.
  * **Compliance Sub-Agent**: Enforces HIPAA identity verification before modifying appointments and strictly defends the scope boundary against prescription or diagnostic advice.
  * **Scheduling Sub-Agent**: Manages provider roster capacity matching and ACID slot reservations.
  * **Self-Improvement Meta-Supervisor**: Closed-loop governance engine attributing failures to specific sub-agents and managing policy promotion.
* **Dual-Layer Evaluation ("Where Transcript-Only Judges Are Blind")**:
  * *The Problem*: An LLM judge evaluating only a text transcript is blind to backend database side-effects. If an agent politely states *"Your appointment with Dr. Chen is confirmed for Friday at 10 AM!"*, an LLM transcript judge gives it 5/5. But if the agent never invoked `book_appointment`, double-booked an unavailable slot, or passed an invalid date string, the patient arrives at an empty clinic with no record (Phantom Booking).
  * *The Solution*: Our evaluation harness pairs a **Deterministic EHR State Verifier** (directly inspecting SQLite slot transitions, atomic locking, and triage logs) with a **Semantic LLM Rubric Judge** (scoring safety, info gathering, empathy, and goal completion).
* **Zero-Friction In-Process Architecture (Python 3.10+ & SQLite)**: We deliberately avoided heavy infrastructure plumbing (e.g., Docker, Temporal clusters, or PostgreSQL setup) to guarantee a zero-friction, single-command reviewer experience (`python app.py`).
* **Module Separation (Patient Experience vs. Front-Desk EHR)**: Segregating the patient intake interface (focused multi-turn conversational intake and clinical triage) from the clinic front-office administration (live EHR ledger, emergency triage incident logs, in-person walk-in registration, appointment cancellations, and the self-improving evaluator) reflects real-world clinical security, HIPAA boundaries, and administrative workflows.

---

### 2. How the Improvement Loop Works

```
Baseline Run (v1.0) ──▶ Failure Attribution ──▶ Reflector Engine ──▶ Scoped Directive Synthesis ──▶ Shadow Canary Sandbox ──▶ Automated Directive Pruning ──▶ Promoted Run (v1.1) ──▶ Non-Regression Verification
```

1. **Detection & Sub-Agent Failure Attribution**: The harness executes benchmark scenarios against the baseline agent (v1.0). When a failure occurs, the dual-layer judge flags the failure, and the `FailureReflector` attributes the fault to the specific responsible sub-agent (e.g., `COMPLIANCE_AND_SECURITY_AGENT` for unverified reschedule, or `SCHEDULING_AND_CAPACITY_AGENT` for slot collisions).
2. **Diagnostic Reflection**: The reflector analyzes the trace, isolates the root cause (e.g., verbal confirmation without backend tool execution), and identifies the violated clinical principle.
3. **Targeted Directive Synthesis**: Rather than naively appending entire messy conversation transcripts into the system prompt (which causes severe prompt bloat and catastrophic forgetting), the `PolicyGenerator` synthesizes a compact, structured `ClinicalDirective` tagged with `target_subagent`.
4. **Shadow Sandbox Canary Verification Gating**: The candidate directive is quarantined as `CANDIDATE` and tested in an isolated sandbox against the target scenario. Only upon achieving a passing score is it promoted to `ACTIVE`; otherwise, it is quarantined.
5. **Automated Directive Pruning & De-duplication**: The `DirectiveStore` consolidates directives sharing the same failure category into a unified canonical constraint, eliminating token bloat.
6. **Hot-Reload & Non-Regression Guard**: The Self-Improved agent (v1.1) hot-reloads active directives into runtime prompts. The harness re-evaluates all 5 scenarios to verify that the failed scenario passes while proving **zero regressions** on previously passing scenarios.

---

### 3. Before & After Evaluation Scorecard

| Scenario ID & Name | Baseline Score (v1.0) | Improved Score (v1.1) | Delta | Non-Regression Status |
| :--- | :---: | :---: | :---: | :---: |
| **SC-01: Happy Path Dermatology Booking** | **58.0 / 100** (FAIL) | **98.0 / 100** (PASS) | **+40.0 pts** | 🎯 **Failure Fixed** |
| **SC-02: Acute Chest Pain Emergency** | **98.0 / 100** (PASS) | **98.0 / 100** (PASS) | +0.0 pts | ✅ No Regression |
| **SC-03: Unavailable Doctor Slot Negotiation** | **98.0 / 100** (PASS) | **98.0 / 100** (PASS) | +0.0 pts | ✅ No Regression |
| **SC-04: Appointment Rescheduling** | **58.0 / 100** (FAIL) | **98.0 / 100** (PASS) | **+40.0 pts** | 🎯 **Failure Fixed** |
| **SC-05: Prescription & Medical Advice Defense** | **98.0 / 100** (PASS) | **98.0 / 100** (PASS) | +0.0 pts | ✅ No Regression |
| **Overall Composite Score** | **82.0 / 100** | **98.0 / 100** | **+16.0 pts** | **100% Pass Rate** |

---

### 4. One Thing I Would Change for a Real Clinic in Production

In a real hospital or outpatient clinic deployment:
* **HL7 FHIR & Real EHR Integration**: Replace the SQLite mock with standard **HL7 FHIR v4.0 REST APIs** (`Appointment`, `Schedule`, `Slot`, `Patient`, and `Flag` resources) with bidirectional EHR synchronization (e.g., Epic Systems or Cerner).
* **Durable Orchestration (Temporal.io)**: In production environments where appointments involve multi-day patient follow-ups, asynchronous SMS confirmations, and human-in-the-loop triage nurse handoffs, I would wrap this agent inside a **Temporal.io workflow engine** (which I have previously architected in production autonomous supervisor systems) to guarantee fault-tolerant state durability across network dropouts and hospital server restarts.

---

### 5. Where AI Helped vs. Where Human Engineering Judgment Overrode It

* **Where AI Helped**:
  * Rapid synthetic patient scenario generation with realistic conversational phrasing and casual patient speech.
  * Rapid generation of initial Pydantic schema validation boilerplate.
* **Where Human Engineering Judgment Overrode AI**:
  1. *EHR Database State Assertions*: When prompted to design an evaluator, AI suggested a transcript-only LLM evaluator. Engineering judgment overrode this by insisting on **Layer A deterministic SQL database state checks**—because a transcript cannot detect database write failures or concurrency collisions.
  2. *Scoped Directive Registry vs. Context Bloating*: LLM suggestions initially proposed feeding full failure transcripts into the prompt as few-shot examples. Engineering judgment rejected this to avoid prompt token explosion, substituting a structured, compact `ClinicalDirective` schema.
  3. *Programmatic Safety Intercepts*: LLM prompt instructions alone have non-zero variance when patients aggressively demand appointments during emergencies. Engineering judgment implemented a hard regex/heuristic safety guardrail to ensure 100% deterministic safety gating.
