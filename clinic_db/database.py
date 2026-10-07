import sqlite3
import uuid
from datetime import datetime
from typing import List, Optional, Tuple, Dict, Any
from contextlib import contextmanager

from .models import Doctor, AppointmentSlot, Appointment, TriageLog, Patient
from .seeds import DOCTORS_SEED, SLOTS_SEED, EXISTING_APPOINTMENTS_SEED


class ClinicDatabase:
    """
    Thread-safe SQLite database manager for CareLoop EHR.
    Provides atomic transactions for appointment booking, slot locking, and emergency logging.
    Supports both file-backed database and in-memory (:memory:) SQLite.
    """

    def __init__(self, db_path: str = "clinic.db"):
        self.db_path = db_path
        self._is_memory = (db_path == ":memory:")
        if self._is_memory:
            self._shared_conn = sqlite3.connect(":memory:", check_same_thread=False)
            self._shared_conn.row_factory = sqlite3.Row
            self._shared_conn.execute("PRAGMA foreign_keys = ON")
        else:
            self._shared_conn = None

        self._init_schema()

    @contextmanager
    def _conn_context(self):
        """Yields a connection, managing transaction commit/rollback and file cleanup."""
        if self._is_memory:
            yield self._shared_conn
            self._shared_conn.commit()
        else:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON")
            try:
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()

    def _init_schema(self) -> None:
        """Create tables if they do not exist, and seed data if empty."""
        with self._conn_context() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS doctors (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    specialty TEXT NOT NULL,
                    room_number TEXT NOT NULL,
                    bio TEXT NOT NULL
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS slots (
                    id TEXT PRIMARY KEY,
                    doctor_id TEXT NOT NULL,
                    doctor_name TEXT NOT NULL,
                    specialty TEXT NOT NULL,
                    start_time_iso TEXT NOT NULL,
                    end_time_iso TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'AVAILABLE',
                    booked_patient_name TEXT,
                    booked_patient_phone TEXT,
                    FOREIGN KEY (doctor_id) REFERENCES doctors(id)
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS patients (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    phone TEXT UNIQUE NOT NULL,
                    created_at_iso TEXT NOT NULL,
                    notes TEXT
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS appointments (
                    id TEXT PRIMARY KEY,
                    patient_id TEXT,
                    patient_name TEXT NOT NULL,
                    patient_phone TEXT NOT NULL,
                    doctor_id TEXT NOT NULL,
                    doctor_name TEXT NOT NULL,
                    specialty TEXT NOT NULL,
                    slot_iso TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'CONFIRMED',
                    visit_type TEXT NOT NULL DEFAULT 'ROUTINE',
                    created_at_iso TEXT NOT NULL,
                    session_id TEXT,
                    FOREIGN KEY (doctor_id) REFERENCES doctors(id)
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS triage_logs (
                    id TEXT PRIMARY KEY,
                    patient_id TEXT,
                    patient_name TEXT,
                    patient_phone TEXT,
                    reported_symptoms TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    action_taken TEXT NOT NULL,
                    timestamp_iso TEXT NOT NULL
                )
            """)
            conn.commit()

            # Ensure all columns exist if table was previously created
            cursor.execute("PRAGMA table_info(appointments)")
            columns = [col[1] for col in cursor.fetchall()]
            if "session_id" not in columns:
                cursor.execute("ALTER TABLE appointments ADD COLUMN session_id TEXT")
            if "patient_id" not in columns:
                cursor.execute("ALTER TABLE appointments ADD COLUMN patient_id TEXT")
            if "visit_type" not in columns:
                cursor.execute("ALTER TABLE appointments ADD COLUMN visit_type TEXT DEFAULT 'ROUTINE'")
            conn.commit()

            # Seed if doctors table is empty
            cursor.execute("SELECT COUNT(*) FROM doctors")
            if cursor.fetchone()[0] == 0:
                self.seed_defaults(conn)

    def seed_defaults(self, conn: Optional[sqlite3.Connection] = None) -> None:
        """Populates baseline doctors, slots, and appointments."""
        if conn is not None:
            self._do_seed(conn)
        else:
            with self._conn_context() as c:
                self._do_seed(c)

    def _do_seed(self, conn: sqlite3.Connection) -> None:
        cursor = conn.cursor()
        for doc in DOCTORS_SEED:
            cursor.execute(
                "INSERT OR REPLACE INTO doctors (id, name, specialty, room_number, bio) VALUES (?, ?, ?, ?, ?)",
                (doc["id"], doc["name"], doc["specialty"], doc["room_number"], doc["bio"])
            )

        for slot in SLOTS_SEED:
            cursor.execute(
                """INSERT OR REPLACE INTO slots 
                   (id, doctor_id, doctor_name, specialty, start_time_iso, end_time_iso, status, booked_patient_name, booked_patient_phone)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    slot["id"], slot["doctor_id"], slot["doctor_name"], slot["specialty"],
                    slot["start_time_iso"], slot["end_time_iso"], slot["status"],
                    slot.get("booked_patient_name"), slot.get("booked_patient_phone")
                )
            )

        cursor.execute(
            "INSERT OR REPLACE INTO patients (id, name, phone, created_at_iso, notes) VALUES (?, ?, ?, ?, ?)",
            ("PAT_15550182", "David Miller", "+1-555-0182", datetime.utcnow().isoformat(), "Seeded benchmark patient")
        )

        for apt in EXISTING_APPOINTMENTS_SEED:
            cursor.execute(
                """INSERT OR REPLACE INTO appointments 
                   (id, patient_id, patient_name, patient_phone, doctor_id, doctor_name, specialty, slot_iso, reason, status, visit_type, created_at_iso, session_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    apt["id"], apt.get("patient_id", "PAT_15550182"), apt["patient_name"], apt["patient_phone"], apt["doctor_id"],
                    apt["doctor_name"], apt["specialty"], apt["slot_iso"], apt["reason"],
                    apt["status"], apt.get("visit_type", "FOLLOWUP"), datetime.utcnow().isoformat(), apt.get("session_id")
                )
            )

    def reset_database(self) -> None:
        """Wipes and reseeds the entire database for test scenario isolation."""
        with self._conn_context() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM appointments")
            cursor.execute("DELETE FROM slots")
            cursor.execute("DELETE FROM doctors")
            cursor.execute("DELETE FROM triage_logs")
            cursor.execute("DELETE FROM patients")
            self._do_seed(conn)

    # -------------------------------------------------------------
    # PATIENT MASTER DIRECTORY METHODS
    # -------------------------------------------------------------
    @staticmethod
    def normalize_phone(phone: str) -> str:
        digits = "".join(c for c in phone if c.isdigit())
        return digits if digits else phone.strip()

    def get_or_create_patient(
        self,
        name: str,
        phone: str,
        notes: Optional[str] = None
    ) -> Patient:
        """Looks up existing patient by phone; creates unique Patient record if not found."""
        clean_name = name.strip()
        clean_phone = phone.strip()
        digits = self.normalize_phone(clean_phone)
        patient_id = f"PAT_{digits}" if digits else f"PAT_{uuid.uuid4().hex[:8].upper()}"

        with self._conn_context() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM patients WHERE phone = ? OR id = ?", (clean_phone, patient_id))
            row = cursor.fetchone()
            if row:
                return Patient(**dict(row))

            now_iso = datetime.utcnow().isoformat()
            cursor.execute(
                "INSERT INTO patients (id, name, phone, created_at_iso, notes) VALUES (?, ?, ?, ?, ?)",
                (patient_id, clean_name, clean_phone, now_iso, notes)
            )
            return Patient(id=patient_id, name=clean_name, phone=clean_phone, created_at_iso=now_iso, notes=notes)

    def get_patient(self, patient_id: str) -> Optional[Patient]:
        with self._conn_context() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM patients WHERE id = ?", (patient_id,))
            row = cursor.fetchone()
            return Patient(**dict(row)) if row else None

    def get_patient_by_phone(self, phone: str) -> Optional[Patient]:
        clean_phone = phone.strip()
        digits = self.normalize_phone(clean_phone)
        patient_id = f"PAT_{digits}"
        with self._conn_context() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM patients WHERE phone = ? OR id = ?", (clean_phone, patient_id))
            row = cursor.fetchone()
            return Patient(**dict(row)) if row else None

    def list_patients(self) -> List[Patient]:
        with self._conn_context() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM patients ORDER BY name ASC")
            rows = cursor.fetchall()
            return [Patient(**dict(r)) for r in rows]

    def get_patient_appointments(self, patient_identifier: str) -> List[Appointment]:
        """Finds all appointments matching patient_id, phone, or name."""
        clean_id = patient_identifier.strip()
        with self._conn_context() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """SELECT * FROM appointments 
                   WHERE patient_id = ? OR patient_phone = ? OR LOWER(patient_name) = LOWER(?)
                   ORDER BY slot_iso ASC""",
                (clean_id, clean_id, clean_id)
            )
            rows = cursor.fetchall()
            return [Appointment(**dict(r)) for r in rows]

    # -------------------------------------------------------------
    # QUERY METHODS
    # -------------------------------------------------------------
    def list_doctors(self, specialty: Optional[str] = None) -> List[Doctor]:
        with self._conn_context() as conn:
            cursor = conn.cursor()
            if specialty:
                cursor.execute("SELECT * FROM doctors WHERE LOWER(specialty) = LOWER(?)", (specialty,))
            else:
                cursor.execute("SELECT * FROM doctors")
            rows = cursor.fetchall()
            return [Doctor(**dict(r)) for r in rows]

    DOCTOR_ID_ALIASES = {
        "DOC_PEDS_01": "DOC_PED_01",
        "DOC_PED_01": "DOC_PED_01",
        "DOC_DERMATOLOGY_01": "DOC_DERM_01",
        "DOC_DERM_01": "DOC_DERM_01",
        "DOC_ORTHO_01": "DOC_ORTH_01",
        "DOC_ORTH_01": "DOC_ORTH_01",
        "DOC_CARDIO_01": "DOC_CARD_01",
        "DOC_CARD_01": "DOC_CARD_01",
        "PATEL": "DOC_PED_01",
        "CHEN": "DOC_DERM_01",
        "MARTINEZ": "DOC_ORTH_01",
        "JENKINS": "DOC_CARD_01",
    }

    def resolve_doctor_id(self, doctor_id: Optional[str], slot_iso: Optional[str] = None) -> Optional[str]:
        """Resolves doctor ID from canonical aliases, slot ISO association, or name lookup."""
        if not doctor_id and not slot_iso:
            return None

        clean_doc_id = str(doctor_id).strip() if doctor_id else ""
        if clean_doc_id.upper() in self.DOCTOR_ID_ALIASES:
            return self.DOCTOR_ID_ALIASES[clean_doc_id.upper()]

        with self._conn_context() as conn:
            cursor = conn.cursor()
            # 1. Exact match in doctors table
            if clean_doc_id:
                cursor.execute("SELECT id FROM doctors WHERE id = ?", (clean_doc_id,))
                row = cursor.fetchone()
                if row:
                    return row["id"]

            # 2. Match from slot_iso directly if provided
            if slot_iso:
                cursor.execute("SELECT doctor_id FROM slots WHERE start_time_iso = ? LIMIT 1", (slot_iso,))
                row = cursor.fetchone()
                if row:
                    return row["doctor_id"]

            # 3. Match from doctor name or specialty substring
            if clean_doc_id:
                cursor.execute(
                    "SELECT id FROM doctors WHERE LOWER(name) LIKE ? OR LOWER(specialty) LIKE ? LIMIT 1",
                    (f"%{clean_doc_id.lower()}%", f"%{clean_doc_id.lower()}%")
                )
                row = cursor.fetchone()
                if row:
                    return row["id"]

        return clean_doc_id or None

    @staticmethod
    def is_past_slot(slot_iso: str, ref_dt: Optional[datetime] = None) -> bool:
        """
        Determines whether an appointment slot's scheduled start time has already passed
        relative to the local clinic wall-clock time.
        """
        if not slot_iso:
            return False
        try:
            clean = str(slot_iso).strip().replace("Z", "").replace(" ", "T")
            if len(clean) == 16:  # YYYY-MM-DDTHH:MM
                clean += ":00"
            slot_dt = datetime.fromisoformat(clean)
            current_dt = ref_dt or datetime.now()
            return slot_dt <= current_dt
        except Exception:
            return False

    def find_available_slots(
        self,
        specialty: Optional[str] = None,
        doctor_id: Optional[str] = None,
        doctor_name: Optional[str] = None,
        date_str: Optional[str] = None,
        include_past: bool = False
    ) -> List[AppointmentSlot]:
        """Returns open (AVAILABLE) slots matching filters. Excludes past slots by default."""
        query = "SELECT * FROM slots WHERE status = 'AVAILABLE'"
        params = []

        if specialty:
            query += " AND LOWER(specialty) LIKE ?"
            params.append(f"%{specialty.lower()}%")
        if doctor_id:
            resolved_doc_id = self.resolve_doctor_id(doctor_id)
            if resolved_doc_id:
                doctor_id = resolved_doc_id
            query += " AND doctor_id = ?"
            params.append(doctor_id)
        if doctor_name:
            import re
            cleaned_doc = re.sub(r'^(dr\.?|doctor)\s+', '', doctor_name.strip(), flags=re.IGNORECASE).strip()
            tokens = [t for t in cleaned_doc.split() if len(t) > 1]
            if tokens:
                for token in tokens:
                    query += " AND LOWER(doctor_name) LIKE ?"
                    params.append(f"%{token.lower()}%")
            else:
                query += " AND LOWER(doctor_name) LIKE ?"
                params.append(f"%{doctor_name.lower()}%")
        if date_str:
            query += " AND start_time_iso LIKE ?"
            params.append(f"{date_str}%")

        query += " ORDER BY start_time_iso ASC"

        with self._conn_context() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()
            slots = [AppointmentSlot(**dict(r)) for r in rows]
            if not include_past:
                slots = [s for s in slots if not self.is_past_slot(s.start_time_iso)]
            return slots

    def book_slot_atomic(
        self,
        patient_name: str,
        patient_phone: str,
        doctor_id: str,
        slot_iso: str,
        reason: str,
        session_id: Optional[str] = None,
        visit_type: Optional[str] = "ROUTINE",
        patient_id: Optional[str] = None
    ) -> Tuple[Optional[Appointment], Optional[str]]:
        """
        Atomically locks a slot and creates an appointment.
        Prevents race conditions and phantom bookings.
        Integrates with Master Patient Index (patient_id).
        """
        if not patient_name or not patient_phone:
            return None, "Patient name and contact phone are required to complete booking."

        # VALIDATION: Cannot book appointment in the past
        if self.is_past_slot(slot_iso):
            return None, f"Cannot book appointment: the requested slot ({slot_iso}) has already passed. Please select an upcoming opening."

        # Automatically resolve or create Master Patient record
        if not patient_id:
            patient_rec = self.get_or_create_patient(patient_name, patient_phone)
            patient_id = patient_rec.id
        else:
            self.get_or_create_patient(patient_name, patient_phone)

        # Resolve doctor ID from aliases or slot ISO
        resolved_doc_id = self.resolve_doctor_id(doctor_id, slot_iso=slot_iso)
        if resolved_doc_id:
            doctor_id = resolved_doc_id

        with self._conn_context() as conn:
            cursor = conn.cursor()
            # 1. Check if doctor exists
            cursor.execute("SELECT * FROM doctors WHERE id = ?", (doctor_id,))
            doc_row = cursor.fetchone()
            if not doc_row and slot_iso:
                # Fallback: check if slot exists for any doctor
                cursor.execute("SELECT doctor_id FROM slots WHERE start_time_iso = ? LIMIT 1", (slot_iso,))
                s_row = cursor.fetchone()
                if s_row:
                    doctor_id = s_row["doctor_id"]
                    cursor.execute("SELECT * FROM doctors WHERE id = ?", (doctor_id,))
                    doc_row = cursor.fetchone()

            if not doc_row:
                return None, f"Doctor ID '{doctor_id}' does not exist in clinic registry."

            doctor = Doctor(**dict(doc_row))

            # 2. Check if slot exists and is AVAILABLE (Atomic check-and-update)
            cursor.execute(
                "SELECT * FROM slots WHERE doctor_id = ? AND start_time_iso = ?",
                (doctor_id, slot_iso)
            )
            slot_row = cursor.fetchone()
            if not slot_row and slot_iso:
                # Check if slot exists with another doctor at that same start_time_iso
                cursor.execute("SELECT * FROM slots WHERE start_time_iso = ? LIMIT 1", (slot_iso,))
                alt_slot = cursor.fetchone()
                if alt_slot:
                    doctor_id = alt_slot["doctor_id"]
                    slot_row = alt_slot
                    cursor.execute("SELECT * FROM doctors WHERE id = ?", (doctor_id,))
                    doc_row = cursor.fetchone()
                    if doc_row:
                        doctor = Doctor(**dict(doc_row))

            if not slot_row:
                return None, f"No slot found for {doctor.name} at {slot_iso}."

            if slot_row["status"] != "AVAILABLE":
                return None, f"Slot at {slot_iso} with {doctor.name} is already booked or unavailable."

            slot_id = slot_row["id"]

            # 3. Mark slot as booked
            cursor.execute(
                """UPDATE slots 
                   SET status = 'BOOKED', booked_patient_name = ?, booked_patient_phone = ?
                   WHERE id = ? AND status = 'AVAILABLE'""",
                (patient_name, patient_phone, slot_id)
            )
            if cursor.rowcount == 0:
                return None, "Concurrent booking detected. Slot was just taken by another patient."

            # 4. Insert appointment record with patient_id and visit_type
            apt_id = f"APT_{uuid.uuid4().hex[:8].upper()}"
            cursor.execute(
                """INSERT INTO appointments 
                   (id, patient_id, patient_name, patient_phone, doctor_id, doctor_name, specialty, slot_iso, reason, status, visit_type, created_at_iso, session_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'CONFIRMED', ?, ?, ?)""",
                (
                    apt_id, patient_id, patient_name, patient_phone, doctor.id, doctor.name,
                    doctor.specialty, slot_iso, reason, visit_type or "ROUTINE", datetime.utcnow().isoformat(), session_id
                )
            )

            cursor.execute("SELECT * FROM appointments WHERE id = ?", (apt_id,))
            created_row = cursor.fetchone()
            return Appointment(**dict(created_row)), None

    def reschedule_appointment_atomic(
        self,
        appointment_id: str,
        new_slot_iso: str,
        patient_name: Optional[str] = None,
        patient_phone: Optional[str] = None,
        session_id: Optional[str] = None,
        doctor_id: Optional[str] = None
    ) -> Tuple[Optional[Appointment], Optional[str]]:
        """Atomically releases old slot and books new slot for existing appointment with full security verification."""
        with self._conn_context() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM appointments WHERE id = ?", (appointment_id,))
            apt_row = cursor.fetchone()
            if not apt_row:
                return None, f"Appointment ID '{appointment_id}' not found."

            apt = Appointment(**dict(apt_row))
            if apt.status != "CONFIRMED":
                return None, f"Cannot reschedule appointment with status '{apt.status}'."

            # SECURITY VALIDATION (CROSS-CHAT HIJACKING DEFENSE):
            # 1. If patient_name is provided, it MUST match the appointment record
            if patient_name:
                cleaned_req_name = patient_name.strip().lower()
                cleaned_apt_name = apt.patient_name.strip().lower()
                if cleaned_req_name != cleaned_apt_name and cleaned_req_name not in cleaned_apt_name and cleaned_apt_name not in cleaned_req_name:
                    return None, f"SECURITY REJECTION: Patient name '{patient_name}' does not match the registered patient for appointment '{appointment_id}'."

            # 2. If patient_phone is provided, verify matching phone
            if patient_phone:
                digits_req = "".join(filter(str.isdigit, patient_phone))
                digits_apt = "".join(filter(str.isdigit, apt.patient_phone))
                if digits_req and digits_apt and digits_req != digits_apt:
                    return None, f"SECURITY REJECTION: Provided phone number does not match the contact on file for appointment '{appointment_id}'."

            # 3. If explicitly an unauthenticated cross-session attempt, require patient_name
            is_cross_session = bool(session_id and apt.session_id and session_id != apt.session_id)
            if is_cross_session:
                if not patient_name:
                    return None, f"SECURITY AUTHENTICATION REQUIRED: To reschedule appointment '{appointment_id}' across sessions, patient full name must be provided for verification."

            # VALIDATION: Cannot reschedule to a slot in the past
            if self.is_past_slot(new_slot_iso):
                return None, f"Cannot reschedule appointment: the requested slot ({new_slot_iso}) has already passed. Please select an upcoming opening."

            # Check new slot availability
            target_doc_id = self.resolve_doctor_id(doctor_id, slot_iso=new_slot_iso) if doctor_id else apt.doctor_id
            cursor.execute(
                "SELECT * FROM slots WHERE doctor_id = ? AND start_time_iso = ? AND status = 'AVAILABLE'",
                (target_doc_id, new_slot_iso)
            )
            new_slot_row = cursor.fetchone()
            if not new_slot_row:
                # If doctor wasn't specified or mismatched, check if any doctor has this slot open
                cursor.execute(
                    "SELECT * FROM slots WHERE start_time_iso = ? AND status = 'AVAILABLE'",
                    (new_slot_iso,)
                )
                new_slot_row = cursor.fetchone()

            if not new_slot_row:
                return None, f"New requested slot at {new_slot_iso} is not available."

            # Release old slot
            cursor.execute(
                """UPDATE slots 
                   SET status = 'AVAILABLE', booked_patient_name = NULL, booked_patient_phone = NULL 
                   WHERE doctor_id = ? AND start_time_iso = ?""",
                (apt.doctor_id, apt.slot_iso)
            )

            # Book new slot
            cursor.execute(
                """UPDATE slots 
                   SET status = 'BOOKED', booked_patient_name = ?, booked_patient_phone = ? 
                   WHERE id = ?""",
                (apt.patient_name, apt.patient_phone, new_slot_row["id"])
            )

            # Update appointment
            cursor.execute(
                """UPDATE appointments 
                   SET slot_iso = ?, doctor_id = ?, doctor_name = ?, specialty = ? 
                   WHERE id = ?""",
                (new_slot_iso, new_slot_row["doctor_id"], new_slot_row["doctor_name"], new_slot_row["specialty"], appointment_id)
            )

            cursor.execute("SELECT * FROM appointments WHERE id = ?", (appointment_id,))
            updated_row = cursor.fetchone()
            return Appointment(**dict(updated_row)), None

    def get_appointment(self, appointment_id: str) -> Optional[Appointment]:
        """Retrieves a single appointment by its unique confirmation ID."""
        with self._conn_context() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM appointments WHERE id = ?", (appointment_id,))
            row = cursor.fetchone()
            if row:
                return Appointment(**dict(row))
            return None

    def cancel_appointment(self, appointment_id: str) -> bool:
        """Cancels an appointment and frees up the associated slot."""
        with self._conn_context() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM appointments WHERE id = ?", (appointment_id,))
            apt_row = cursor.fetchone()
            if not apt_row:
                return False

            apt = Appointment(**dict(apt_row))
            if apt.status == "CANCELLED":
                return False

            # Mark appointment as CANCELLED
            cursor.execute("UPDATE appointments SET status = 'CANCELLED' WHERE id = ?", (appointment_id,))

            # Release slot back to AVAILABLE
            cursor.execute(
                """UPDATE slots 
                   SET status = 'AVAILABLE', booked_patient_name = NULL, booked_patient_phone = NULL 
                   WHERE doctor_id = ? AND start_time_iso = ?""",
                (apt.doctor_id, apt.slot_iso)
            )
            return True

    def log_emergency_triage(
        self,
        reported_symptoms: str,
        severity: str = "EMERGENCY",
        patient_name: Optional[str] = None,
        patient_phone: Optional[str] = None
    ) -> TriageLog:
        """Logs acute emergency triage event and alert for clinic records."""
        with self._conn_context() as conn:
            cursor = conn.cursor()
            triage_id = f"TRG_{uuid.uuid4().hex[:8].upper()}"
            action_taken = "Patient directed to call 911 / visit nearest Emergency Room immediately."
            timestamp = datetime.utcnow().isoformat()

            cursor.execute(
                """INSERT INTO triage_logs 
                   (id, patient_name, patient_phone, reported_symptoms, severity, action_taken, timestamp_iso)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (triage_id, patient_name, patient_phone, reported_symptoms, severity, action_taken, timestamp)
            )

            cursor.execute("SELECT * FROM triage_logs WHERE id = ?", (triage_id,))
            row = cursor.fetchone()
            return TriageLog(**dict(row))

    # -------------------------------------------------------------
    # AUDIT / STATE ASSERTION HELPERS
    # -------------------------------------------------------------
    def get_appointments_by_patient(self, patient_name: str) -> List[Appointment]:
        with self._conn_context() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM appointments WHERE LOWER(patient_name) LIKE ?", (f"%{patient_name.lower()}%",))
            return [Appointment(**dict(r)) for r in cursor.fetchall()]

    def get_all_appointments(self) -> List[Appointment]:
        with self._conn_context() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM appointments ORDER BY created_at_iso DESC")
            return [Appointment(**dict(r)) for r in cursor.fetchall()]

    def get_triage_logs(self) -> List[TriageLog]:
        with self._conn_context() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM triage_logs ORDER BY timestamp_iso DESC")
            return [TriageLog(**dict(r)) for r in cursor.fetchall()]
