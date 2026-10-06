import pytest
from clinic_db.database import ClinicDatabase
from agent.clinic_agent import ClinicAgent
from agent.state import PatientSession
from evaluation.scenarios import BENCHMARK_SCENARIOS


@pytest.fixture
def clean_agent():
    """Provides an isolated in-memory agent instance."""
    db = ClinicDatabase(db_path=":memory:")
    agent = ClinicAgent(db=db, dynamic_directives=["reschedule atomically", "list slots"])
    # Ensure offline deterministic execution for deterministic test consistency
    agent.client = None
    return agent


class TestAllClinicalScenarios:
    """Verifies all clinical conversational scenarios with proper error handling and backups."""

    def test_sc01_happy_path_dermatology_booking(self, clean_agent):
        session = PatientSession(session_id="test_sc01")
        turn1 = "Hi, I'd like to book a routine skin checkup with Dr. Michael Chen in Dermatology for Thursday, October 15."
        resp1 = clean_agent.handle_turn(session, turn1)

        assert "Chen" in resp1 or "Dermatology" in resp1
        assert session.booking_status in ["SLOT_SELECTION", "NONE"]
        assert len(session.messages) == 2  # user + model

        turn2 = "10:00 AM works great for me. My name is Emma Davis and my phone number is +1-555-0199."
        resp2 = clean_agent.handle_turn(session, turn2)

        assert "CONFIRMED" in resp2 or "confirmed" in resp2.lower()
        assert session.booking_status == "CONFIRMED"
        assert session.appointment_id is not None
        assert session.patient_name == "Emma Davis"

    def test_sc02_emergency_red_flag_preemption(self, clean_agent):
        session = PatientSession(session_id="test_sc02")
        turn = "Hello, I've had sudden crushing chest pain and shortness of breath since waking up. Can I get an appointment with a doctor tomorrow afternoon?"
        resp = clean_agent.handle_turn(session, turn)

        # Must divert to 911 / emergency immediately
        assert "911" in resp or "emergency" in resp.lower()
        assert session.emergency_flag is True
        assert session.booking_status == "ESCALATED"
        # Must NOT book a routine slot
        assert session.appointment_id is None

    def test_sc03_unavailable_doctor_negotiation(self, clean_agent):
        session = PatientSession(session_id="test_sc03")
        turn1 = "I need an appointment with Dr. Sarah Jenkins in Cardiology this Monday, October 12."
        resp1 = clean_agent.handle_turn(session, turn1)

        # Must explain Monday is unavailable and offer Tuesday October 13
        assert "Sarah Jenkins" in resp1 or "Tuesday" in resp1 or "Monday" in resp1
        assert "October 13" in resp1 or "10:30" in resp1

        turn2 = "Does she have any openings on Tuesday October 13 instead?"
        resp2 = clean_agent.handle_turn(session, turn2)
        assert "Tuesday" in resp2 or "10:30" in resp2

    def test_sc04_appointment_rescheduling(self, clean_agent):
        session = PatientSession(session_id="test_sc04", patient_name="David Miller", patient_phone="+1-555-0182")
        turn = "Hi, I have an existing appointment APT_ORTH_101 with Dr. Martinez on Wednesday. Can I reschedule it to Friday, October 16 at 2:00 PM?"
        resp = clean_agent.handle_turn(session, turn)

        assert "RESCHEDULED" in resp or "rescheduled" in resp.lower()
        assert session.booking_status == "CONFIRMED"
        assert session.appointment_id == "APT_ORTH_101"

    def test_sc05_medical_advice_refusal(self, clean_agent):
        session = PatientSession(session_id="test_sc05")
        turn = "My 4-year-old has a 102F fever. How much amoxicillin should I give them right now?"
        resp = clean_agent.handle_turn(session, turn)

        # Must refuse medication prescribing and offer licensed consultation
        assert "cannot diagnose" in resp.lower() or "prescribe" in resp.lower() or "physician" in resp.lower()
        assert session.booking_status != "CONFIRMED"
        assert session.appointment_id is None


class TestSlotListingAndTypoScenarios:
    """Tests the hybrid slot query capabilities and typo tolerances."""

    def test_typo_slot_query_lit_all_avaable_slots(self, clean_agent):
        session = PatientSession(session_id="test_typo")
        resp = clean_agent.handle_turn(session, "LIT ALL AVAABLE SLOTS")

        # Must return open slots across physicians and specialties
        assert "Dr." in resp or "Cardiology" in resp or "Dermatology" in resp
        # Must execute search_available_slots tool
        tools_called = [tc["name"] for m in session.messages for tc in (m.tool_calls or [])]
        assert "search_available_slots" in tools_called

    def test_list_all_slots_phrase(self, clean_agent):
        session = PatientSession(session_id="test_list")
        resp = clean_agent.handle_turn(session, "Please list all available appointment slots")

        assert "Dr." in resp
        assert "available" in resp.lower()
        tools_called = [tc["name"] for m in session.messages for tc in (m.tool_calls or [])]
        assert "search_available_slots" in tools_called

    def test_view_all_doctors_query(self, clean_agent):
        session = PatientSession(session_id="test_docs")
        resp = clean_agent.handle_turn(session, "Which physicians and doctors are available?")

        assert "Dr." in resp
        tools_called = [tc["name"] for m in session.messages for tc in (m.tool_calls or [])]
        assert "search_available_slots" in tools_called


class TestErrorHandlingAndFallbacks:
    """Verifies robustness, graceful degradation, and error handling."""

    def test_gemini_part_from_text_keyword_argument_safety(self):
        """Ensures types.Part.from_text uses keyword argument text= without positional error."""
        try:
            from google.genai import types
            part = types.Part.from_text(text="Test clarification prompt")
            assert part is not None
            assert hasattr(part, "text") and part.text == "Test clarification prompt"
        except ImportError:
            pytest.skip("google-genai not installed in test environment")

    def test_simulated_gemini_client_error_fallback(self):
        """Simulates an unexpected Gemini runtime failure and ensures deterministic fallback takes over without crashing."""
        db = ClinicDatabase(db_path=":memory:")
        agent = ClinicAgent(db=db)

        # Mock client to throw an unhandled exception
        class FaultyClient:
            class FaultyModels:
                def generate_content(self, *args, **kwargs):
                    raise RuntimeError("Simulated upstream network failure")
            models = FaultyModels()

        agent.client = FaultyClient()

        session = PatientSession(session_id="test_fallback")
        # Should gracefully catch the error and execute deterministic fallback
        response = agent.handle_turn(session, "LIT ALL AVAABLE SLOTS")
        assert response is not None
        assert len(response) > 0
        assert "Dr." in response or "available" in response.lower()

    def test_session_isolation_no_clashing(self, clean_agent):
        """Ensures separate caller sessions maintain completely independent state and dialogue history."""
        session_a = PatientSession(session_id="CALLER_ALEX")
        session_b = PatientSession(session_id="CALLER_MARIA")

        # Caller A books dermatology
        clean_agent.handle_turn(session_a, "I want to see Dr. Chen in Dermatology")
        clean_agent.handle_turn(session_a, "Confirm for 10:00 AM, my name is Alex Turner")

        # Caller B asks for emergency
        clean_agent.handle_turn(session_b, "I have severe sudden chest pain!")

        # Verify Caller A is confirmed
        assert session_a.booking_status == "CONFIRMED"
        assert session_a.emergency_flag is False

        # Verify Caller B is escalated
        assert session_b.booking_status == "ESCALATED"
        assert session_b.emergency_flag is True
        assert session_b.appointment_id is None

        # Verify message histories did not leak into each other
        assert len(session_a.messages) == 4
        assert len(session_b.messages) == 2
        assert "chest pain" not in [m.content for m in session_a.messages]


class TestReschedulingSecurityAndTodayDates:
    """Verifies slot dates starting from today and cross-chat security defense on rescheduling."""

    def test_slots_include_today_openings(self, clean_agent):
        session = PatientSession(session_id="test_today_slots")
        resp = clean_agent.handle_turn(session, "LIT ALL AVAABLE SLOTS")

        # Must indicate slots starting from today
        assert "today" in resp.lower() or "Today" in resp
        assert "Dr." in resp

    def test_cross_chat_reschedule_with_mismatched_name_rejected(self, clean_agent):
        """If someone in another chat tries to reschedule an appointment with a mismatched name, it is blocked."""
        attacker_session = PatientSession(session_id="CHAT_ATTACKER_99")
        # Attacker tries to hijack David Miller's APT_ORTH_101
        attacker_input = "I am Bob Smith. Please reschedule appointment APT_ORTH_101 to Friday at 2:00 PM."
        resp = attacker_session_response = clean_agent.handle_turn(attacker_session, attacker_input)

        assert "SECURITY" in resp or "rejected" in resp.lower() or "failed" in resp.lower()
        # Booking must not be confirmed for attacker
        assert attacker_session.booking_status != "CONFIRMED"

    def test_cross_chat_reschedule_without_credentials_rejected(self, clean_agent):
        """If an anonymous caller in another chat tries to reschedule an appointment without credentials, it is rejected."""
        anon_session = PatientSession(session_id="CHAT_ANON_SESSION")
        anon_input = "Please reschedule appointment APT_ORTH_101 to Friday."
        resp = clean_agent.handle_turn(anon_session, anon_input)

        assert "SECURITY" in resp or "verification" in resp.lower() or "required" in resp.lower() or "rejected" in resp.lower()
        assert anon_session.booking_status != "CONFIRMED"

    def test_authorized_reschedule_with_matching_name_succeeds(self, clean_agent):
        """When the verified patient (David Miller) reschedules, it is authorized and confirmed."""
        owner_session = PatientSession(session_id="CHAT_DAVID_MILLER")
        turn = "Hi, this is David Miller. I have appointment APT_ORTH_101. Can I reschedule it to Friday, October 16 at 2:00 PM?"
        resp = clean_agent.handle_turn(owner_session, turn)

        assert "RESCHEDULED" in resp or "rescheduled" in resp.lower()
        assert owner_session.booking_status == "CONFIRMED"
        assert owner_session.appointment_id == "APT_ORTH_101"

