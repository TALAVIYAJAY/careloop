import pytest
from fastapi.testclient import TestClient
from app import app


@pytest.fixture
def client():
    from app import app, agent, orchestrator
    agent.client = None
    if hasattr(orchestrator, "receptionist_agent"):
        orchestrator.receptionist_agent.client = None
    c = TestClient(app)
    # Ensure database is clean before tests run
    c.post("/api/database/reset")
    return c


class TestApiChatAndEndpoints:
    """Verifies all FastAPI API endpoints under various user scenarios and error states."""

    def test_api_status_endpoint(self, client):
        response = client.get("/api/status")
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "healthy"
        assert "doctors_count" in data
        assert "appointments_count" in data

    def test_api_database_endpoint(self, client):
        response = client.get("/api/database")
        assert response.status_code == 200
        data = response.json()
        assert "doctors" in data
        assert "appointments" in data
        assert "escalations" in data
        assert len(data["doctors"]) == 4

    def test_api_database_reset(self, client):
        response = client.post("/api/database/reset")
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "ok"

    def test_api_chat_query_slots_with_typo(self, client):
        payload = {
            "session_id": "api_test_typo",
            "message": "LIT ALL AVAABLE SLOTS"
        }
        response = client.post("/api/chat", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "response" in data
        assert len(data["response"]) > 0
        assert data["emergency_triggered"] is False
        assert "recent_tool_calls" in data
        assert any(tc["tool_name"] == "search_available_slots" for tc in data["recent_tool_calls"])

    def test_api_chat_emergency_preemption(self, client):
        payload = {
            "session_id": "api_test_emergency",
            "message": "I'm having acute crushing chest pain and difficulty breathing!"
        }
        response = client.post("/api/chat", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["emergency_triggered"] is True
        assert "911" in data["response"] or "emergency" in data["response"].lower()
        assert data["session"]["emergency_triggered"] is True

    def test_api_chat_medical_advice_refusal(self, client):
        payload = {
            "session_id": "api_test_advice",
            "message": "What dosage of amoxicillin should I give to my kid for their fever?"
        }
        response = client.post("/api/chat", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["emergency_triggered"] is False
        assert "prescribe" in data["response"].lower() or "cannot diagnose" in data["response"].lower() or "physician" in data["response"].lower()

    def test_api_chat_multi_turn_booking(self, client):
        session_id = "api_test_booking_flow"
        # Turn 1: Search slots
        p1 = {
            "session_id": session_id,
            "message": "I would like to see Dr. Sarah Jenkins in Cardiology on Tuesday Oct 13"
        }
        r1 = client.post("/api/chat", json=p1)
        assert r1.status_code == 200

        # Turn 2: Book slot
        p2 = {
            "session_id": session_id,
            "message": "Please book 10:30 AM with Dr. Sarah Jenkins for Alex Rivera, phone: +1-555-0142"
        }
        r2 = client.post("/api/chat", json=p2)
        assert r2.status_code == 200
        data2 = r2.json()
        assert "CONFIRMED" in data2["response"] or "confirmed" in data2["response"].lower()
        assert data2["session"]["triage_level"] == "CONFIRMED"

    def test_api_reset_session(self, client):
        session_id = "api_test_reset"
        # First send a message
        client.post("/api/chat", json={"session_id": session_id, "message": "Hello"})
        # Now reset
        res = client.post("/api/chat/reset", json={"session_id": session_id})
        assert res.status_code == 200
        data = res.json()
        assert data.get("status") == "ok"
        assert data.get("session_id") == session_id

    def test_api_chat_empty_message_rejected(self, client):
        # Sending empty or whitespace message must return 400 Bad Request
        res = client.post("/api/chat", json={"session_id": "api_test_empty", "message": "   "})
        assert res.status_code == 400
        assert "cannot be empty" in res.json().get("detail", "").lower()

    def test_independent_concurrent_sessions(self, client):
        # Ensure session 1 and session 2 are completely distinct
        r1 = client.post("/api/chat", json={"session_id": "SESSION_ALPHA", "message": "I need cardiology with Dr. Jenkins"})
        r2 = client.post("/api/chat", json={"session_id": "SESSION_BETA", "message": "I have sudden numbness and slurred speech"})

        data1 = r1.json()
        data2 = r2.json()

        assert data1["emergency_triggered"] is False
        assert data2["emergency_triggered"] is True

        assert data1["session"]["emergency_triggered"] is False
        assert data2["session"]["emergency_triggered"] is True

    def test_api_slots_include_today(self, client):
        response = client.get("/api/slots")
        assert response.status_code == 200
        slots = response.json().get("slots", [])
        assert len(slots) > 0
        from datetime import date
        today_iso = date.today().isoformat()
        # Ensure at least one available slot starts today
        has_today_slot = any(s["start_time_iso"].startswith(today_iso) for s in slots)
        assert has_today_slot is True

    def test_api_cross_session_reschedule_security_blocked(self, client):
        # Attacker tries to hijack David Miller's appointment APT_ORTH_101
        payload = {
            "session_id": "ATTACKER_SESSION_API",
            "message": "I am Bob Smith. Please reschedule appointment APT_ORTH_101 to Friday at 2:00 PM."
        }
        res = client.post("/api/chat", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert "SECURITY" in data["response"] or "rejected" in data["response"].lower() or "failed" in data["response"].lower() or data["session"]["triage_level"] != "CONFIRMED"
        assert data["session"]["triage_level"] != "CONFIRMED"

    def test_walk_in_registration_and_cancellation(self, client):
        # Step 1: Query open slots for Dr. Sarah Jenkins
        slots_res = client.get("/api/slots?doctor_name=Sarah Jenkins")
        assert slots_res.status_code == 200
        slots = slots_res.json().get("slots", [])
        assert len(slots) > 0
        target_slot = slots[0]["start_time_iso"]
        doctor_id = slots[0]["doctor_id"]

        # Step 2: Book walk-in appointment
        walk_in_payload = {
            "patient_name": "In-Person Patient Alex",
            "patient_phone": "+1-555-9999",
            "doctor_id": doctor_id,
            "slot_iso": target_slot,
            "reason": "Front Desk Walk-In Intake"
        }
        book_res = client.post("/api/appointments/walk-in", json=walk_in_payload)
        assert book_res.status_code == 200
        book_data = book_res.json()
        assert book_data["status"] == "success"
        appt_id = book_data["appointment"]["id"]
        assert appt_id.startswith("APT_")
        assert book_data["appointment"]["patient_name"] == "In-Person Patient Alex"

        # Step 3: Verify double booking same slot returns 409 Conflict
        conflict_res = client.post("/api/appointments/walk-in", json=walk_in_payload)
        assert conflict_res.status_code == 409

        # Step 4: Verify appointment appears in EHR database
        db_res = client.get("/api/database")
        assert db_res.status_code == 200
        appts = db_res.json().get("appointments", [])
        assert any(a["id"] == appt_id and a["patient_name"] == "In-Person Patient Alex" for a in appts)

        # Step 5: Cancel appointment via receptionist front desk
        cancel_res = client.post("/api/appointments/cancel", json={"appointment_id": appt_id})
        assert cancel_res.status_code == 200
        assert cancel_res.json()["status"] == "ok"

        # Step 6: Verify status is CANCELLED in EHR database
        db_res_after = client.get("/api/database")
        appts_after = db_res_after.json().get("appointments", [])
        target_appt = next(a for a in appts_after if a["id"] == appt_id)
        assert target_appt["status"] == "CANCELLED"

    def test_api_chat_frontend_slot_booking_evening(self, client):
        # Query open upcoming slots for Dr Priya Patel
        slots_res = client.get("/api/slots?doctor_name=Priya Patel")
        assert slots_res.status_code == 200
        slots = slots_res.json().get("slots", [])
        assert len(slots) > 0
        target_slot = slots[0]["start_time_iso"]

        payload = {
            "session_id": "api_test_evening_frontend",
            "message": f"Please schedule an appointment with Dr. Priya Patel [{target_slot}] for patient Jay Talaviya.",
            "patient_name": "Jay Talaviya",
            "patient_phone": "+1-555-0199",
            "patient_id": "PAT_JAY_001",
            "slot_iso": target_slot,
            "doctor_id": "DOC_PED_01",
            "doctor_name": "Dr. Priya Patel"
        }
        resp = client.post("/api/chat", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert "CONFIRMED" in data["response"] or "confirmed" in data["response"].lower()
        assert data["session"]["selected_slot"] == target_slot

        # Verify directly in SQLite DB
        db_res = client.get("/api/database")
        appts = db_res.json().get("appointments", [])
        my_appt = [a for a in appts if a.get("patient_name") == "Jay Talaviya"]
        assert len(my_appt) >= 1
        assert my_appt[-1]["slot_iso"] == target_slot

    def test_api_walk_in_past_slot_rejected(self, client):
        from datetime import datetime, timedelta
        past_iso = (datetime.now() - timedelta(hours=3)).strftime("%Y-%m-%dT%H:%M:00Z")
        payload = {
            "patient_name": "Late Alex",
            "patient_phone": "+1-555-1122",
            "doctor_id": "DOC_CARD_01",
            "slot_iso": past_iso,
            "reason": "Walk-in"
        }
        res = client.post("/api/appointments/walk-in", json=payload)
        assert res.status_code in [400, 409]
        assert "already passed" in res.json().get("detail", "").lower()
