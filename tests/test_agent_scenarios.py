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

    def test_multi_turn_reschedule_preserves_single_appointment_zero_duplicates(self, clean_agent):
        """
        Tests the exact user flow:
        1. Book Dr. Patel (Pediatrics) for today at 3:30 PM.
        2. Ask 'i want to reshedule' (typo test).
        3. Say 'tomorrow'.
        4. Assert that ONLY 1 appointment exists in EHR and it is atomically moved, with ZERO duplicates!
        """
        session = PatientSession(
            session_id="SESS_JAY_LIVE_TEST",
            patient_name="Jay Talaviya",
            patient_phone="+1-555-0199",
            patient_id="PAT_15550199"
        )

        # Step 1: Routine complaint
        resp1 = clean_agent.handle_turn(session, "i am having normal fever - low")
        assert "Patel" in resp1 or "available" in resp1.lower()

        # Step 2: Date filter
        resp2 = clean_agent.handle_turn(session, "today")
        assert "today" in resp2.lower() or "Patel" in resp2

        # Step 3: Pick time
        avail_patel = clean_agent.db.find_available_slots(doctor_id="DOC_PED_01")
        target_slot = avail_patel[0]
        resp3 = clean_agent.handle_turn(session, f"Please book [{target_slot.start_time_iso}]")
        assert "CONFIRMED" in resp3 or "confirmed" in resp3.lower()
        assert session.booking_status == "CONFIRMED"
        first_apt_id = session.appointment_id
        assert first_apt_id is not None

        # Verify initial booking in database
        initial_appts = clean_agent.db.get_patient_appointments("+1-555-0199")
        assert len(initial_appts) == 1
        assert initial_appts[0].id == first_apt_id
        initial_slot = initial_appts[0].slot_iso

        # Step 4: User asks to reschedule (with typo 'reshedule')
        resp4 = clean_agent.handle_turn(session, "i want to reshedule")
        assert "reschedule" in resp4.lower() or "available" in resp4.lower() or "slot" in resp4.lower()
        assert session.pending_action == "RESCHEDULE"

        # Step 5: User picks tomorrow
        resp5 = clean_agent.handle_turn(session, "tomorrow")
        assert "RESCHEDULED" in resp5 or "rescheduled" in resp5.lower()
        assert session.booking_status == "CONFIRMED"

        # Step 6: Verify ZERO DUPLICATES IN DATABASE
        final_appts = clean_agent.db.get_patient_appointments("+1-555-0199")
        assert len(final_appts) == 1, f"Expected exactly 1 appointment in EHR, but found {len(final_appts)}! (Duplicate booking bug)"
        assert final_appts[0].id == first_apt_id
        assert final_appts[0].slot_iso != initial_slot
        assert "tomorrow" in resp5.lower() or final_appts[0].slot_iso != initial_slot

        # Verify old slot was freed back to AVAILABLE
        old_slot_row = clean_agent.db.find_available_slots(doctor_id=initial_appts[0].doctor_id, include_past=True)
        old_slot_isos = [s.start_time_iso for s in old_slot_row]
        assert initial_slot in old_slot_isos, "Old slot was not released back to AVAILABLE status!"

    def test_doc_peds_alias_resilience_and_no_iso_leakage(self, clean_agent):
        """Verifies doctor ID resilience (DOC_PEDS_01 -> DOC_PED_01) and ensures no ISO tags leak to patient."""
        # 1. Alias resolution
        resolved = clean_agent.db.resolve_doctor_id("DOC_PEDS_01")
        assert resolved == "DOC_PED_01"

        # 2. Direct atomic booking with alias DOC_PEDS_01 succeeds
        p_slots = clean_agent.db.find_available_slots(doctor_id="DOC_PED_01")
        assert len(p_slots) > 0
        target_slot = p_slots[0].start_time_iso
        apt, err = clean_agent.db.book_slot_atomic(
            patient_name="Peds Test",
            patient_phone="+1-555-7766",
            doctor_id="DOC_PEDS_01",
            slot_iso=target_slot,
            reason="Low fever"
        )
        assert err is None
        assert apt is not None
        assert apt.doctor_id == "DOC_PED_01"

        # 3. Text sanitization strips [ISO: ...] and [tool slot_iso: ...]
        raw_msg = "We have slots available: Today at 11:30 AM [ISO: 2026-10-07T11:30:00Z] and Tomorrow [tool slot_iso: 2026-10-08T14:00:00Z]."
        sanitized = clean_agent._sanitize_patient_text(raw_msg)
        assert "[ISO:" not in sanitized
        assert "2026-10-07T11:30:00Z" not in sanitized
        assert "slot_iso" not in sanitized

    def test_explicit_slot_booking_honors_selected_time_not_1130(self, clean_agent):
        """Verifies that selecting an explicit slot books that exact slot and never defaults to 11:30 AM."""
        avail_patel = clean_agent.db.find_available_slots(doctor_id="DOC_PED_01")
        target_slot_iso = avail_patel[0].start_time_iso

        session = PatientSession(
            session_id="test_sess_explicit_slot",
            patient_name="Jay Talaviya",
            patient_phone="+1-555-0199",
            patient_id="PAT_JAY_001",
            selected_slot_iso=target_slot_iso,
            selected_doctor_id="DOC_PED_01",
            selected_doctor_name="Dr. Priya Patel"
        )

        msg = f"Please schedule an appointment with Dr. Priya Patel [{target_slot_iso}] for patient Jay Talaviya."
        resp = clean_agent.handle_turn(session, msg)
        assert "CONFIRMED" in resp or "confirmed" in resp.lower()

        # Check DB to verify it booked target_slot_iso exactly and never 11:30
        appts = clean_agent.db.get_patient_appointments("+1-555-0199")
        assert len(appts) == 1
        assert appts[0].slot_iso == target_slot_iso, f"Expected slot {target_slot_iso}, but got {appts[0].slot_iso} (11:30 fallback bug!)"

    def test_natural_language_evening_slot_booking_630pm_and_7pm(self, clean_agent, monkeypatch):
        """Verifies that saying 'today at 6:30 pm' or '7:00 pm' books that exact evening slot."""
        # Simulate daytime execution so evening slots remain bookable 24/7 regardless of test run time
        monkeypatch.setattr(clean_agent.db, "is_past_slot", lambda s, ref_dt=None: False)
        from datetime import date
        today_str = date.today().isoformat()
        slot_630pm = f"{today_str}T18:30:00Z"
        slot_7pm = f"{today_str}T19:00:00Z"

        # Patient 1: Books 6:30 PM
        session1 = PatientSession(
            session_id="test_sess_630pm",
            patient_name="Jay Talaviya",
            patient_phone="+1-555-0199",
            patient_id="PAT_JAY_001"
        )
        resp1_1 = clean_agent.handle_turn(session1, "I have mild fever and want Dr. Patel")
        assert "Patel" in resp1_1
        resp1_2 = clean_agent.handle_turn(session1, "today at 6:30 pm")
        assert "CONFIRMED" in resp1_2 or "confirmed" in resp1_2.lower()
        appts1 = clean_agent.db.get_patient_appointments("+1-555-0199")
        assert len(appts1) == 1
        assert appts1[0].slot_iso == slot_630pm, f"Expected {slot_630pm}, got {appts1[0].slot_iso}"

        # Patient 2: Routine inquiry then selects 7:00 PM
        session2 = PatientSession(
            session_id="test_sess_7pm",
            patient_name="Alex Turner",
            patient_phone="+1-555-0101",
            patient_id="PAT_0101"
        )
        resp2_1 = clean_agent.handle_turn(session2, "I need to see Dr. Patel for a checkup")
        assert "Patel" in resp2_1
        resp2_2 = clean_agent.handle_turn(session2, "7pm works for me")
        assert "CONFIRMED" in resp2_2 or "confirmed" in resp2_2.lower()
        appts2 = clean_agent.db.get_patient_appointments("+1-555-0101")
        assert len(appts2) == 1
        assert appts2[0].slot_iso == slot_7pm, f"Expected {slot_7pm}, got {appts2[0].slot_iso}"

    def test_past_slot_booking_rejected_by_agent(self, clean_agent):
        """Verifies that an attempt to book a slot that has already passed is rejected."""
        from datetime import datetime, timedelta
        past_iso = (datetime.now() - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:00Z")
        session = PatientSession(
            session_id="test_sess_past_rejection",
            patient_name="Late Patient",
            patient_phone="+1-555-0199",
            selected_slot_iso=past_iso,
            selected_doctor_id="DOC_PED_01"
        )
        resp = clean_agent.handle_turn(session, f"Please book appointment at [{past_iso}]")
        assert session.booking_status != "CONFIRMED"
        assert "passed" in resp.lower() or "not available" in resp.lower() or "upcoming" in resp.lower() or "could not be booked" in resp.lower()


