#!/usr/bin/env python3
"""
CareLoop Master Clinical Agent & Self-Improvement Studio
Single-command web application hosting the complete clinical agent,
closed-loop evaluation harness, and live EHR state inspector.
"""

import sys
import os
import webbrowser
import threading
from typing import Dict, Any, List, Optional
from pathlib import Path

# Ensure UTF-8 console output on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import uvicorn
from rich.console import Console
from rich.panel import Panel

from clinic_db.database import ClinicDatabase
from agent.clinic_agent import ClinicAgent
from agent.orchestrator import ClinicalOrchestrator
from agent.state import PatientSession
from improvement.memory_store import DirectiveStore
from improvement.self_improver import SelfImprovementCoordinator
import json

console = Console()

app = FastAPI(
    title="CareLoop Clinical Agent Studio",
    description="Autonomous clinical appointment scheduling agent with closed-loop evaluation",
    version="1.1.0"
)

# Persistent database and directive store
db = ClinicDatabase(db_path="clinic.db")
store = DirectiveStore(persistence_file="clinical_directives.json")
agent = ClinicAgent(db=db, dynamic_directives=store.get_prompt_strings())
orchestrator = ClinicalOrchestrator(db=db, dynamic_directives=store.get_prompt_strings())
coordinator = SelfImprovementCoordinator(db=db, store=store)

# In-memory active patient sessions: session_id -> PatientSession
sessions: Dict[str, PatientSession] = {}

from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

FRONTEND_OUT = Path(__file__).parent / "frontend" / "out"
if (FRONTEND_OUT / "_next").exists():
    app.mount("/_next", StaticFiles(directory=str(FRONTEND_OUT / "_next")), name="next_assets")


class ChatMessageRequest(BaseModel):
    session_id: str
    message: str
    patient_name: Optional[str] = "Jay Talaviya"
    patient_phone: Optional[str] = "+1-555-0199"
    patient_id: Optional[str] = "PAT_JAY_001"
    slot_iso: Optional[str] = None
    doctor_id: Optional[str] = None
    doctor_name: Optional[str] = None


class SessionResetRequest(BaseModel):
    session_id: str
    patient_name: Optional[str] = "Jay Talaviya"
    patient_phone: Optional[str] = "+1-555-0199"
    patient_id: Optional[str] = "PAT_JAY_001"


# =====================================================================
# WEB UI ROOT
# =====================================================================
@app.get("/")
async def serve_index():
    next_index = FRONTEND_OUT / "index.html"
    if next_index.exists():
        return FileResponse(next_index)
    raise HTTPException(status_code=404, detail="Frontend build not found. Run 'npm run build' inside frontend/")


# =====================================================================
# SYSTEM STATUS API
# =====================================================================
@app.get("/api/status")
async def get_system_status():
    doctors = db.list_doctors()
    appointments = db.get_all_appointments()
    directives = store.list_directives()
    return {
        "status": "healthy",
        "model": "gemini-3.5-flash-lite",
        "active_directives_count": len(directives),
        "doctors_count": len(doctors),
        "appointments_count": len(appointments),
    }


@app.get("/api/agents")
async def get_agent_hierarchy():
    """Returns the complete Hierarchical Multi-Agent manifest and active statuses."""
    return [a.model_dump() for a in orchestrator.get_agent_manifest()]


# =====================================================================
# AGENT CHAT API
# =====================================================================
@app.post("/api/chat")
async def chat_with_agent(req: ChatMessageRequest):
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    session = sessions.get(req.session_id)
    if not session:
        session = PatientSession(
            session_id=req.session_id,
            patient_name=req.patient_name or "Jay Talaviya",
            patient_phone=req.patient_phone or "+1-555-0199",
            patient_id=req.patient_id or "PAT_JAY_001"
        )
        sessions[req.session_id] = session
    else:
        if not session.patient_name:
            session.patient_name = req.patient_name or "Jay Talaviya"
        if not session.patient_phone:
            session.patient_phone = req.patient_phone or "+1-555-0199"
        if not session.patient_id:
            session.patient_id = req.patient_id or "PAT_JAY_001"

    # Propagate explicit slot/doctor selections if specified
    if req.slot_iso:
        session.selected_slot_iso = req.slot_iso
    if req.doctor_id:
        session.selected_doctor_id = req.doctor_id
    if req.doctor_name:
        session.selected_doctor_name = req.doctor_name

    # Synchronize active appointments with true database state before turn
    if session.patient_id:
        db_appts = db.get_patient_appointments(session.patient_id)
        session.active_appointments = [a.model_dump() for a in db_appts]
        if db_appts and not session.appointment_id:
            session.appointment_id = db_appts[-1].id

    # Keep orchestrator and agent synced with current clinical directives
    active_directives = store.get_prompt_strings()
    orchestrator.update_directives(active_directives)
    agent.update_directives(active_directives)

    # Auto-extract patient name from message if provided
    for known_caller in ["Alex Rivera", "Jay Talaviya", "Jay", "Alex Turner", "Maria Garcia", "Robert Hayes", "David Miller", "Elena Rostova", "Emma Davis"]:
        if known_caller.lower() in req.message.lower():
            session.patient_name = known_caller
            break

    # Execute conversational turn through Hierarchical Clinical Orchestrator
    response_text = orchestrator.process_turn(session, req.message)

    # Collect tool calls executed during this turn
    recent_tools = []
    if session.messages:
        last_turn = session.messages[-1]
        tool_responses_map = {}
        if last_turn.tool_responses:
            for resp in last_turn.tool_responses:
                if isinstance(resp, dict):
                    tool_responses_map[resp.get("name")] = resp.get("output")

        if last_turn.tool_calls:
            for call in last_turn.tool_calls:
                call_name = call.get("name") if isinstance(call, dict) else getattr(call, "name", str(call))
                call_args = call.get("args") if isinstance(call, dict) else getattr(call, "arguments", {})
                call_res = tool_responses_map.get(call_name) or (call.get("output") if isinstance(call, dict) else getattr(call, "result", None))
                recent_tools.append({
                    "tool_name": call_name,
                    "arguments": call_args,
                    "result": call_res
                })

    # Synchronize active appointments with true database state after tool execution
    if session.patient_id:
        db_appts = db.get_patient_appointments(session.patient_id)
        session.active_appointments = [a.model_dump() for a in db_appts]
        if db_appts:
            session.appointment_id = db_appts[-1].id
            session.selected_slot_iso = db_appts[-1].slot_iso
            session.selected_doctor_name = db_appts[-1].doctor_name

    triage_str = "EMERGENCY_ESCALATED" if session.emergency_flag else (
        "CONFIRMED" if session.booking_status == "CONFIRMED" else "ROUTINE"
    )

    return {
        "response": response_text,
        "session": {
            "patient_name": session.patient_name or "Jay Talaviya",
            "patient_phone": session.patient_phone or "+1-555-0199",
            "patient_id": session.patient_id or "PAT_JAY_001",
            "active_doctor_name": session.selected_doctor_name or "None Selected",
            "selected_slot": session.selected_slot_iso or "None",
            "appointment_id": session.appointment_id or "",
            "active_appointments": session.active_appointments,
            "stage": session.booking_status or "INTAKE",
            "triage_level": triage_str,
            "emergency_triggered": session.emergency_flag
        },
        "recent_tool_calls": recent_tools,
        "emergency_triggered": session.emergency_flag
    }


@app.post("/api/chat/reset")
async def reset_chat_session(req: SessionResetRequest):
    sessions[req.session_id] = PatientSession(
        session_id=req.session_id,
        patient_name=req.patient_name or "Jay Talaviya",
        patient_phone=req.patient_phone or "+1-555-0199",
        patient_id=req.patient_id or "PAT_JAY_001"
    )
    return {"status": "ok", "session_id": req.session_id}


# =====================================================================
# SELF-IMPROVEMENT & EVALUATION API
# =====================================================================
_cached_evaluation_result = None


@app.post("/api/evaluation/run")
async def run_evaluation_loop():
    """
    Executes the closed evaluation loop:
    1. Baseline Agent evaluation across 5 clinical scenarios.
    2. Failure reflection & root-cause diagnosis.
    3. Scoped Clinical Directive synthesis.
    4. Self-Improved Agent re-evaluation proving score gain and 0 regressions.
    """
    global _cached_evaluation_result
    try:
        if _cached_evaluation_result is None:
            _cached_evaluation_result = coordinator.run_cycle()
        # Synchronize live agent with the newly generated directives
        agent.update_directives(store.get_prompt_strings())
        return _cached_evaluation_result.model_dump()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Evaluation failed: {str(e)}")


@app.get("/api/directives")
async def get_directives():
    return [d.model_dump() for d in store.list_directives()]


@app.post("/api/directives/clear")
async def clear_directives():
    store.clear()
    agent.update_directives([])
    orchestrator.update_directives([])
    return {"status": "ok", "message": "Clinical directives cleared"}


@app.post("/api/evolution/simulate")
async def simulate_edge_case_evolution():
    """Triggers an interactive clinical edge-case simulation with shadow canary verification."""
    global _cached_evaluation_result
    cycle_result = coordinator.run_cycle()
    _cached_evaluation_result = cycle_result
    active_prompt_strings = store.get_prompt_strings()
    orchestrator.update_directives(active_prompt_strings)
    agent.update_directives(active_prompt_strings)
    return {
        "status": "SUCCESS",
        "scenario_tested": "SC-04",
        "baseline_score": cycle_result.baseline_summary.composite_score,
        "improved_score": cycle_result.improved_summary.composite_score,
        "score_delta": cycle_result.score_delta,
        "regressions_detected": cycle_result.regressions_detected,
        "active_directives": [d.model_dump() for d in store.get_active_directives()],
        "reflections": [r.model_dump() for r in cycle_result.reflected_analyses]
    }


# =====================================================================
# EHR DATABASE API
# =====================================================================
@app.get("/api/slots")
async def get_available_slots(specialty: Optional[str] = None, doctor_name: Optional[str] = None):
    slots = db.find_available_slots(specialty=specialty, doctor_name=doctor_name)
    return {"status": "ok", "slots": [s.model_dump() for s in slots]}


@app.get("/api/database")
async def get_database_state():
    doctors_raw = db.list_doctors()
    doctors = []
    for d in doctors_raw:
        slots = db.find_available_slots(doctor_id=d.id)
        slot_times = [s.start_time_iso.split("T")[-1][:5] if "T" in s.start_time_iso else s.start_time_iso for s in slots]
        doctors.append({
            "id": d.id,
            "name": d.name,
            "specialty": d.specialty,
            "available_slots": slot_times or ["No open slots"]
        })

    appts_raw = db.get_all_appointments()
    appointments = []
    for a in appts_raw:
        appointments.append({
            "id": a.id,
            "patient_id": a.patient_id or "",
            "patient_name": a.patient_name,
            "patient_phone": a.patient_phone,
            "doctor_name": a.doctor_name,
            "doctor_id": a.doctor_id,
            "specialty": a.specialty,
            "slot_time": a.slot_iso,
            "status": a.status,
            "visit_type": a.visit_type or "ROUTINE"
        })

    patients_raw = db.list_patients()
    patients = [
        {
            "id": p.id,
            "name": p.name,
            "phone": p.phone,
            "created_at_iso": p.created_at_iso,
            "notes": p.notes or ""
        }
        for p in patients_raw
    ]

    triage_raw = db.get_triage_logs()
    escalations = []
    for t in triage_raw:
        escalations.append({
            "id": t.id,
            "patient_name": t.patient_name or "Anonymous",
            "emergency_type": t.reported_symptoms,
            "action_taken": t.action_taken,
            "escalated_at": t.timestamp_iso
        })

    return {
        "doctors": doctors,
        "appointments": appointments,
        "patients": patients,
        "escalations": escalations
    }


@app.post("/api/database/reset")
async def reset_database():
    global _cached_evaluation_result
    db.reset_database()
    sessions.clear()
    store.clear()
    _cached_evaluation_result = None
    agent.update_directives([])
    orchestrator.update_directives([])
    return {"status": "ok", "message": "Database, chat sessions, and learned policies reset to clean seeds"}


class WalkInBookingRequest(BaseModel):
    patient_name: str
    patient_phone: str
    doctor_id: str
    slot_iso: str
    reason: Optional[str] = "Front Desk Walk-In Intake"


@app.post("/api/appointments/walk-in")
async def register_walk_in_appointment(req: WalkInBookingRequest):
    if not req.patient_name.strip() or not req.patient_phone.strip():
        raise HTTPException(status_code=400, detail="Patient name and phone are required for walk-in registration.")

    appt, err = db.book_slot_atomic(
        doctor_id=req.doctor_id,
        patient_name=req.patient_name.strip(),
        patient_phone=req.patient_phone.strip(),
        slot_iso=req.slot_iso,
        reason=req.reason or "Front Desk Walk-In Intake",
        session_id="walk-in-front-desk"
    )
    if not appt:
        raise HTTPException(status_code=409, detail=err or "Requested slot is already booked or unavailable.")

    return {
        "status": "success",
        "appointment": {
            "id": appt.id,
            "patient_id": appt.patient_id or "",
            "patient_name": appt.patient_name,
            "patient_phone": appt.patient_phone,
            "doctor_name": appt.doctor_name,
            "slot_time": appt.slot_iso,
            "status": appt.status,
            "visit_type": appt.visit_type or "ROUTINE"
        },
        "message": f"Walk-in appointment {appt.id} confirmed with {appt.doctor_name}."
    }


class CancelAppointmentRequest(BaseModel):
    appointment_id: str


@app.post("/api/appointments/cancel")
async def cancel_appointment_endpoint(req: CancelAppointmentRequest):
    success = db.cancel_appointment(req.appointment_id)
    if not success:
        raise HTTPException(status_code=404, detail="Appointment not found or already cancelled.")
    return {"status": "ok", "message": f"Appointment {req.appointment_id} successfully cancelled."}


# =====================================================================
# STATIC ASSETS & SPA ROUTING
# =====================================================================
@app.get("/{filename:path}")
async def serve_static_assets(filename: str):
    target = FRONTEND_OUT / filename
    if target.is_file():
        return FileResponse(target)
    index_file = FRONTEND_OUT / "index.html"
    if index_file.exists() and not filename.startswith("api/"):
        return FileResponse(index_file)
    raise HTTPException(status_code=404, detail="Resource not found")


# =====================================================================
# ENTRY POINT
# =====================================================================
def open_browser():
    try:
        webbrowser.open("http://localhost:8000")
    except Exception:
        pass


def main():
    welcome = (
        "[bold cyan]CareLoop AI Clinical Agent Studio[/bold cyan]\n"
        "[green]Single-Command Unified Healthcare System & Evaluation Platform[/green]\n\n"
        "[bold]Web UI:[/bold]  [link=http://localhost:8000]http://localhost:8000[/link]\n"
        "[bold]EHR DB:[/bold]  SQLite (Thread-Safe)\n"
        "[bold]Model:[/bold]   Gemini 3.5 Flash-Lite\n\n"
        "[dim]Opening browser at http://localhost:8000 automatically... Press CTRL+C to stop.[/dim]"
    )
    console.print(Panel(welcome, title="🏥 [bold green]CareLoop Started[/bold green]", border_style="green"))

    # Open browser 1.2s after starting server
    threading.Timer(1.2, open_browser).start()

    # Run FastAPI server directly with app instance and info logging
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")


if __name__ == "__main__":
    main()
