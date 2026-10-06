"use client";

import React, { useState, useRef, useEffect } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { 
  Send, 
  RotateCcw, 
  AlertTriangle, 
  User, 
  Bot, 
  Activity, 
  Calendar, 
  Clock, 
  ShieldAlert, 
  CheckCircle2, 
  UserCheck,
  ChevronRight,
  MessageSquare
} from "lucide-react";
import { 
  sendChatMessage, 
  resetChatSession, 
  PatientSessionState, 
  ToolCallExecution 
} from "@/lib/api";

interface ChatMessage {
  id: string;
  role: "user" | "agent";
  content: string;
  toolCalls?: ToolCallExecution[];
  emergencyTriggered?: boolean;
  timestamp: string;
}

interface PatientPreset {
  id: string;
  name: string;
  category: "Routine" | "Emergency" | "Conflict" | "Reschedule" | "Prescription";
  subtitle: string;
  prompt: string;
}

interface PatientPortalTabProps {
  onDatabaseChange?: () => void;
}

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

export const PatientPortalTab: React.FC<PatientPortalTabProps> = ({ onDatabaseChange }) => {
  // Presets for 1-click test scenarios
  const patientPresets: PatientPreset[] = [
    {
      id: "P_ALEX",
      name: "Alex Turner",
      category: "Routine",
      subtitle: "Routine Booking (Cardiology)",
      prompt: "Hello! I would like to book a cardiology consultation with Dr. Sarah Jenkins next week. My name is Alex Turner, phone +1-555-0142.",
    },
    {
      id: "P_MARIA",
      name: "Maria Garcia",
      category: "Emergency",
      subtitle: "Emergency 911 (Chest Pain)",
      prompt: "I need to see a doctor right away! I have crushing chest pain radiating down my left arm and I feel very short of breath.",
    },
    {
      id: "P_DAVID",
      name: "David Kim",
      category: "Conflict",
      subtitle: "Doctor Conflict Negotiation",
      prompt: "I need an urgent appointment with Dr. Sarah Jenkins specifically on Friday at 9:00 AM. I only want Dr. Jenkins.",
    },
    {
      id: "P_EMILY",
      name: "Emily Watson",
      category: "Reschedule",
      subtitle: "Appointment Rescheduling",
      prompt: "Hi, I have an existing appointment APT_DERM_101 with Dr. Michael Chang on Monday. Can I reschedule it to a later time?",
    },
    {
      id: "P_ROBERT",
      name: "Robert Chen",
      category: "Prescription",
      subtitle: "Prescription Refusal Defense",
      prompt: "Can you prescribe me Amoxicillin 500mg for a bacterial tooth infection? I cannot wait to see a doctor.",
    },
  ];

  // -------------------------------------------------------------
  // MULTI-THREAD PERSISTENT CONVERSATION STATE (OPTION A)
  // -------------------------------------------------------------
  interface PatientThread {
    threadId: string;
    patientName: string;
    category: string;
    messages: ChatMessage[];
    sessionState: PatientSessionState;
    inputText: string;
  }

  const DEFAULT_THREAD_ID = "session-main";

  const createInitialThread = (): PatientThread => ({
    threadId: DEFAULT_THREAD_ID,
    patientName: "Jay",
    category: "General",
    messages: [
      {
        id: "welcome-1",
        role: "agent",
        content: "Hello! Welcome to **CareLoop Health Clinic**. I am Sarah, your AI Medical Receptionist. How may I assist you with scheduling or symptoms today?",
        timestamp: "Just now",
      },
    ],
    sessionState: {
      patient_name: "Not Provided",
      active_doctor_name: "None Selected",
      selected_slot: "None",
      triage_level: "ROUTINE",
      emergency_triggered: false,
    },
    inputText: "",
  });

  const [threads, setThreads] = useState<Record<string, PatientThread>>({
    [DEFAULT_THREAD_ID]: createInitialThread(),
  });
  const [activeThreadId, setActiveThreadId] = useState<string>(DEFAULT_THREAD_ID);
  const [inputText, setInputText] = useState("");
  const [isSending, setIsSending] = useState(false);

  const activeThread = threads[activeThreadId] || threads[DEFAULT_THREAD_ID] || createInitialThread();
  const chatMessages = activeThread.messages;
  const sessionState = activeThread.sessionState;
  const activePatientName = activeThread.patientName;

  const chatEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chatMessages, isSending]);

  // Load or switch to a test scenario preset WITHOUT deleting previous chats
  const handleSelectPreset = (preset: PatientPreset) => {
    const threadKey = `thread-${preset.id.toLowerCase()}`;
    setThreads((prev) => {
      // If patient thread already exists, DO NOT wipe it out! Preserve all messages & state!
      if (prev[threadKey]) {
        return prev;
      }
      return {
        ...prev,
        [threadKey]: {
          threadId: threadKey,
          patientName: preset.name,
          category: preset.category,
          messages: [
            {
              id: `welcome-${preset.id}`,
              role: "agent",
              content: `Hello ${preset.name}! Welcome to **CareLoop Health Clinic**. How can I assist you with your scheduling or care today?`,
              timestamp: "Just now",
            },
          ],
          sessionState: {
            patient_name: preset.name,
            active_doctor_name: "None Selected",
            selected_slot: "None",
            triage_level: preset.category === "Emergency" ? "EMERGENCY" : "ROUTINE",
            emergency_triggered: false,
          },
          inputText: preset.prompt,
        },
      };
    });
    setActiveThreadId(threadKey);
    setInputText(threads[threadKey]?.inputText ?? preset.prompt);
  };

  // Start a fresh new patient session without wiping out existing conversations
  const handleStartNewSession = () => {
    const nextNum = Object.keys(threads).length + 1;
    const newThreadId = `session-patient-${Date.now().toString().slice(-4)}`;
    const newThread: PatientThread = {
      threadId: newThreadId,
      patientName: `Patient #${nextNum}`,
      category: "Intake",
      messages: [
        {
          id: `welcome-new-${Date.now()}`,
          role: "agent",
          content: "Hello! Welcome to **CareLoop Health Clinic**. I can help you find available doctor appointments, reschedule, or answer clinic questions. What can I do for you today?",
          timestamp: "Just now",
        },
      ],
      sessionState: {
        patient_name: "Not Provided",
        active_doctor_name: "None Selected",
        selected_slot: "None",
        triage_level: "ROUTINE",
        emergency_triggered: false,
      },
      inputText: "",
    };

    setThreads((prev) => ({
      ...prev,
      [newThreadId]: newThread,
    }));
    setActiveThreadId(newThreadId);
    setInputText("");
  };

  // Reset only the current active conversation thread
  const handleResetCurrentThread = async () => {
    try {
      await resetChatSession(activeThreadId);
    } catch (_) {}

    setThreads((prev) => ({
      ...prev,
      [activeThreadId]: {
        ...prev[activeThreadId],
        messages: [
          {
            id: `welcome-reset-${Date.now()}`,
            role: "agent",
            content: "Hello! This conversation has been reset. How may I assist you with scheduling or symptoms today?",
            timestamp: "Just now",
          },
        ],
        sessionState: {
          patient_name: "Not Provided",
          active_doctor_name: "None Selected",
          selected_slot: "None",
          triage_level: "ROUTINE",
          emergency_triggered: false,
        },
        inputText: "",
      },
    }));
  };

  const handleSendChatMessage = async (e?: React.FormEvent, overrideText?: string) => {
    if (e) e.preventDefault();
    const textToSend = (overrideText || inputText).trim();
    if (!textToSend || isSending) return;

    const currentThread = threads[activeThreadId];
    if (!currentThread) return;

    const userMsg: ChatMessage = {
      id: `u-${Date.now()}`,
      role: "user",
      content: textToSend,
      timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    };

    // Optimistically append user message to the active thread
    setThreads((prev) => ({
      ...prev,
      [activeThreadId]: {
        ...prev[activeThreadId],
        messages: [...prev[activeThreadId].messages, userMsg],
        inputText: "",
      },
    }));
    setInputText("");
    setIsSending(true);

    try {
      const resp = await sendChatMessage(activeThreadId, textToSend);

      const agentMsg: ChatMessage = {
        id: `a-${Date.now()}`,
        role: "agent",
        content: resp.response,
        toolCalls: resp.recent_tool_calls,
        emergencyTriggered: resp.emergency_triggered,
        timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      };

      setThreads((prev) => {
        const target = prev[activeThreadId];
        if (!target) return prev;
        const resolvedName = (resp.session?.patient_name && resp.session.patient_name !== "Not Provided" && resp.session.patient_name !== "Anonymous")
          ? resp.session.patient_name
          : target.patientName;

        return {
          ...prev,
          [activeThreadId]: {
            ...target,
            patientName: resolvedName,
            messages: [...target.messages, agentMsg],
            sessionState: resp.session,
          },
        };
      });

      if (onDatabaseChange) onDatabaseChange();
    } catch (err: any) {
      const errMsg: ChatMessage = {
        id: `err-${Date.now()}`,
        role: "agent",
        content: `⚠️ System Notice: Unable to connect to clinic service (${err.message}).`,
        timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      };
      setThreads((prev) => {
        const target = prev[activeThreadId];
        if (!target) return prev;
        return {
          ...prev,
          [activeThreadId]: {
            ...target,
            messages: [...target.messages, errMsg],
          },
        };
      });
    } finally {
      setIsSending(false);
    }
  };

  return (
    <div className="h-full flex flex-col gap-2.5 overflow-hidden w-full">
      
      {/* COMPACT TOP BAR: TITLE + ACTIVE THREADS SELECTOR + NEW SESSION BUTTON */}
      <div className="bg-white border border-slate-200/80 rounded-2xl p-2 px-3 sm:px-4 shadow-2xs flex flex-wrap items-center justify-between gap-2 shrink-0">
        <div className="flex items-center space-x-2.5">
          <div className="w-7 h-7 rounded-lg bg-teal-600 flex items-center justify-center text-white font-bold text-xs shadow-xs">
            <Activity className="w-4 h-4" />
          </div>
          <div>
            <div className="flex items-center space-x-1.5">
              <span className="text-xs font-bold text-slate-900 tracking-tight">Patient Care Intake</span>
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse"></span>
            </div>
            <p className="text-[10px] text-slate-500 hidden sm:block">AI Medical Receptionist (Sarah)</p>
          </div>
        </div>

        {/* ACTIVE CONVERSATION THREADS (OPTION A: ONE CONTINUOUS CHAT PER PERSON + NEW SESSION) */}
        <div className="flex items-center flex-wrap gap-1 text-xs">
          <button
            onClick={handleStartNewSession}
            title="Start a fresh new patient session"
            className="px-2.5 py-1 rounded-lg text-xs font-bold bg-teal-600 hover:bg-teal-700 text-white border border-teal-600 shadow-2xs flex items-center space-x-1 transition"
          >
            <RotateCcw className="w-3 h-3" />
            <span>+ New Session</span>
          </button>

          <span className="text-[11px] font-semibold text-slate-400 mx-1 hidden sm:inline">Threads:</span>

          {Object.values(threads).map((t) => {
            const userMsgCount = t.messages.filter((m) => m.role === "user").length;
            const hasBooking = t.sessionState?.appointment_id || (t.sessionState?.active_appointments && t.sessionState.active_appointments.length > 0);
            const isSelected = activeThreadId === t.threadId;

            return (
              <button
                key={t.threadId}
                onClick={() => {
                  setActiveThreadId(t.threadId);
                  setInputText(t.inputText);
                }}
                className={`px-2 py-1 rounded-lg text-xs font-semibold border transition flex items-center space-x-1.5 ${
                  isSelected
                    ? "bg-slate-900 text-white border-slate-900 shadow-2xs"
                    : "bg-white text-slate-700 border-slate-200 hover:bg-slate-50"
                }`}
              >
                <span>{t.patientName.split(" ")[0]}</span>
                {hasBooking && <span className="text-emerald-400 text-[10px]">✓</span>}
                <span className={`text-[9px] px-1 py-0.2 rounded font-bold ${
                  isSelected ? "bg-slate-800 text-teal-300" : "bg-slate-100 text-slate-600"
                }`}>
                  {userMsgCount}
                </span>
              </button>
            );
          })}

          <span className="text-slate-300 mx-0.5 hidden lg:inline">|</span>

          {/* QUICK SCENARIOS (OPEN/SWITCH TO PRESET PATIENT) */}
          <div className="hidden lg:flex items-center space-x-1">
            <span className="text-[10px] font-semibold text-slate-400">Presets:</span>
            {patientPresets.map((p) => {
              const threadKey = `thread-${p.id.toLowerCase()}`;
              const isSelected = activeThreadId === threadKey;
              return (
                <button
                  key={p.id}
                  onClick={() => handleSelectPreset(p)}
                  className={`px-1.5 py-0.5 rounded text-[11px] font-medium border transition ${
                    isSelected
                      ? "bg-teal-50 text-teal-800 border-teal-300 font-bold"
                      : "bg-slate-50 text-slate-600 border-slate-200 hover:bg-slate-100"
                  }`}
                >
                  {p.name.split(" ")[0]}
                </button>
              );
            })}
          </div>
        </div>
      </div>

      {/* TWO-COLUMN WORKSPACE: 3 COLS CHAT STREAM (INTERNAL SCROLL ONLY) + 1 COL SIDEBAR */}
      <div className="flex-1 min-h-0 grid grid-cols-1 lg:grid-cols-4 gap-2.5 overflow-hidden">
        
        {/* MAIN CHAT STREAM (COLUMNS 1-3) */}
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
                <span className="text-[11px] text-slate-500">Speaking with: <strong className="text-slate-800">{activePatientName}</strong></span>
              </div>
            </div>

            <div className="flex items-center space-x-2">
              <span className="text-[10px] font-mono bg-slate-100 text-slate-600 px-2 py-0.5 rounded-md hidden sm:inline">
                {activeThreadId}
              </span>
              <button
                onClick={handleResetCurrentThread}
                title="Reset this patient conversation"
                className="text-[11px] text-slate-600 hover:text-slate-900 flex items-center space-x-1 px-2 py-1 rounded-md hover:bg-slate-100 transition"
              >
                <RotateCcw className="w-3 h-3" />
                <span>Reset Thread</span>
              </button>
            </div>
          </div>

          {/* CHAT MESSAGES SCROLL AREA (SCROLLS INTERNALLY ONLY AS CONVERSATION GROWS) */}
          <div className="flex-1 min-h-0 overflow-y-auto p-3.5 sm:p-4 space-y-3">
            {chatMessages.map((msg) => (
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

                <div className={`max-w-[85%] sm:max-w-[78%] space-y-1.5`}>
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

                  {/* RENDER TOOL EXECUTION BADGES */}
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

                  {/* CLINICAL EMERGENCY PREEMPTION ALERT */}
                  {msg.emergencyTriggered && (
                    <div className="p-2.5 bg-red-100/90 border border-red-200 rounded-xl text-red-900 text-xs flex items-start space-x-2">
                      <AlertTriangle className="w-4 h-4 text-red-600 shrink-0 mt-0.5" />
                      <div>
                        <strong className="block font-bold">EMERGENCY PROTOCOL ENGAGED</strong>
                        Routine outpatient booking has been locked. The patient has been directed to dial 911 or proceed immediately to the nearest hospital Emergency Room.
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

          {/* CHAT INPUT FORM (PINNED AT BOTTOM) */}
          <form onSubmit={handleSendChatMessage} className="p-2.5 sm:p-3 border-t border-slate-100 bg-white flex items-center space-x-2 shrink-0">
            <input
              type="text"
              value={inputText}
              onChange={(e) => setInputText(e.target.value)}
              placeholder="Ask Sarah about doctor slots, symptoms, or appointments..."
              className="flex-1 bg-slate-50 border border-slate-200 rounded-xl px-3.5 py-2 text-xs sm:text-sm text-slate-900 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-teal-600/30 focus:border-teal-600 transition"
            />
            <button
              type="submit"
              disabled={!inputText.trim() || isSending}
              className="px-3.5 py-2 rounded-xl bg-teal-600 hover:bg-teal-700 text-white text-xs sm:text-sm font-semibold transition flex items-center space-x-1.5 disabled:opacity-50 disabled:cursor-not-allowed shadow-2xs shrink-0"
            >
              <span>Send</span>
              <Send className="w-3.5 h-3.5" />
            </button>
          </form>

        </div>

        {/* PATIENT SESSION STATE & QUICK ACTIONS (COLUMN 4) */}
        <div className="lg:col-span-1 flex flex-col gap-2 h-full overflow-y-auto pr-0.5">
          
          {/* PATIENT SESSION STATE CARD */}
          <div className="bg-white border border-slate-200/80 rounded-2xl p-3 shadow-2xs space-y-2 shrink-0">
            <div className="flex items-center justify-between border-b border-slate-100 pb-1.5">
              <h3 className="text-[11px] font-bold text-slate-900 uppercase tracking-wider">
                Intake State
              </h3>
              <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${
                sessionState.triage_level === "EMERGENCY" ? "bg-red-100 text-red-700" :
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
                  {sessionState.patient_name !== "Not Provided" ? sessionState.patient_name : activePatientName}
                </span>
              </div>

              {sessionState.patient_id && (
                <div className="bg-slate-50 p-2 rounded-lg border border-slate-100 flex justify-between items-center">
                  <span className="text-[10px] text-slate-400 font-semibold">PATIENT ID</span>
                  <span className="font-mono text-[10px] bg-teal-50 text-teal-700 px-1.5 py-0.5 rounded font-bold">
                    {sessionState.patient_id}
                  </span>
                </div>
              )}

              {sessionState.patient_phone && (
                <div className="bg-slate-50 p-2 rounded-lg border border-slate-100 flex justify-between items-center">
                  <span className="text-[10px] text-slate-400 font-semibold">PHONE</span>
                  <span className="font-mono text-[11px] text-slate-700 font-medium">
                    {sessionState.patient_phone}
                  </span>
                </div>
              )}

              <div className="bg-slate-50 p-2 rounded-lg border border-slate-100 flex justify-between items-center">
                <span className="text-[10px] text-slate-400 font-semibold">PHYSICIAN</span>
                <span className="font-semibold text-slate-800 text-[11px]">
                  {sessionState.active_doctor_name || "None Selected"}
                </span>
              </div>

              <div className="bg-slate-50 p-2 rounded-lg border border-slate-100 flex justify-between items-center">
                <span className="text-[10px] text-slate-400 font-semibold">SLOT</span>
                <span className="font-mono text-[11px] text-teal-700 font-semibold">
                  {formatCleanTime(sessionState.selected_slot)}
                </span>
              </div>
            </div>

            {/* MULTI-APPOINTMENT ACTIVE CARE PLAN */}
            {sessionState.active_appointments && sessionState.active_appointments.length > 0 && (
              <div className="mt-2 pt-2 border-t border-slate-100 space-y-1.5">
                <div className="flex items-center justify-between">
                  <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">
                    Care Plan ({sessionState.active_appointments.length})
                  </span>
                  <span className="text-[9px] bg-emerald-50 text-emerald-700 font-semibold px-1 rounded">
                    Multi-Checkup
                  </span>
                </div>
                <div className="space-y-1 max-h-32 overflow-y-auto">
                  {sessionState.active_appointments.map((a, idx) => (
                    <div key={a.id || idx} className="p-1.5 bg-slate-50 rounded-lg border border-slate-200/60 text-[10px] space-y-0.5">
                      <div className="flex items-center justify-between font-semibold text-slate-800">
                        <span>{a.doctor_name}</span>
                        <span className="text-[9px] font-mono text-teal-700 bg-teal-50 px-1 rounded">{a.id}</span>
                      </div>
                      <div className="flex items-center justify-between text-slate-500 text-[9px]">
                        <span>{a.specialty || "Specialty"}</span>
                        <span>{formatCleanTime(a.slot_iso)}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* QUICK INQUIRIES FOR EASY TESTING */}
          <div className="bg-white border border-slate-200/80 rounded-2xl p-3 shadow-2xs space-y-2 shrink-0">
            <h4 className="text-[11px] font-bold text-slate-900">Quick Inquiries:</h4>
            <div className="space-y-1.5">
              <button
                onClick={() => handleSendChatMessage(undefined, "What open slots do you have available today?")}
                className="w-full text-left p-1.5 px-2 rounded-lg text-[11px] font-medium bg-slate-50 hover:bg-slate-100 text-slate-700 border border-slate-200/60 transition"
              >
                📅 Open Slots Today
              </button>
              <button
                onClick={() => handleSendChatMessage(undefined, "Can I see Dr. Sarah Jenkins tomorrow?")}
                className="w-full text-left p-1.5 px-2 rounded-lg text-[11px] font-medium bg-slate-50 hover:bg-slate-100 text-slate-700 border border-slate-200/60 transition"
              >
                🩺 Dr. Jenkins (Cardiology)
              </button>
              {sessionState.triage_level === "CONFIRMED" && (
                <button
                  onClick={() => handleSendChatMessage(undefined, `Can I reschedule my appointment to another time? My name is ${sessionState.patient_name || activePatientName}.`)}
                  className="w-full text-left p-1.5 px-2 rounded-lg text-[11px] font-medium bg-teal-50 hover:bg-teal-100 text-teal-800 border border-teal-200 transition"
                >
                  🔄 Reschedule My Booking
                </button>
              )}
            </div>
          </div>

          {/* CLINICAL GUARDRAIL STATUS */}
          <div className="bg-teal-50/70 border border-teal-200/60 rounded-2xl p-2.5 text-[10px] text-teal-900 space-y-1 shrink-0">
            <div className="flex items-center space-x-1 font-bold text-teal-800">
              <CheckCircle2 className="w-3 h-3 text-teal-600" />
              <span>Active Guardrails</span>
            </div>
            <p className="leading-tight text-slate-600">
              Life-threatening emergencies immediately trigger 911/ER diversion. Medical prescriptions strictly refused.
            </p>
          </div>

        </div>

      </div>

    </div>
  );
};
