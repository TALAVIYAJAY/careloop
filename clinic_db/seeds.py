"""
Realistic seed data for CareLoop Clinic EHR database.
Provides diverse doctors across 4 departments with realistic availability starting from TODAY.
"""
from datetime import date, datetime, timedelta
from typing import List, Dict, Any

DOCTORS_SEED = [
    {
        "id": "DOC_CARD_01",
        "name": "Dr. Sarah Jenkins",
        "specialty": "Cardiology",
        "room_number": "Suite 201",
        "bio": "Board-certified cardiologist specializing in preventive cardiology and hypertension management."
    },
    {
        "id": "DOC_DERM_01",
        "name": "Dr. Michael Chen",
        "specialty": "Dermatology",
        "room_number": "Suite 305",
        "bio": "Dermatologist with 12 years of experience in clinical dermatology, skin checks, and eczema."
    },
    {
        "id": "DOC_PED_01",
        "name": "Dr. Priya Patel",
        "specialty": "Pediatrics",
        "room_number": "Suite 110",
        "bio": "Pediatrician specializing in child wellness, childhood immunizations, and adolescent medicine."
    },
    {
        "id": "DOC_ORTH_01",
        "name": "Dr. Robert Martinez",
        "specialty": "Orthopedics",
        "room_number": "Suite 402",
        "bio": "Orthopedic specialist focusing on joint pain, sports injuries, and musculoskeletal recovery."
    }
]

# Benchmark reference slots (used by standard evaluation harness & scenarios)
BENCHMARK_REFERENCE_SLOTS = [
    # Dr. Michael Chen (Dermatology)
    {
        "id": "SLOT_DERM_01",
        "doctor_id": "DOC_DERM_01",
        "doctor_name": "Dr. Michael Chen",
        "specialty": "Dermatology",
        "start_time_iso": "2026-10-15T10:00:00Z",
        "end_time_iso": "2026-10-15T10:30:00Z",
        "status": "AVAILABLE"
    },
    {
        "id": "SLOT_DERM_02",
        "doctor_id": "DOC_DERM_01",
        "doctor_name": "Dr. Michael Chen",
        "specialty": "Dermatology",
        "start_time_iso": "2026-10-15T14:00:00Z",
        "end_time_iso": "2026-10-15T14:30:00Z",
        "status": "AVAILABLE"
    },
    {
        "id": "SLOT_DERM_03",
        "doctor_id": "DOC_DERM_01",
        "doctor_name": "Dr. Michael Chen",
        "specialty": "Dermatology",
        "start_time_iso": "2026-10-16T11:00:00Z",
        "end_time_iso": "2026-10-16T11:30:00Z",
        "status": "AVAILABLE"
    },

    # Dr. Sarah Jenkins (Cardiology) - Booked on Monday Oct 12, open Tuesday Oct 13
    {
        "id": "SLOT_CARD_01",
        "doctor_id": "DOC_CARD_01",
        "doctor_name": "Dr. Sarah Jenkins",
        "specialty": "Cardiology",
        "start_time_iso": "2026-10-12T09:00:00Z",
        "end_time_iso": "2026-10-12T09:30:00Z",
        "status": "BOOKED",
        "booked_patient_name": "James Wilson",
        "booked_patient_phone": "+1-555-0199"
    },
    {
        "id": "SLOT_CARD_02",
        "doctor_id": "DOC_CARD_01",
        "doctor_name": "Dr. Sarah Jenkins",
        "specialty": "Cardiology",
        "start_time_iso": "2026-10-12T14:00:00Z",
        "end_time_iso": "2026-10-12T14:30:00Z",
        "status": "BOOKED",
        "booked_patient_name": "Linda Vance",
        "booked_patient_phone": "+1-555-0144"
    },
    {
        "id": "SLOT_CARD_03",
        "doctor_id": "DOC_CARD_01",
        "doctor_name": "Dr. Sarah Jenkins",
        "specialty": "Cardiology",
        "start_time_iso": "2026-10-13T10:30:00Z",
        "end_time_iso": "2026-10-13T11:00:00Z",
        "status": "AVAILABLE"
    },

    # Dr. Priya Patel (Pediatrics)
    {
        "id": "SLOT_PED_01",
        "doctor_id": "DOC_PED_01",
        "doctor_name": "Dr. Priya Patel",
        "specialty": "Pediatrics",
        "start_time_iso": "2026-10-14T09:00:00Z",
        "end_time_iso": "2026-10-14T09:30:00Z",
        "status": "AVAILABLE"
    },
    {
        "id": "SLOT_PED_02",
        "doctor_id": "DOC_PED_01",
        "doctor_name": "Dr. Priya Patel",
        "specialty": "Pediatrics",
        "start_time_iso": "2026-10-16T15:00:00Z",
        "end_time_iso": "2026-10-16T15:30:00Z",
        "status": "AVAILABLE"
    },

    # Dr. Robert Martinez (Orthopedics)
    {
        "id": "SLOT_ORTH_01",
        "doctor_id": "DOC_ORTH_01",
        "doctor_name": "Dr. Robert Martinez",
        "specialty": "Orthopedics",
        "start_time_iso": "2026-10-14T11:00:00Z",
        "end_time_iso": "2026-10-14T11:30:00Z",
        "status": "BOOKED",
        "booked_patient_name": "David Miller",
        "booked_patient_phone": "+1-555-0182"
    },
    {
        "id": "SLOT_ORTH_02",
        "doctor_id": "DOC_ORTH_01",
        "doctor_name": "Dr. Robert Martinez",
        "specialty": "Orthopedics",
        "start_time_iso": "2026-10-16T14:00:00Z",
        "end_time_iso": "2026-10-16T14:30:00Z",
        "status": "AVAILABLE"
    }
]


def generate_slots_seed() -> List[Dict[str, Any]]:
    """
    Dynamically generates slots starting from TODAY and upcoming days,
    while preserving benchmark scenario reference slots.
    """
    today = date.today()
    today_str = today.isoformat()
    tomorrow_str = (today + timedelta(days=1)).isoformat()

    slots = [
        # ==============================================================
        # IMMEDIATE TODAY SLOTS (Patients can book starting from Today!)
        # ==============================================================
        {
            "id": "SLOT_TODAY_CARD_01",
            "doctor_id": "DOC_CARD_01",
            "doctor_name": "Dr. Sarah Jenkins",
            "specialty": "Cardiology",
            "start_time_iso": f"{today_str}T10:30:00Z",
            "end_time_iso": f"{today_str}T11:00:00Z",
            "status": "AVAILABLE"
        },
        {
            "id": "SLOT_TODAY_CARD_02",
            "doctor_id": "DOC_CARD_01",
            "doctor_name": "Dr. Sarah Jenkins",
            "specialty": "Cardiology",
            "start_time_iso": f"{today_str}T14:30:00Z",
            "end_time_iso": f"{today_str}T15:00:00Z",
            "status": "AVAILABLE"
        },
        {
            "id": "SLOT_TOMORROW_CARD_01",
            "doctor_id": "DOC_CARD_01",
            "doctor_name": "Dr. Sarah Jenkins",
            "specialty": "Cardiology",
            "start_time_iso": f"{tomorrow_str}T11:00:00Z",
            "end_time_iso": f"{tomorrow_str}T11:30:00Z",
            "status": "AVAILABLE"
        },

        # Dr. Michael Chen (Dermatology)
        {
            "id": "SLOT_TODAY_DERM_01",
            "doctor_id": "DOC_DERM_01",
            "doctor_name": "Dr. Michael Chen",
            "specialty": "Dermatology",
            "start_time_iso": f"{today_str}T10:00:00Z",
            "end_time_iso": f"{today_str}T10:30:00Z",
            "status": "AVAILABLE"
        },
        {
            "id": "SLOT_TODAY_DERM_02",
            "doctor_id": "DOC_DERM_01",
            "doctor_name": "Dr. Michael Chen",
            "specialty": "Dermatology",
            "start_time_iso": f"{today_str}T14:00:00Z",
            "end_time_iso": f"{today_str}T14:30:00Z",
            "status": "AVAILABLE"
        },
        {
            "id": "SLOT_TOMORROW_DERM_01",
            "doctor_id": "DOC_DERM_01",
            "doctor_name": "Dr. Michael Chen",
            "specialty": "Dermatology",
            "start_time_iso": f"{tomorrow_str}T09:30:00Z",
            "end_time_iso": f"{tomorrow_str}T10:00:00Z",
            "status": "AVAILABLE"
        },

        # Dr. Priya Patel (Pediatrics)
        {
            "id": "SLOT_TODAY_PED_01",
            "doctor_id": "DOC_PED_01",
            "doctor_name": "Dr. Priya Patel",
            "specialty": "Pediatrics",
            "start_time_iso": f"{today_str}T11:30:00Z",
            "end_time_iso": f"{today_str}T12:00:00Z",
            "status": "AVAILABLE"
        },
        {
            "id": "SLOT_TODAY_PED_02",
            "doctor_id": "DOC_PED_01",
            "doctor_name": "Dr. Priya Patel",
            "specialty": "Pediatrics",
            "start_time_iso": f"{today_str}T15:30:00Z",
            "end_time_iso": f"{today_str}T16:00:00Z",
            "status": "AVAILABLE"
        },
        {
            "id": "SLOT_TOMORROW_PED_01",
            "doctor_id": "DOC_PED_01",
            "doctor_name": "Dr. Priya Patel",
            "specialty": "Pediatrics",
            "start_time_iso": f"{tomorrow_str}T14:00:00Z",
            "end_time_iso": f"{tomorrow_str}T14:30:00Z",
            "status": "AVAILABLE"
        },

        # Dr. Robert Martinez (Orthopedics)
        {
            "id": "SLOT_TODAY_ORTH_01",
            "doctor_id": "DOC_ORTH_01",
            "doctor_name": "Dr. Robert Martinez",
            "specialty": "Orthopedics",
            "start_time_iso": f"{today_str}T13:00:00Z",
            "end_time_iso": f"{today_str}T13:30:00Z",
            "status": "AVAILABLE"
        },
        {
            "id": "SLOT_TODAY_ORTH_02",
            "doctor_id": "DOC_ORTH_01",
            "doctor_name": "Dr. Robert Martinez",
            "specialty": "Orthopedics",
            "start_time_iso": f"{today_str}T16:00:00Z",
            "end_time_iso": f"{today_str}T16:30:00Z",
            "status": "AVAILABLE"
        },
        {
            "id": "SLOT_TOMORROW_ORTH_01",
            "doctor_id": "DOC_ORTH_01",
            "doctor_name": "Dr. Robert Martinez",
            "specialty": "Orthopedics",
            "start_time_iso": f"{tomorrow_str}T10:30:00Z",
            "end_time_iso": f"{tomorrow_str}T11:00:00Z",
            "status": "AVAILABLE"
        },
    ]

    # Preserve reference benchmark slots for evaluation consistency
    existing_keys = {(s["doctor_id"], s["start_time_iso"]) for s in slots}
    for ref_slot in BENCHMARK_REFERENCE_SLOTS:
        if (ref_slot["doctor_id"], ref_slot["start_time_iso"]) not in existing_keys:
            slots.append(ref_slot)

    return slots


SLOTS_SEED = generate_slots_seed()

EXISTING_APPOINTMENTS_SEED = [
    {
        "id": "APT_ORTH_101",
        "patient_name": "David Miller",
        "patient_phone": "+1-555-0182",
        "doctor_id": "DOC_ORTH_01",
        "doctor_name": "Dr. Robert Martinez",
        "specialty": "Orthopedics",
        "slot_iso": "2026-10-14T11:00:00Z",
        "reason": "Knee rehabilitation follow-up",
        "status": "CONFIRMED",
        "session_id": "SEEDED_BENCHMARK_SESSION"
    }
]
