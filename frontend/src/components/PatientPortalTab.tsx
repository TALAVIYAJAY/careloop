"use client";

import React, { useState, useRef, useEffect } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { 
  RotateCcw, 
  AlertTriangle, 
  User, 
  Bot, 
  Calendar, 
  Clock, 
  CheckCircle2, 
  Sparkles, 
  Stethoscope, 
  ShieldCheck, 
  MessageSquare
} from "lucide-react";
import { 
  sendChatMessage, 
  resetChatSession, 
  fetchAvailableSlots,
  PatientSessionState, 
  ToolCallExecution,
  ActiveAppointmentItem
} from "@/lib/api";

interface ChatMessage {
  id: string;
  role: "user" | "agent";
  content: string;
  toolCalls?: ToolCallExecution[];
  emergencyTriggered?: boolean;
  timestamp: string;
}

interface PatientPortalTabProps {
  onDatabaseChange?: () => void;
}

const JAY_USER = {
  fullName: "Jay Talaviya",
  shortName: "Jay",
  phone: "+1-555-0199",
  patientId: "PAT_JAY_001",
};

interface ClinicDoctorItem {
  id: string;
  name: string;
  specialty: string;
  badge: string;
}

const CLINIC_DOCTORS: ClinicDoctorItem[] = [
  { id: "DOC_PED_01", name: "Dr. Priya Patel", specialty: "Pediatrics & Family Medicine", badge: "Primary Care" },
  { id: "DOC_DERM_01", name: "Dr. Michael Chen", specialty: "Dermatology", badge: "Skin / Rash" },
  { id: "DOC_ORTH_01", name: "Dr. Robert Martinez", specialty: "Orthopedics & Sports Medicine", badge: "Joints / Bones" },
  { id: "DOC_CARD_01", name: "Dr. Sarah Jenkins", specialty: "Cardiology", badge: "Heart / Cardio" },
];

const SESSION_ID = "jay-primary-session";
const STORAGE_MESSAGES_KEY = "careloop_jay_messages_v4";
const STORAGE_SESSION_KEY = "careloop_jay_session_v4";

function formatCleanTime(isoStr?: string): string {
  if (!isoStr || isoStr === "None") return "None";
  if (isoStr.includes("T")) {
    const [datePart, timePart] = isoStr.split("T");
    const cleanTime = timePart.substring(0, 5);
    const now = new Date();
    const todayStr = now.toISOString().split("T")[0];
    const tomorrow = new Date(now);
    tomorrow.setDate(tomorrow.getDate() + 1);
    const tomorrowStr = tomorrow.toISOString().split("T")[0];

    if (datePart === todayStr) {
      return `Today (${cleanTime})`;
    } else if (datePart === tomorrowStr) {
      return `Tomorrow (${cleanTime})`;
    }
    return `${datePart} (${cleanTime})`;
  }
  return isoStr;
}

function formatSlotDisplay(isoStr?: string): string {
  if (!isoStr || isoStr === "None") return "None";
  try {
    const dt = new Date(isoStr);
    const now = new Date();
    const todayStr = now.toISOString().split("T")[0];
    const tomorrow = new Date(now);
    tomorrow.setDate(tomorrow.getDate() + 1);
    const tomorrowStr = tomorrow.toISOString().split("T")[0];
    const slotDateStr = isoStr.split("T")[0];
    const timeStr = dt.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

    if (slotDateStr === todayStr) {
      return `Today at ${timeStr}`;
    } else if (slotDateStr === tomorrowStr) {
      return `Tomorrow at ${timeStr}`;
    }
    const dayName = dt.toLocaleDateString([], { weekday: "short", month: "short", day: "numeric" });
    return `${dayName} at ${timeStr}`;
  } catch (_) {
    return isoStr;
  }
}

const INITIAL_WELCOME_MESSAGE: ChatMessage = {
  id: "welcome-msg",
  role: "agent",
  content: `Hello **${JAY_USER.shortName}**! Welcome to **CareLoop Health Clinic**.\n\nI am Sarah, your AI Medical Receptionist. Your verified medical chart (**${JAY_USER.patientId}**, phone **${JAY_USER.phone}**) is already active in our system.\n\nHow can I help you today? You can check open doctor schedules, book or reschedule appointments across specialties, or ask questions about symptoms.`,
  timestamp: "Just now",
};

const INITIAL_SESSION_STATE: PatientSessionState = {
  patient_name: JAY_USER.fullName,
  patient_phone: JAY_USER.phone,
  patient_id: JAY_USER.patientId,
  active_doctor_name: "None Selected",
  selected_slot: "None",
  triage_level: "ROUTINE",
  emergency_triggered: false,
  active_appointments: [],
};

export const PatientPortalTab: React.FC<PatientPortalTabProps> = ({ onDatabaseChange }) => {
  // -------------------------------------------------------------
  // SINGLE UNIFIED CHAT SESSION FOR JAY TALAVIYA
  // -------------------------------------------------------------
  const [messages, setMessages] = useState<ChatMessage[]>(() => {
    if (typeof window !== "undefined") {
      try {
        const saved = localStorage.getItem(STORAGE_MESSAGES_KEY);
        if (saved) {
          const parsed = JSON.parse(saved);
          if (Array.isArray(parsed) && parsed.length > 0) return parsed;
        }
      } catch (e) {
        console.warn("Could not read messages from localStorage:", e);
      }
    }
    return [INITIAL_WELCOME_MESSAGE];
  });

  const [sessionState, setSessionState] = useState<PatientSessionState>(() => {
    if (typeof window !== "undefined") {
      try {
        const saved = localStorage.getItem(STORAGE_SESSION_KEY);
        if (saved) {
          const parsed = JSON.parse(saved);
          if (parsed && typeof parsed === "object") return parsed;
        }
      } catch (e) {
        console.warn("Could not read sessionState from localStorage:", e);
      }
    }
    return INITIAL_SESSION_STATE;
  });

  const [isSending, setIsSending] = useState(false);
  const chatEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll chat to bottom when messages update
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isSending]);

  // Persist messages and sessionState to localStorage
  useEffect(() => {
    if (typeof window !== "undefined") {
      try {
        localStorage.setItem(STORAGE_MESSAGES_KEY, JSON.stringify(messages));
        localStorage.setItem(STORAGE_SESSION_KEY, JSON.stringify(sessionState));
      } catch (e) {
        console.warn("Could not persist chat state:", e);
      }
    }
  }, [messages, sessionState]);

  // Listen for complete system factory reset event dispatched from Receptionist tab
  useEffect(() => {
    const handleSystemReset = () => {
      setMessages([INITIAL_WELCOME_MESSAGE]);
      setSessionState(INITIAL_SESSION_STATE);
      if (typeof window !== "undefined") {
        try {
          localStorage.removeItem(STORAGE_MESSAGES_KEY);
          localStorage.removeItem(STORAGE_SESSION_KEY);
        } catch (_) {}
      }
      if (onDatabaseChange) onDatabaseChange();
    };

    window.addEventListener("careloop:complete-system-reset", handleSystemReset);
    return () => {
      window.removeEventListener("careloop:complete-system-reset", handleSystemReset);
    };
  }, [onDatabaseChange]);

  // Reset the single chat session cleanly
  const handleResetChat = async () => {
    if (!window.confirm("Are you sure you want to clear chat history and reset this conversation?")) return;
    try {
      await resetChatSession(SESSION_ID);
    } catch (_) {}

    setMessages([INITIAL_WELCOME_MESSAGE]);
    setSessionState(INITIAL_SESSION_STATE);

    if (typeof window !== "undefined") {
      localStorage.removeItem(STORAGE_MESSAGES_KEY);
      localStorage.removeItem(STORAGE_SESSION_KEY);
    }
    if (onDatabaseChange) onDatabaseChange();
  };

  // Interactive Physician & Slot Selection State
  const [selectedDoctorId, setSelectedDoctorId] = useState<string>("DOC_PED_01");
  const [doctorSlots, setDoctorSlots] = useState<any[]>([]);
  const [selectedSlotIso, setSelectedSlotIso] = useState<string>("");
  const [isLoadingSlots, setIsLoadingSlots] = useState<boolean>(false);

  const loadDoctorSlots = async (docId?: string) => {
    const targetDocId = docId || selectedDoctorId;
    const doc = CLINIC_DOCTORS.find((d) => d.id === targetDocId);
    if (!doc) return;
    setIsLoadingSlots(true);
    try {
      const slots = await fetchAvailableSlots(undefined, doc.name);
      setDoctorSlots(slots);
      if (slots.length > 0) {
        setSelectedSlotIso((prev) => (slots.some((s: any) => s.start_time_iso === prev) ? prev : slots[0].start_time_iso));
      } else {
        setSelectedSlotIso("");
      }
    } catch (e) {
      console.warn("Could not load available doctor slots:", e);
    } finally {
      setIsLoadingSlots(false);
    }
  };

  useEffect(() => {
    loadDoctorSlots(selectedDoctorId);
  }, [selectedDoctorId]);

  useEffect(() => {
    const handleSync = () => {
      loadDoctorSlots(selectedDoctorId);
    };
    window.addEventListener("careloop:db-sync", handleSync);
    window.addEventListener("careloop:complete-system-reset", handleSync);
    return () => {
      window.removeEventListener("careloop:db-sync", handleSync);
      window.removeEventListener("careloop:complete-system-reset", handleSync);
    };
  }, [selectedDoctorId]);

  // Execute clinical action through Clinical Orchestrator
  const handleSendChatMessage = async (
    textToSend: string,
    slotIso?: string,
    doctorId?: string,
    doctorName?: string
  ) => {
    const trimmed = textToSend.trim();
    if (!trimmed || isSending) return;

    // Clean user message display (strip [ISO: ...] if present for display)
    const cleanUserContent = trimmed.replace(/\s*\[[\w\:\-\.]+\]/g, "");

    const userMsg: ChatMessage = {
      id: `u-${Date.now()}`,
      role: "user",
      content: cleanUserContent,
      timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    };

    setMessages((prev) => [...prev, userMsg]);
    setIsSending(true);

    try {
      const resp = await sendChatMessage(
        SESSION_ID,
        trimmed,
        JAY_USER.fullName,
        JAY_USER.phone,
        JAY_USER.patientId,
        slotIso,
        doctorId,
        doctorName
      );

      const agentMsg: ChatMessage = {
        id: `a-${Date.now()}`,
        role: "agent",
        content: resp.response,
        toolCalls: resp.recent_tool_calls,
        emergencyTriggered: resp.emergency_triggered,
        timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      };

      setMessages((prev) => [...prev, agentMsg]);

      if (resp.session) {
        setSessionState((prev) => ({
          ...prev,
          patient_name: resp.session.patient_name || prev.patient_name,
          patient_phone: resp.session.patient_phone || prev.patient_phone,
          patient_id: resp.session.patient_id || prev.patient_id,
          active_doctor_name: resp.session.active_doctor_name || prev.active_doctor_name,
          selected_slot: resp.session.selected_slot || prev.selected_slot,
          appointment_id: resp.session.appointment_id || prev.appointment_id,
          triage_level: resp.session.triage_level || "ROUTINE",
          emergency_triggered: resp.session.emergency_triggered || false,
          active_appointments: resp.session.active_appointments || prev.active_appointments || [],
        }));
      }

      if (onDatabaseChange) {
        onDatabaseChange();
      }
      if (typeof window !== "undefined") {
        window.dispatchEvent(new Event("careloop:db-sync"));
      }
    } catch (err: any) {
      console.error("Error communicating with Clinical Orchestrator:", err);
      const errMsg: ChatMessage = {
        id: `err-${Date.now()}`,
        role: "agent",
        content: "⚠️ An issue occurred communicating with the clinic server. Please check connection and try again.",
        timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      };
      setMessages((prev) => [...prev, errMsg]);
    } finally {
      setIsSending(false);
      loadDoctorSlots(selectedDoctorId);
    }
  };

  const handleBookSelectedSlot = () => {
    const doc = CLINIC_DOCTORS.find((d) => d.id === selectedDoctorId);
    const chosenSlot = doctorSlots.find((s) => s.start_time_iso === selectedSlotIso);
    if (!doc || !chosenSlot) return;
    const timeLabel = formatSlotDisplay(chosenSlot.start_time_iso);
    const prompt = `Please schedule an appointment with ${doc.name} for ${timeLabel} [${chosenSlot.start_time_iso}] for patient Jay Talaviya.`;
    handleSendChatMessage(prompt, chosenSlot.start_time_iso, doc.id, doc.name);
  };

  const handleRescheduleSelectedSlot = () => {
    const doc = CLINIC_DOCTORS.find((d) => d.id === selectedDoctorId);
    const chosenSlot = doctorSlots.find((s) => s.start_time_iso === selectedSlotIso);
    if (!doc || !chosenSlot) return;
    const timeLabel = formatSlotDisplay(chosenSlot.start_time_iso);
    const prompt = `Please reschedule my appointment with ${doc.name} to ${timeLabel} [${chosenSlot.start_time_iso}].`;
    handleSendChatMessage(prompt, chosenSlot.start_time_iso, doc.id, doc.name);
  };

  const bookedAppointments = sessionState.active_appointments || [];

  return (
    <div className="h-full flex flex-col gap-2 overflow-hidden w-full">
      
      {/* ========================================================= */}
      {/* TOP BAR: JAY'S PROFILE & VERIFIED CREDENTIALS */}
      {/* ========================================================= */}
      <div className="bg-white border border-slate-200/80 rounded-2xl p-2 px-3 sm:px-4 shadow-2xs flex items-center justify-between gap-2 shrink-0">
        
        {/* PATIENT IDENTITY BADGE (JAY TALAVIYA) */}
        <div className="flex items-center space-x-2.5">
          <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-teal-600 to-indigo-600 flex items-center justify-center text-white font-bold text-xs shadow-xs">
            JT
          </div>
          <div>
            <div className="flex items-center space-x-1.5">
              <span className="text-xs font-bold text-slate-900 tracking-tight">{JAY_USER.fullName}</span>
              <span className="px-1.5 py-0.2 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200 text-[9px] font-bold">
                Verified Patient
              </span>
            </div>
            <div className="flex items-center space-x-2 text-[10px] text-slate-500 font-mono">
              <span>MPI: {JAY_USER.patientId}</span>
              <span>•</span>
              <span>{JAY_USER.phone}</span>
            </div>
          </div>
        </div>

        {/* RESET BUTTON */}
        <button
          onClick={handleResetChat}
          title="Clear all messages and start fresh"
          className="px-2.5 py-1 rounded-lg text-xs font-semibold bg-slate-100 hover:bg-red-50 hover:text-red-700 text-slate-600 border border-slate-200 transition flex items-center space-x-1.5"
        >
          <RotateCcw className="w-3 h-3" />
          <span>Reset Chat</span>
        </button>

      </div>

      {/* ========================================================= */}
      {/* MAIN TWO-COLUMN WORKSPACE: CHAT STREAM + PATIENT CARE PANEL */}
      {/* ========================================================= */}
      <div className="flex-1 min-h-0 grid grid-cols-1 lg:grid-cols-4 gap-2.5 overflow-hidden">
        
        {/* CHAT STREAM (COLUMNS 1-3) */}
        <div className="lg:col-span-3 bg-white border border-slate-200/80 rounded-2xl flex flex-col h-full shadow-xs overflow-hidden">
          
          {/* CHAT HEADER */}
          <div className="px-3.5 py-2 border-b border-slate-100 flex items-center justify-between bg-slate-50/70 shrink-0">
            <div className="flex items-center space-x-2.5">
              <div className="w-6 h-6 rounded-full bg-teal-600 flex items-center justify-center text-white font-bold text-[10px]">
                SL
              </div>
              <div className="flex items-center space-x-2">
                <span className="text-xs font-bold text-slate-900">Sarah</span>
                <span className="text-slate-300 text-xs">•</span>
                <span className="text-[11px] text-teal-700 font-medium">AI Medical Receptionist</span>
              </div>
            </div>

            <div className="flex items-center space-x-2">
              <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
              <span className="text-[10px] font-semibold text-slate-500">Live Active</span>
            </div>
          </div>

          {/* SCROLLABLE CHAT MESSAGES */}
          <div className="flex-1 min-h-0 overflow-y-auto p-3.5 sm:p-4 space-y-3">
            {messages.map((msg) => (
              <div
                key={msg.id}
                className={`flex items-start space-x-2.5 ${msg.role === "user" ? "flex-row-reverse space-x-reverse" : "flex-row"}`}
              >
                <div
                  className={`w-6 h-6 rounded-full flex items-center justify-center shrink-0 text-xs font-bold ${
                    msg.role === "user" ? "bg-slate-900 text-white" : "bg-teal-600 text-white"
                  }`}
                >
                  {msg.role === "user" ? <User className="w-3 h-3" /> : <Bot className="w-3 h-3" />}
                </div>

                <div className="max-w-[85%] sm:max-w-[78%] space-y-1.5">
                  <div
                    className={`p-3 rounded-2xl text-xs sm:text-[13px] leading-relaxed shadow-2xs ${
                      msg.role === "user"
                        ? "bg-slate-900 text-white rounded-tr-none font-normal"
                        : msg.emergencyTriggered
                        ? "bg-red-50 text-red-950 border border-red-200 rounded-tl-none"
                        : "bg-slate-100 text-slate-900 rounded-tl-none font-normal"
                    }`}
                  >
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.content}</ReactMarkdown>
                  </div>

                  {/* TOOL CALLS EXECUTION CHIPS */}
                  {msg.toolCalls && msg.toolCalls.length > 0 && (
                    <div className="flex flex-wrap gap-1 pt-0.5">
                      {msg.toolCalls.map((tc, idx) => (
                        <span
                          key={idx}
                          className="inline-flex items-center space-x-1 px-1.5 py-0.5 rounded-md bg-teal-50 border border-teal-200/80 text-[10px] font-mono text-teal-800"
                        >
                          <CheckCircle2 className="w-2.5 h-2.5 text-teal-600" />
                          <span>{tc.tool_name}</span>
                        </span>
                      ))}
                    </div>
                  )}

                  {/* CLINICAL EMERGENCY PREEMPTION ALERT (ONLY ON EMERGENCY MESSAGES) */}
                  {msg.emergencyTriggered && (
                    <div className="p-2.5 bg-red-100/90 border border-red-200 rounded-xl text-red-900 text-xs flex items-start space-x-2">
                      <AlertTriangle className="w-4 h-4 text-red-600 shrink-0 mt-0.5" />
                      <div>
                        <strong className="block font-bold">EMERGENCY PROTOCOL ENGAGED</strong>
                        Outpatient scheduling has been preempted. Dial 911 or proceed immediately to the nearest Emergency Room.
                      </div>
                    </div>
                  )}

                  <span className="text-[9px] text-slate-400 block px-1">
                    {msg.timestamp}
                  </span>
                </div>
              </div>
            ))}

            {isSending && (
              <div className="flex items-center space-x-2 text-xs text-slate-400 italic pl-8">
                <div className="flex space-x-1">
                  <div className="w-1.5 h-1.5 bg-teal-600 rounded-full animate-bounce"></div>
                  <div className="w-1.5 h-1.5 bg-teal-600 rounded-full animate-bounce [animation-delay:0.2s]"></div>
                  <div className="w-1.5 h-1.5 bg-teal-600 rounded-full animate-bounce [animation-delay:0.4s]"></div>
                </div>
                <span>Sarah is checking clinic schedule & evaluating symptoms...</span>
              </div>
            )}

            <div ref={chatEndRef} />
          </div>

          {/* INTERACTIVE PHYSICIAN & SLOT BOOKING CONSOLE */}
          <div className="p-2.5 sm:p-3 border-t border-slate-200/90 bg-slate-50/70 space-y-2 shrink-0">
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-bold text-slate-800 flex items-center space-x-1.5 uppercase tracking-wider">
                <Sparkles className="w-3.5 h-3.5 text-teal-600" />
                <span>Physician & Slot Action Console</span>
              </span>
              <span className="text-[10px] bg-teal-100/70 text-teal-800 px-2 py-0.5 rounded-full font-semibold border border-teal-200">
                100% EHR Synced • Zero Typos
              </span>
            </div>

            {/* DYNAMIC PHYSICIAN & AVAILABLE SLOT SELECTOR CARD */}
            <div className="bg-white p-2.5 rounded-xl border border-slate-200 shadow-2xs space-y-2">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                {/* DOCTOR DROPDOWN */}
                <div>
                  <label className="block text-[10px] font-bold text-slate-600 uppercase tracking-wide mb-1 flex items-center space-x-1">
                    <Stethoscope className="w-3 h-3 text-teal-600" />
                    <span>1. Select Physician</span>
                  </label>
                  <select
                    value={selectedDoctorId}
                    disabled={isSending}
                    onChange={(e) => setSelectedDoctorId(e.target.value)}
                    className="w-full text-xs font-semibold bg-slate-50 border border-slate-300 rounded-lg p-1.5 text-slate-900 focus:outline-none focus:ring-1 focus:ring-teal-500 cursor-pointer"
                  >
                    {CLINIC_DOCTORS.map((d) => (
                      <option key={d.id} value={d.id}>
                        {d.name} — {d.specialty}
                      </option>
                    ))}
                  </select>
                </div>

                {/* AVAILABLE SLOTS DROPDOWN */}
                <div>
                  <label className="block text-[10px] font-bold text-slate-600 uppercase tracking-wide mb-1 flex items-center justify-between">
                    <span className="flex items-center space-x-1">
                      <Clock className="w-3 h-3 text-teal-600" />
                      <span>2. Available Open Slots</span>
                    </span>
                    <span className="text-[9px] font-semibold text-teal-700 bg-teal-50 px-1.5 rounded border border-teal-200">
                      {isLoadingSlots ? "Refreshing..." : `${doctorSlots.length} open`}
                    </span>
                  </label>
                  <select
                    value={selectedSlotIso}
                    disabled={isSending || doctorSlots.length === 0}
                    onChange={(e) => setSelectedSlotIso(e.target.value)}
                    className="w-full text-xs font-semibold bg-slate-50 border border-slate-300 rounded-lg p-1.5 text-slate-900 focus:outline-none focus:ring-1 focus:ring-teal-500 cursor-pointer disabled:bg-slate-100 disabled:text-slate-400"
                  >
                    {doctorSlots.length === 0 ? (
                      <option value="">No open slots currently available</option>
                    ) : (
                      doctorSlots.map((s) => (
                        <option key={s.id || s.start_time_iso} value={s.start_time_iso}>
                          {formatSlotDisplay(s.start_time_iso)} ({s.specialty || "Clinic"})
                        </option>
                      ))
                    )}
                  </select>
                </div>
              </div>

              {/* ACTION BUTTONS: BOOK, RESCHEDULE, CANCEL */}
              <div className="grid grid-cols-3 gap-2 pt-1 border-t border-slate-100">
                <button
                  type="button"
                  disabled={isSending || !selectedSlotIso || doctorSlots.length === 0}
                  onClick={handleBookSelectedSlot}
                  className="px-2.5 py-1.5 rounded-lg bg-teal-600 hover:bg-teal-700 active:scale-[0.98] text-white font-bold text-xs flex items-center justify-center space-x-1.5 transition shadow-2xs disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  <Calendar className="w-3.5 h-3.5" />
                  <span>Book Slot</span>
                </button>

                <button
                  type="button"
                  disabled={isSending || !selectedSlotIso || doctorSlots.length === 0 || bookedAppointments.length === 0}
                  onClick={handleRescheduleSelectedSlot}
                  title={bookedAppointments.length === 0 ? "You do not have an active booking to reschedule" : "Move active appointment to selected slot"}
                  className="px-2.5 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-700 active:scale-[0.98] text-white font-bold text-xs flex items-center justify-center space-x-1.5 transition shadow-2xs disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  <RotateCcw className="w-3.5 h-3.5" />
                  <span>Reschedule</span>
                </button>

                <button
                  type="button"
                  disabled={isSending || bookedAppointments.length === 0}
                  onClick={() => handleSendChatMessage("Please cancel my confirmed appointment.")}
                  title={bookedAppointments.length === 0 ? "No active appointments to cancel" : "Cancel active appointment atomically"}
                  className="px-2.5 py-1.5 rounded-lg bg-rose-600 hover:bg-rose-700 active:scale-[0.98] text-white font-bold text-xs flex items-center justify-center space-x-1.5 transition shadow-2xs disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  <span>Cancel Visit</span>
                </button>
              </div>
            </div>

            {/* QUICK PROTOCOL AND CONVENIENCE BUTTONS */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-1.5 pt-0.5">
              <button
                type="button"
                disabled={isSending}
                onClick={() => handleSendChatMessage("I am having a low fever and cold symptoms. Please recommend a doctor.")}
                className="p-1.5 px-2 rounded-lg text-left bg-white hover:bg-amber-50 text-amber-950 border border-amber-200/80 transition flex items-center justify-between text-[11px] font-semibold disabled:opacity-50"
              >
                <span>🌡️ Report Fever</span>
                <span className="text-[9px] bg-amber-100 text-amber-900 px-1 rounded font-mono">Triage</span>
              </button>

              <button
                type="button"
                disabled={isSending}
                onClick={() => handleSendChatMessage("I'm experiencing severe crushing chest pain radiating to my left arm and shortness of breath!")}
                className="p-1.5 px-2 rounded-lg text-left bg-white hover:bg-red-50 text-red-950 border border-red-200/80 transition flex items-center justify-between text-[11px] font-semibold disabled:opacity-50"
              >
                <span>🚨 911 Emergency</span>
                <span className="text-[9px] bg-red-100 text-red-900 px-1 rounded font-mono">Preempt</span>
              </button>

              <button
                type="button"
                disabled={isSending}
                onClick={() => handleSendChatMessage("Can you prescribe me Amoxicillin 500mg for a bacterial infection?")}
                className="p-1.5 px-2 rounded-lg text-left bg-white hover:bg-purple-50 text-purple-950 border border-purple-200/80 transition flex items-center justify-between text-[11px] font-semibold disabled:opacity-50"
              >
                <span>💊 Rx Request</span>
                <span className="text-[9px] bg-purple-100 text-purple-900 px-1 rounded font-mono">Scope</span>
              </button>

              <button
                type="button"
                disabled={isSending}
                onClick={() => handleSendChatMessage("What appointments do I currently have scheduled on file?")}
                className="p-1.5 px-2 rounded-lg text-left bg-white hover:bg-emerald-50 text-emerald-950 border border-emerald-200/80 transition flex items-center justify-between text-[11px] font-semibold disabled:opacity-50"
              >
                <span>📋 My Bookings</span>
                <span className="text-[9px] bg-emerald-100 text-emerald-900 px-1 rounded font-mono">EHR</span>
              </button>
            </div>
          </div>

        </div>

        {/* SIDEBAR: PATIENT STATE + MULTI-APPOINTMENT CARE PLAN + QUICK TESTING (COLUMN 4) */}
        <div className="lg:col-span-1 flex flex-col gap-2 h-full overflow-y-auto pr-0.5">
          
          {/* CURRENT INTAKE STATE */}
          <div className="bg-white border border-slate-200/80 rounded-2xl p-3 shadow-2xs space-y-2 shrink-0">
            <div className="flex items-center justify-between border-b border-slate-100 pb-1.5">
              <h3 className="text-[11px] font-bold text-slate-900 uppercase tracking-wider">
                Jay&apos;s Intake State
              </h3>
              <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${
                sessionState.triage_level === "EMERGENCY_ESCALATED" ? "bg-red-100 text-red-700" :
                sessionState.triage_level === "CONFIRMED" ? "bg-emerald-100 text-emerald-700" :
                "bg-slate-100 text-slate-700"
              }`}>
                {sessionState.triage_level}
              </span>
            </div>

            <div className="space-y-1.5 text-xs">
              <div className="bg-slate-50 p-2 rounded-lg border border-slate-100 flex justify-between items-center">
                <span className="text-[10px] text-slate-400 font-semibold">PATIENT</span>
                <span className="font-semibold text-slate-800 text-[11px]">
                  {JAY_USER.fullName}
                </span>
              </div>

              <div className="bg-slate-50 p-2 rounded-lg border border-slate-100 flex justify-between items-center">
                <span className="text-[10px] text-slate-400 font-semibold">LAST PHYSICIAN</span>
                <span className="font-semibold text-slate-800 text-[11px]">
                  {sessionState.active_doctor_name || "None Selected"}
                </span>
              </div>

              <div className="bg-slate-50 p-2 rounded-lg border border-slate-100 flex justify-between items-center">
                <span className="text-[10px] text-slate-400 font-semibold">LAST SLOT</span>
                <span className="font-mono text-[11px] text-teal-700 font-semibold">
                  {formatCleanTime(sessionState.selected_slot)}
                </span>
              </div>
            </div>

            {/* MULTI-APPOINTMENT BOOKING LEDGER */}
            <div className="mt-2.5 pt-2 border-t border-slate-100 space-y-1.5">
              <div className="flex items-center justify-between">
                <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider flex items-center space-x-1">
                  <Calendar className="w-3 h-3 text-teal-600" />
                  <span>Booked in this Chat ({bookedAppointments.length})</span>
                </span>
                {bookedAppointments.length > 1 && (
                  <span className="text-[9px] bg-purple-50 text-purple-700 font-bold px-1.5 py-0.2 rounded border border-purple-200">
                    Multi-Booking
                  </span>
                )}
              </div>

              {bookedAppointments.length === 0 ? (
                <div className="p-2.5 text-center text-[10px] text-slate-400 bg-slate-50 rounded-lg border border-dashed border-slate-200">
                  No appointments booked in this chat yet.
                </div>
              ) : (
                <div className="space-y-1.5 max-h-36 overflow-y-auto">
                  {bookedAppointments.map((a, idx) => (
                    <div key={a.id || idx} className="p-2 bg-emerald-50/60 rounded-lg border border-emerald-200/80 text-[10px] space-y-0.5">
                      <div className="flex items-center justify-between font-bold text-emerald-950">
                        <span>{a.doctor_name}</span>
                        <span className="text-[9px] font-mono text-emerald-700 bg-white px-1 rounded border border-emerald-200">
                          {a.id}
                        </span>
                      </div>
                      <div className="flex items-center justify-between text-emerald-800 text-[10px] font-medium">
                        <span>{a.specialty || "Outpatient Care"}</span>
                        <span className="font-mono font-semibold">{formatCleanTime(a.slot_iso)}</span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* ACTIVE CLINICAL GUARDRAILS */}
          <div className="bg-teal-50/70 border border-teal-200/60 rounded-2xl p-2.5 text-[10px] text-teal-900 space-y-1 shrink-0">
            <div className="flex items-center space-x-1 font-bold text-teal-800">
              <ShieldCheck className="w-3 h-3 text-teal-600" />
              <span>Multi-Agent Safety Guardrails</span>
            </div>
            <p className="leading-tight text-slate-600">
              Deterministic 911 preemption by Triage Sub-Agent. Strict HIPAA identity verification & prescription defense by Compliance Sub-Agent.
            </p>
          </div>

        </div>

      </div>

    </div>
  );
};
