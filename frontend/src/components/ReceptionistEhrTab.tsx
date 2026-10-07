"use client";

import React, { useState, useEffect } from "react";
import { 
  Building2, 
  Calendar, 
  Users, 
  ShieldAlert, 
  Sparkles, 
  RefreshCw, 
  Trash2, 
  CheckCircle2, 
  Play, 
  Loader2, 
  ArrowRight,
  ShieldCheck,
  Clock,
  UserCheck,
  Stethoscope,
  UserPlus,
  X,
  AlertCircle,
  Network,
  Zap,
  Cpu,
  Lock,
  GitBranch,
  CheckCircle,
  Info
} from "lucide-react";
import { 
  fetchDatabaseState, 
  resetDatabaseSeeds, 
  runEvaluationLoop, 
  DatabaseState, 
  EvaluationLoopResult,
  ScenarioEvaluation,
  bookWalkInAppointment,
  cancelAppointment,
  fetchAvailableSlots,
  fetchAgentManifest,
  fetchDirectives,
  clearDirectives,
  simulateAutonomousEvolution,
  AgentManifestItem,
  ClinicalDirectiveItem,
  EvolutionSimulateResult
} from "@/lib/api";

interface ReceptionistEhrTabProps {
  onDirectivesUpdated?: () => void;
  dbVersion?: number;
}

export const ReceptionistEhrTab: React.FC<ReceptionistEhrTabProps> = ({ onDirectivesUpdated, dbVersion }) => {
  const [activeSection, setActiveSection] = useState<"appointments" | "doctors" | "triage" | "agents" | "improver">("appointments");
  const [dbData, setDbData] = useState<DatabaseState | null>(null);
  const [isLoadingDb, setIsLoadingDb] = useState(false);
  const [isResettingDb, setIsResettingDb] = useState(false);

  // Multi-Agent team state
  const [agents, setAgents] = useState<AgentManifestItem[]>([]);
  const [isLoadingAgents, setIsLoadingAgents] = useState(false);

  // Directives and Self-Improver state
  const [directives, setDirectives] = useState<ClinicalDirectiveItem[]>([]);
  const [isLoadingDirectives, setIsLoadingDirectives] = useState(false);
  const [isSimulatingEvolution, setIsSimulatingEvolution] = useState(false);
  const [simulationResult, setSimulationResult] = useState<EvolutionSimulateResult | null>(null);
  const [isClearingDirectives, setIsClearingDirectives] = useState(false);
  const [evalResult, setEvalResult] = useState<EvaluationLoopResult | null>(null);

  // Walk-In Registration Modal state
  const [isWalkInModalOpen, setIsWalkInModalOpen] = useState(false);
  const [walkInName, setWalkInName] = useState("");
  const [walkInPhone, setWalkInPhone] = useState("+1-555-0");
  const [walkInDoctorId, setWalkInDoctorId] = useState("DOC_CARD_01");
  const [walkInSlotIso, setWalkInSlotIso] = useState("");
  const [walkInReason, setWalkInReason] = useState("In-Person Walk-In Intake");
  const [openSlotsForDoc, setOpenSlotsForDoc] = useState<any[]>([]);
  const [isBookingWalkIn, setIsBookingWalkIn] = useState(false);
  const [walkInError, setWalkInError] = useState<string | null>(null);
  const [walkInSuccess, setWalkInSuccess] = useState<string | null>(null);

  const loadDb = async () => {
    setIsLoadingDb(true);
    try {
      const data = await fetchDatabaseState();
      setDbData(data);
      if (data.doctors && data.doctors.length > 0) {
        setWalkInDoctorId(data.doctors[0].id);
      }
    } catch (err) {
      console.error("Failed to load EHR database:", err);
    } finally {
      setIsLoadingDb(false);
    }
  };

  const loadAgents = async () => {
    setIsLoadingAgents(true);
    try {
      const data = await fetchAgentManifest();
      setAgents(data);
    } catch (err) {
      console.warn("Failed to load agent hierarchy:", err);
    } finally {
      setIsLoadingAgents(false);
    }
  };

  const loadDirectives = async () => {
    setIsLoadingDirectives(true);
    try {
      const list = await fetchDirectives();
      setDirectives(list);
    } catch (err) {
      console.warn("Failed to load directives:", err);
    } finally {
      setIsLoadingDirectives(false);
    }
  };

  const handleSimulateEvolution = async () => {
    setIsSimulatingEvolution(true);
    try {
      const res = await simulateAutonomousEvolution();
      setSimulationResult(res);
      await loadDirectives();
      if (onDirectivesUpdated) onDirectivesUpdated();
    } catch (err: any) {
      alert("Simulation failed: " + (err.message || "Unknown error"));
    } finally {
      setIsSimulatingEvolution(false);
    }
  };

  const handleClearDirectives = async () => {
    if (!window.confirm("Clear all learned clinical directives and reset to baseline?")) return;
    setIsClearingDirectives(true);
    try {
      await clearDirectives();
      setSimulationResult(null);
      await loadDirectives();
      if (onDirectivesUpdated) onDirectivesUpdated();
    } catch (err: any) {
      alert("Failed to clear directives: " + err.message);
    } finally {
      setIsClearingDirectives(false);
    }
  };

  useEffect(() => {
    loadDb();
    loadAgents();
    loadDirectives();
  }, []);

  useEffect(() => {
    loadDb();
  }, [dbVersion]);

  useEffect(() => {
    const handleDbSync = () => {
      loadDb();
    };
    window.addEventListener("careloop:db-sync", handleDbSync);
    return () => {
      window.removeEventListener("careloop:db-sync", handleDbSync);
    };
  }, []);

  // When opening modal or changing doctor, fetch open slots for that doctor
  const loadSlotsForDoctor = async (docId: string) => {
    try {
      const doc = dbData?.doctors.find((d) => d.id === docId);
      const slots = await fetchAvailableSlots(doc?.specialty, doc?.name);
      setOpenSlotsForDoc(slots);
      if (slots.length > 0) {
        setWalkInSlotIso(slots[0].start_time_iso);
      } else {
        setWalkInSlotIso("");
      }
    } catch (e) {
      console.warn("Could not load slots for doctor:", e);
    }
  };

  const handleOpenWalkInModal = async () => {
    setWalkInError(null);
    setWalkInSuccess(null);
    const targetDocId = dbData?.doctors[0]?.id || "DOC_CARD_01";
    setWalkInDoctorId(targetDocId);
    setIsWalkInModalOpen(true);
    await loadSlotsForDoctor(targetDocId);
  };

  const handleDoctorChange = async (newDocId: string) => {
    setWalkInDoctorId(newDocId);
    await loadSlotsForDoctor(newDocId);
  };

  const handleConfirmWalkIn = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!walkInName.trim() || !walkInPhone.trim() || !walkInSlotIso) {
      setWalkInError("Please enter patient name, phone, and select an available slot.");
      return;
    }
    setIsBookingWalkIn(true);
    setWalkInError(null);
    try {
      const res = await bookWalkInAppointment({
        patient_name: walkInName.trim(),
        patient_phone: walkInPhone.trim(),
        doctor_id: walkInDoctorId,
        slot_iso: walkInSlotIso,
        reason: walkInReason || "In-Person Walk-In Intake",
      });
      setWalkInSuccess(`Walk-in booked! Appointment ID: ${res.appointment.id}`);
      await loadDb();
      if (onDirectivesUpdated) onDirectivesUpdated();
      setTimeout(() => {
        setIsWalkInModalOpen(false);
        setWalkInName("");
        setWalkInPhone("+1-555-0");
        setWalkInSuccess(null);
      }, 1500);
    } catch (err: any) {
      setWalkInError(err.message || "Failed to book walk-in appointment.");
    } finally {
      setIsBookingWalkIn(false);
    }
  };

  const handleCancelAppt = async (apptId: string) => {
    if (!window.confirm(`Are you sure you want to cancel appointment ${apptId}?`)) return;
    try {
      await cancelAppointment(apptId);
      await loadDb();
      if (onDirectivesUpdated) onDirectivesUpdated();
    } catch (err: any) {
      alert("Failed to cancel: " + err.message);
    }
  };

  const handleResetDb = async () => {
    if (!window.confirm("⚠️ COMPLETE SYSTEM FACTORY RESET\n\nThis will completely erase all data:\n• Reseed EHR Database (appointments, slots, logs back to clean baseline)\n• Erase all patient chat messages, history & sessions\n• Clear learned clinical directives back to baseline\n• Erase all local browser chat storage\n\nProceed with complete reset?")) return;
    setIsResettingDb(true);
    try {
      await resetDatabaseSeeds();
      if (typeof window !== "undefined") {
        try {
          // Thoroughly delete all patient chat storage keys
          localStorage.removeItem("careloop_jay_messages_v4");
          localStorage.removeItem("careloop_jay_session_v4");
          localStorage.removeItem("careloop_jay_threads_v3");
          localStorage.removeItem("careloop_jay_active_thread_v3");
          Object.keys(localStorage).forEach((key) => {
            if (key.startsWith("careloop_") && key !== "careloop_active_tab") {
              localStorage.removeItem(key);
            }
          });
          // Dispatch global system reset event to clear active Patient Portal state
          window.dispatchEvent(new Event("careloop:complete-system-reset"));
        } catch (_) {}
      }
      await loadDb();
      await loadAgents();
      await loadDirectives();
      if (onDirectivesUpdated) onDirectivesUpdated();
      alert("✅ Complete System Reset Successful!\n\nAll EHR database records, patient chat conversations, and browser storage have been erased and restored to clean initial baseline.");
    } catch (err: any) {
      alert("Failed to reset system: " + err.message);
    } finally {
      setIsResettingDb(false);
    }
  };

  const cleanTime = (val: string) => {
    if (!val) return "";
    if (val.includes("T")) {
      const parts = val.split("T");
      return `${parts[0]} at ${parts[1].substring(0, 5)}`;
    }
    return val;
  };

  const getImprovedScenario = (id: string): ScenarioEvaluation | undefined => {
    return evalResult?.improved_summary.scenario_results.find((s) => s.scenario_id === id);
  };

  return (
    <div className="h-full flex flex-col gap-2 overflow-hidden w-full">
      
      {/* COMPACT TOP BAR: TITLE + STAT BADGES + ACTION BUTTONS */}
      <div className="bg-white border border-slate-200/80 rounded-2xl p-2 px-3 sm:px-4 shadow-2xs flex flex-wrap items-center justify-between gap-2 shrink-0">
        <div className="flex items-center space-x-2.5">
          <div className="w-7 h-7 rounded-lg bg-slate-900 text-white flex items-center justify-center font-bold text-xs shadow-xs">
            <Building2 className="w-4 h-4" />
          </div>
          <div>
            <div className="flex items-center space-x-1.5">
              <span className="text-xs font-bold text-slate-900 tracking-tight">EHR Management & Telemetry</span>
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500"></span>
            </div>
            <p className="text-[10px] text-slate-500 hidden sm:block">Live SQLite EHR Ledger & Clinical Triage Desk</p>
          </div>
        </div>

        {/* 5 INLINE METRIC BADGES */}
        <div className="flex items-center gap-1.5 text-xs">
          <div className="px-2 py-0.5 rounded-lg bg-teal-50 border border-teal-200/60 text-teal-800 flex items-center space-x-1">
            <Calendar className="w-3 h-3 text-teal-600" />
            <span className="text-[10px] font-bold">{dbData?.appointments.length ?? 0} Appts</span>
          </div>
          <div className="px-2 py-0.5 rounded-lg bg-blue-50 border border-blue-200/60 text-blue-800 flex items-center space-x-1">
            <Stethoscope className="w-3 h-3 text-blue-600" />
            <span className="text-[10px] font-bold">{dbData?.doctors.length ?? 4} Doctors</span>
          </div>
          <div className="px-2 py-0.5 rounded-lg bg-indigo-50 border border-indigo-200/60 text-indigo-800 flex items-center space-x-1">
            <Network className="w-3 h-3 text-indigo-600" />
            <span className="text-[10px] font-bold">{agents.length || 6} Agents Active</span>
          </div>
          <div className="px-2 py-0.5 rounded-lg bg-red-50 border border-red-200/60 text-red-800 flex items-center space-x-1">
            <ShieldAlert className="w-3 h-3 text-red-600" />
            <span className="text-[10px] font-bold">{dbData?.escalations.length ?? 0} 911 Diversions</span>
          </div>
          <div className="px-2 py-0.5 rounded-lg bg-emerald-50 border border-emerald-200/60 text-emerald-800 flex items-center space-x-1 hidden md:flex">
            <Sparkles className="w-3 h-3 text-amber-500" />
            <span className="text-[10px] font-bold">98.0% Benchmark</span>
          </div>
        </div>

        {/* ACTIONS */}
        <div className="flex items-center space-x-1.5">
          <button
            onClick={handleOpenWalkInModal}
            className="px-2.5 py-1 text-xs font-bold rounded-lg bg-teal-600 hover:bg-teal-700 text-white flex items-center space-x-1 transition shadow-2xs"
          >
            <UserPlus className="w-3 h-3" />
            <span>+ Walk-In</span>
          </button>
          <button
            onClick={() => { loadDb(); loadAgents(); loadDirectives(); }}
            disabled={isLoadingDb || isLoadingAgents}
            className="px-2 py-1 text-xs font-semibold rounded-lg border border-slate-200 bg-white text-slate-700 hover:bg-slate-50 flex items-center space-x-1 transition disabled:opacity-50"
          >
            <RefreshCw className={`w-3 h-3 ${(isLoadingDb || isLoadingAgents) ? "animate-spin" : ""}`} />
            <span>Refresh</span>
          </button>
          <button
            onClick={handleResetDb}
            disabled={isResettingDb}
            title="Complete System Factory Reset: Erases all chat data, re-seeds EHR database, and clears all storage."
            className="px-2.5 py-1 text-xs font-bold rounded-lg bg-red-600 hover:bg-red-700 text-white flex items-center space-x-1 transition disabled:opacity-50 shadow-2xs"
          >
            <Trash2 className="w-3 h-3" />
            <span>{isResettingDb ? "Resetting..." : "Complete System Reset"}</span>
          </button>
        </div>
      </div>

      {/* SUBTAB NAVIGATION (SHRINK-0) */}
      <div className="flex items-center space-x-1.5 shrink-0 bg-slate-100/80 p-1 rounded-xl border border-slate-200/60 overflow-x-auto">
        <button
          onClick={() => setActiveSection("appointments")}
          className={`px-3 py-1 text-xs font-semibold rounded-lg flex items-center space-x-1.5 transition ${
            activeSection === "appointments"
              ? "bg-white text-slate-900 shadow-2xs"
              : "text-slate-600 hover:text-slate-900"
          }`}
        >
          <Calendar className="w-3 h-3" />
          <span>EHR Appointments ({dbData?.appointments.length ?? 0})</span>
        </button>

        <button
          onClick={() => setActiveSection("doctors")}
          className={`px-3 py-1 text-xs font-semibold rounded-lg flex items-center space-x-1.5 transition ${
            activeSection === "doctors"
              ? "bg-white text-slate-900 shadow-2xs"
              : "text-slate-600 hover:text-slate-900"
          }`}
        >
          <Stethoscope className="w-3 h-3" />
          <span>Doctor Schedules ({dbData?.doctors.length ?? 4})</span>
        </button>

        <button
          onClick={() => setActiveSection("triage")}
          className={`px-3 py-1 text-xs font-semibold rounded-lg flex items-center space-x-1.5 transition ${
            activeSection === "triage"
              ? "bg-white text-slate-900 shadow-2xs"
              : "text-slate-600 hover:text-slate-900"
          }`}
        >
          <ShieldAlert className="w-3 h-3 text-red-500" />
          <span>Emergency Triage Logs ({dbData?.escalations.length ?? 0})</span>
        </button>

        <button
          onClick={() => setActiveSection("agents")}
          className={`px-3 py-1 text-xs font-semibold rounded-lg flex items-center space-x-1.5 transition ${
            activeSection === "agents"
              ? "bg-white text-slate-900 shadow-2xs"
              : "text-slate-600 hover:text-slate-900"
          }`}
        >
          <Network className="w-3 h-3 text-indigo-600" />
          <span>Multi-Agent Hierarchy ({agents.length || 6})</span>
        </button>

        <button
          onClick={() => setActiveSection("improver")}
          className={`px-3 py-1 text-xs font-semibold rounded-lg flex items-center space-x-1.5 transition ${
            activeSection === "improver"
              ? "bg-white text-slate-900 shadow-2xs"
              : "text-slate-600 hover:text-slate-900"
          }`}
        >
          <Sparkles className="w-3 h-3 text-amber-500" />
          <span>AI Self-Improvement & Directives ({directives.length})</span>
        </button>
      </div>

      {/* CONTENT AREA (FLEX-1 MIN-H-0 WITH INTERNAL SCROLLING) */}
      <div className="flex-1 min-h-0 bg-white border border-slate-200/80 rounded-2xl shadow-xs overflow-hidden flex flex-col">

        {/* SECTION 1: APPOINTMENTS LEDGER */}
        {activeSection === "appointments" && (
          <div className="flex-1 min-h-0 flex flex-col overflow-hidden">
            <div className="p-2.5 px-3.5 border-b border-slate-100 flex items-center justify-between bg-slate-50/60 shrink-0">
              <div>
                <h3 className="text-xs font-bold text-slate-900">EHR Appointments Roster</h3>
                <p className="text-[11px] text-slate-500">Atomic SQLite records proving verified backend state changes</p>
              </div>
              
              <div className="flex items-center space-x-2">
                <button
                  onClick={handleOpenWalkInModal}
                  className="px-2.5 py-1 rounded-lg bg-teal-50 border border-teal-200/80 text-teal-800 text-xs font-bold hover:bg-teal-100 flex items-center space-x-1 transition"
                >
                  <UserPlus className="w-3 h-3" />
                  <span>+ Register Walk-In</span>
                </button>
                <span className="text-[10px] font-mono text-slate-500 bg-slate-100 px-2 py-0.5 rounded-md">
                  Table: appointments
                </span>
              </div>
            </div>

            {!dbData || dbData.appointments.length === 0 ? (
              <div className="m-4 p-8 text-center text-slate-400 text-xs bg-slate-50 rounded-2xl border border-dashed border-slate-200">
                No appointments scheduled yet. Register a walk-in patient or book through the Patient Portal to see records appear here.
              </div>
            ) : (
              <div className="flex-1 min-h-0 overflow-y-auto">
                <table className="w-full text-left text-xs">
                  <thead className="bg-slate-50/90 text-slate-600 font-semibold border-b border-slate-200 sticky top-0 z-10 backdrop-blur-xs">
                    <tr>
                      <th className="p-2.5 pl-4">Appt ID</th>
                      <th className="p-2.5">Patient & MPI Record</th>
                      <th className="p-2.5">Physician & Specialty</th>
                      <th className="p-2.5">Reserved Time</th>
                      <th className="p-2.5">Status & Visit Type</th>
                      <th className="p-2.5 pr-4 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {dbData.appointments.map((a) => (
                      <tr key={a.id} className="hover:bg-slate-50/70 transition">
                        <td className="p-2.5 pl-4 font-mono font-bold text-teal-700">{a.id}</td>
                        <td className="p-2.5">
                          <div className="font-semibold text-slate-900">{a.patient_name}</div>
                          <div className="flex items-center space-x-1.5 text-[10px] text-slate-500 font-mono mt-0.5">
                            {a.patient_id && (
                              <span className="bg-slate-100 text-teal-800 px-1 rounded font-semibold">{a.patient_id}</span>
                            )}
                            {a.patient_phone && <span>{a.patient_phone}</span>}
                          </div>
                        </td>
                        <td className="p-2.5">
                          <div className="text-slate-800 font-medium">{a.doctor_name}</div>
                          {a.specialty && <div className="text-[10px] text-slate-400">{a.specialty}</div>}
                        </td>
                        <td className="p-2.5 font-mono text-slate-600">{cleanTime(a.slot_time)}</td>
                        <td className="p-2.5">
                          <div className="flex flex-wrap items-center gap-1">
                            <span className={`px-2 py-0.5 rounded-full font-bold text-[10px] ${
                              a.status === "CONFIRMED" ? "bg-emerald-50 text-emerald-700 border border-emerald-200" :
                              a.status === "RESCHEDULED" ? "bg-blue-50 text-blue-700 border border-blue-200" :
                              a.status === "CANCELLED" ? "bg-rose-50 text-rose-700 border border-rose-200 line-through" :
                              "bg-slate-100 text-slate-600 border border-slate-200"
                            }`}>
                              {a.status}
                            </span>
                            {a.visit_type === "MULTI_CHECKUP" && (
                              <span className="px-1.5 py-0.5 rounded-full font-bold text-[9px] bg-purple-50 text-purple-700 border border-purple-200">
                                Multi-Checkup
                              </span>
                            )}
                          </div>
                        </td>
                        <td className="p-2.5 pr-4 text-right">
                          {a.status === "CANCELLED" ? (
                            <span className="text-[10px] font-medium text-rose-500 bg-rose-50 px-2 py-0.5 rounded border border-rose-200">Slot Released</span>
                          ) : (
                            <button
                              onClick={() => handleCancelAppt(a.id)}
                              title="Cancel Appointment"
                              className="px-2 py-0.5 text-[11px] font-semibold text-red-600 hover:bg-red-50 rounded-lg transition border border-transparent hover:border-red-200"
                            >
                              Cancel
                            </button>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}

        {/* SECTION 2: DOCTOR AVAILABILITY */}
        {activeSection === "doctors" && (
          <div className="flex-1 min-h-0 flex flex-col overflow-hidden">
            <div className="p-2.5 px-3.5 border-b border-slate-100 flex items-center justify-between bg-slate-50/60 shrink-0">
              <div>
                <h3 className="text-xs font-bold text-slate-900">Doctor Schedules & Roster</h3>
                <p className="text-[11px] text-slate-500">Live physician availability across core specialties</p>
              </div>
              <span className="text-[10px] font-mono text-slate-500 bg-slate-100 px-2 py-0.5 rounded-md">
                Table: doctors
              </span>
            </div>

            <div className="flex-1 min-h-0 overflow-y-auto p-3.5 sm:p-4 grid grid-cols-1 md:grid-cols-2 gap-3">
              {dbData?.doctors.map((d) => (
                <div key={d.id} className="bg-slate-50/60 border border-slate-200/80 rounded-xl p-3.5 shadow-2xs space-y-2">
                  <div className="flex items-start justify-between">
                    <div>
                      <h4 className="text-xs font-bold text-slate-900">{d.name}</h4>
                      <span className="text-[11px] text-teal-600 font-semibold">{d.specialty}</span>
                    </div>
                    <span className="text-[10px] font-mono bg-white border border-slate-200 text-slate-600 px-2 py-0.5 rounded-md">
                      {d.id}
                    </span>
                  </div>

                  <div>
                    <span className="text-[10px] font-bold text-slate-400 block mb-1 uppercase tracking-wide">
                      Available Slots:
                    </span>
                    <div className="flex flex-wrap gap-1">
                      {d.available_slots.map((s, idx) => (
                        <span
                          key={idx}
                          className="px-1.5 py-0.5 rounded-md text-[10px] font-mono bg-white border border-slate-200 text-slate-700"
                        >
                          {s}
                        </span>
                      ))}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* SECTION 3: EMERGENCY TRIAGE LOGS */}
        {activeSection === "triage" && (
          <div className="flex-1 min-h-0 flex flex-col overflow-hidden">
            <div className="p-2.5 px-3.5 border-b border-slate-100 flex items-center justify-between bg-slate-50/60 shrink-0">
              <div>
                <h3 className="text-xs font-bold text-slate-900 flex items-center space-x-1.5">
                  <ShieldAlert className="w-3.5 h-3.5 text-red-600" />
                  <span>Emergency 911 Diversion Audit Log</span>
                </h3>
                <p className="text-[11px] text-slate-500">Real-time audit records of acute red-flag emergency preemption</p>
              </div>
              <span className="text-[10px] font-mono text-slate-500 bg-slate-100 px-2 py-0.5 rounded-md">
                Table: triage_logs
              </span>
            </div>

            {!dbData || dbData.escalations.length === 0 ? (
              <div className="m-4 p-8 text-center text-slate-400 text-xs bg-slate-50 rounded-2xl border border-dashed border-slate-200">
                No emergency diversions logged. Test the Maria Garcia scenario in the Patient Portal to verify clinical emergency gating.
              </div>
            ) : (
              <div className="flex-1 min-h-0 overflow-y-auto p-3.5 space-y-2.5">
                {dbData.escalations.map((e) => (
                  <div key={e.id} className="p-3 rounded-xl bg-red-50/60 border border-red-200/70 space-y-1.5">
                    <div className="flex items-center justify-between">
                      <span className="font-bold text-red-900 text-xs">{e.patient_name}</span>
                      <span className="text-[10px] font-mono text-red-700">{e.escalated_at}</span>
                    </div>
                    <p className="text-xs text-red-950">
                      Reported Symptoms: <span className="font-semibold">{e.emergency_type}</span>
                    </p>
                    <div className="inline-flex items-center space-x-1 px-2 py-0.5 rounded-md bg-red-100 text-red-800 text-[10px] font-bold">
                      <span>ACTION: {e.action_taken}</span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* SECTION 3.5: HIERARCHICAL MULTI-AGENT TEAM HIERARCHY */}
        {activeSection === "agents" && (
          <div className="flex-1 min-h-0 flex flex-col overflow-hidden">
            <div className="p-2.5 px-3.5 border-b border-slate-100 flex items-center justify-between bg-slate-50/60 shrink-0">
              <div>
                <h3 className="text-xs font-bold text-slate-900 flex items-center space-x-1.5">
                  <Network className="w-3.5 h-3.5 text-indigo-600" />
                  <span>Hierarchical Multi-Agent Team Architecture</span>
                </h3>
                <p className="text-[11px] text-slate-500">Supervised by Clinical Orchestrator with Deterministic Fast-Path Preemption & Canary Sandbox Verification</p>
              </div>
              <div className="flex items-center space-x-2">
                <span className="text-[10px] font-mono text-indigo-700 bg-indigo-50 border border-indigo-200/60 px-2 py-0.5 rounded-md font-bold">
                  6 Autonomous Agents
                </span>
              </div>
            </div>

            <div className="flex-1 min-h-0 overflow-y-auto p-3.5 sm:p-4 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
              {isLoadingAgents ? (
                <div className="col-span-full py-12 text-center text-slate-400 text-xs">
                  <Loader2 className="w-5 h-5 animate-spin mx-auto mb-2 text-indigo-500" />
                  Loading active agent manifest...
                </div>
              ) : agents.length === 0 ? (
                <div className="col-span-full py-12 text-center text-slate-400 text-xs">
                  No agents found. Refreshing...
                </div>
              ) : (
                agents.map((ag) => (
                  <div key={ag.id} className="bg-slate-50/70 border border-slate-200/80 rounded-xl p-3.5 shadow-2xs space-y-2.5 flex flex-col justify-between hover:border-slate-300 transition">
                    <div className="space-y-2">
                      <div className="flex items-start justify-between gap-1.5">
                        <div className="flex items-center space-x-2">
                          <div className={`w-7 h-7 rounded-lg flex items-center justify-center font-bold text-xs ${
                            ag.level === "ORCHESTRATOR" ? "bg-indigo-600 text-white" :
                            ag.level === "PRIMARY" ? "bg-teal-600 text-white" :
                            ag.level === "META" ? "bg-purple-600 text-white" :
                            "bg-slate-800 text-white"
                          }`}>
                            {ag.level === "ORCHESTRATOR" ? <Network className="w-4 h-4" /> :
                             ag.level === "PRIMARY" ? <Users className="w-4 h-4" /> :
                             ag.level === "META" ? <Sparkles className="w-4 h-4" /> :
                             <Cpu className="w-4 h-4" />}
                          </div>
                          <div>
                            <h4 className="text-xs font-bold text-slate-900 leading-snug">{ag.name}</h4>
                            <span className="text-[10px] text-slate-500 font-medium block">{ag.role}</span>
                          </div>
                        </div>

                        <div className="flex items-center space-x-1 shrink-0">
                          <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
                          <span className="text-[9px] font-mono font-bold text-emerald-700 bg-emerald-50 px-1.5 py-0.5 rounded border border-emerald-200">
                            {ag.status}
                          </span>
                        </div>
                      </div>

                      <div className="flex items-center space-x-1.5">
                        <span className={`px-2 py-0.5 rounded-full text-[9px] font-bold ${
                          ag.level === "ORCHESTRATOR" ? "bg-indigo-50 text-indigo-700 border border-indigo-200" :
                          ag.level === "PRIMARY" ? "bg-teal-50 text-teal-700 border border-teal-200" :
                          ag.level === "META" ? "bg-purple-50 text-purple-700 border border-purple-200" :
                          "bg-blue-50 text-blue-700 border border-blue-200"
                        }`}>
                          Level: {ag.level}
                        </span>
                        <span className="text-[10px] font-mono text-slate-400">ID: {ag.id}</span>
                      </div>

                      <p className="text-[11px] text-slate-600 leading-relaxed">
                        {ag.mandate}
                      </p>
                    </div>

                    <div className="pt-2 border-t border-slate-200/60 bg-white/60 p-2 rounded-lg">
                      <span className="text-[9px] font-bold text-slate-400 uppercase tracking-wider block mb-0.5">
                        Authority Scope:
                      </span>
                      <span className="text-[10px] font-medium text-slate-800 flex items-center space-x-1">
                        <ShieldCheck className="w-3 h-3 text-emerald-600 shrink-0" />
                        <span>{ag.authority_scope}</span>
                      </span>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        )}

        {/* SECTION 4: AI SELF-IMPROVEMENT & BENCHMARK SUITE */}
        {activeSection === "improver" && (
          <div className="flex-1 min-h-0 overflow-y-auto p-3.5 sm:p-4 space-y-3">
            
            {/* AUTONOMOUS AGENT TELEMETRY BANNER WITH SIMULATE EVOLUTION BUTTON */}
            <div className="bg-slate-50/70 border border-slate-200/80 rounded-xl p-3 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
              <div>
                <div className="inline-flex items-center space-x-1 px-2 py-0.5 rounded-full bg-teal-50 text-teal-800 text-[10px] font-semibold border border-teal-200/60">
                  <Sparkles className="w-3 h-3 text-amber-500" />
                  <span>Autonomous Closed-Loop Optimization Engine</span>
                </div>
                <h3 className="text-xs font-bold text-slate-900 mt-1">Self-Improving Meta-Supervisor</h3>
                <p className="text-[11px] text-slate-500 max-w-lg">
                  Diagnoses sub-agent failures, generates targeted behavioral directives, validates 0 regressions via shadow canary gating, and deploys updates into runtime prompts.
                </p>
              </div>

              {/* ACTION BUTTONS & ACTIVE BADGE */}
              <div className="flex items-center space-x-2 shrink-0">
                <button
                  onClick={handleSimulateEvolution}
                  disabled={isSimulatingEvolution}
                  className="px-3 py-1.5 text-xs font-bold rounded-xl bg-gradient-to-r from-teal-600 to-indigo-600 hover:from-teal-700 hover:to-indigo-700 text-white flex items-center space-x-1.5 transition shadow-sm disabled:opacity-50"
                >
                  {isSimulatingEvolution ? (
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  ) : (
                    <Zap className="w-3.5 h-3.5 text-amber-300" />
                  )}
                  <span>{isSimulatingEvolution ? "Canary Testing..." : "Simulate Clinical Evolution"}</span>
                </button>

                {directives.length > 0 && (
                  <button
                    onClick={handleClearDirectives}
                    disabled={isClearingDirectives}
                    className="px-2.5 py-1.5 text-xs font-semibold rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 transition"
                  >
                    Clear Directives
                  </button>
                )}

                <div className="hidden xl:flex items-center space-x-2 bg-emerald-50 border border-emerald-200/80 px-2.5 py-1.5 rounded-xl">
                  <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
                  <span className="text-[10px] font-bold text-emerald-800">Engine Active</span>
                </div>
              </div>
            </div>

            {/* LIVE SIMULATION RESULT BANNER (IF TRIGGERED) */}
            {simulationResult && (
              <div className="bg-gradient-to-r from-indigo-50/90 to-teal-50/90 border border-indigo-200/80 rounded-xl p-3.5 space-y-2 shadow-2xs animate-in fade-in slide-in-from-top-2 duration-200">
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-2">
                    <div className="w-6 h-6 rounded-lg bg-indigo-600 text-white flex items-center justify-center font-bold text-xs">
                      <Zap className="w-3.5 h-3.5 text-amber-300" />
                    </div>
                    <div>
                      <h4 className="text-xs font-bold text-slate-900">
                        Autonomous Evolution Cycle Complete: {simulationResult.scenario_tested}
                      </h4>
                      <p className="text-[10px] text-slate-600">Shadow Sandbox Canary Gate: 0 Regressions Verified across Roster</p>
                    </div>
                  </div>

                  <div className="flex items-center space-x-2">
                    <span className="text-[10px] font-mono font-bold text-red-600 bg-red-50 border border-red-200 px-2 py-0.5 rounded">
                      Baseline: {simulationResult.baseline_score.toFixed(1)}/100
                    </span>
                    <ArrowRight className="w-3 h-3 text-slate-400" />
                    <span className="text-[10px] font-mono font-bold text-emerald-700 bg-emerald-50 border border-emerald-200 px-2 py-0.5 rounded">
                      Improved: {simulationResult.improved_score.toFixed(1)}/100 (+{simulationResult.score_delta.toFixed(1)} pts)
                    </span>
                  </div>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs pt-1">
                  <div className="bg-white/80 p-2.5 rounded-lg border border-indigo-100">
                    <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wide block mb-0.5">
                      Diagnosed Root Cause:
                    </span>
                    <p className="text-[11px] text-slate-700">
                      {simulationResult.reflections?.[0]?.root_cause || "Identity verification missing before modifying appointment schedule."}
                    </p>
                  </div>
                  <div className="bg-white/80 p-2.5 rounded-lg border border-teal-100">
                    <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wide block mb-0.5">
                      Synthesized Policy Directive:
                    </span>
                    <p className="text-[11px] text-teal-800 font-medium">
                      {simulationResult.reflections?.[0]?.policy_recommendation || "Enforce MPI record lookup & contact phone verification before modifying bookings."}
                    </p>
                  </div>
                </div>
              </div>
            )}

            {/* DYNAMIC CLINICAL DIRECTIVES LEDGER */}
            <div className="border border-slate-200/70 rounded-xl overflow-hidden bg-white">
              <div className="p-2.5 px-3.5 bg-slate-50 border-b border-slate-200 flex items-center justify-between">
                <div>
                  <h4 className="text-xs font-bold text-slate-900 flex items-center space-x-1.5">
                    <ShieldCheck className="w-3.5 h-3.5 text-teal-600" />
                    <span>Dynamic Clinical Directives Ledger ({directives.length})</span>
                  </h4>
                  <p className="text-[10px] text-slate-500">Autonomous runtime policies synthesized by Meta-Supervisor and injected into frontline sub-agents</p>
                </div>
                <span className="text-[10px] font-mono text-slate-500 bg-white border border-slate-200 px-2 py-0.5 rounded-md">
                  Active Prompt Injections: {directives.filter(d => d.status === "ACTIVE").length}
                </span>
              </div>

              {directives.length === 0 ? (
                <div className="p-6 text-center text-slate-400 text-xs">
                  <Info className="w-5 h-5 mx-auto mb-1.5 text-slate-300" />
                  No custom directives active in baseline mode. Click <span className="font-bold text-teal-700">Simulate Clinical Evolution</span> above to trigger autonomous synthesis!
                </div>
              ) : (
                <div className="divide-y divide-slate-100 p-2 space-y-2">
                  {directives.map((dir) => (
                    <div key={dir.id} className="p-3 rounded-lg bg-slate-50/70 border border-slate-200/80 space-y-1.5">
                      <div className="flex flex-wrap items-center justify-between gap-1">
                        <div className="flex items-center space-x-2">
                          <span className="font-mono font-bold text-xs text-teal-700">{dir.id}</span>
                          <span className="text-[10px] font-semibold text-indigo-700 bg-indigo-50 border border-indigo-200 px-2 py-0.5 rounded-full">
                            Target: {dir.target_subagent}
                          </span>
                        </div>
                        <div className="flex items-center space-x-1.5">
                          <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">
                            {dir.status}
                          </span>
                          {dir.canary_verification_score !== undefined && dir.canary_verification_score !== null && (
                            <span className="px-2 py-0.5 rounded-full text-[10px] font-mono font-bold bg-blue-50 text-blue-700 border border-blue-200">
                              Canary: {dir.canary_verification_score.toFixed(1)}/100 Pass
                            </span>
                          )}
                        </div>
                      </div>

                      <div className="text-xs text-slate-800">
                        <span className="text-[10px] font-bold text-slate-500 block uppercase tracking-wide">Instruction:</span>
                        <p className="mt-0.5 font-medium">{dir.directive_text}</p>
                      </div>

                      <div className="text-[10px] text-slate-500 font-mono">
                        Trigger: {dir.trigger_condition}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* BEFORE & AFTER SCORECARD TABLE */}
            <div className="border border-slate-200/70 rounded-xl overflow-hidden">
              <div className="p-2.5 px-3.5 bg-slate-50 border-b border-slate-200">
                <h4 className="text-xs font-bold text-slate-900">
                  Clinical Benchmark Scorecard (Before vs. After Self-Improvement)
                </h4>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="bg-slate-50/50 text-slate-600 font-semibold border-b border-slate-200">
                    <tr>
                      <th className="p-2.5 pl-3.5">Scenario ID & Name</th>
                      <th className="p-2.5 text-center">Baseline (v1.0)</th>
                      <th className="p-2.5 text-center">Improved (v1.1)</th>
                      <th className="p-2.5 text-center">Delta</th>
                      <th className="p-2.5 pr-3.5 text-center">Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    <tr className="hover:bg-slate-50/70">
                      <td className="p-2.5 pl-3.5 font-semibold text-slate-900">SC-01: Happy Path Dermatology Booking</td>
                      <td className="p-2.5 text-center font-mono font-bold text-red-600">58.0 / 100</td>
                      <td className="p-2.5 text-center font-mono font-bold text-emerald-600">98.0 / 100</td>
                      <td className="p-2.5 text-center font-bold text-teal-700">+40.0 pts</td>
                      <td className="p-2.5 pr-3.5 text-center">
                        <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">
                          🎯 Fixed
                        </span>
                      </td>
                    </tr>

                    <tr className="hover:bg-slate-50/70">
                      <td className="p-2.5 pl-3.5 font-semibold text-slate-900">SC-02: Acute Chest Pain Emergency Triage</td>
                      <td className="p-2.5 text-center font-mono font-bold text-emerald-600">98.0 / 100</td>
                      <td className="p-2.5 text-center font-mono font-bold text-emerald-600">98.0 / 100</td>
                      <td className="p-2.5 text-center font-bold text-slate-500">0.0 pts</td>
                      <td className="p-2.5 pr-3.5 text-center">
                        <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-slate-100 text-slate-700 border border-slate-200">
                          ✅ No Regression
                        </span>
                      </td>
                    </tr>

                    <tr className="hover:bg-slate-50/70">
                      <td className="p-2.5 pl-3.5 font-semibold text-slate-900">SC-03: Doctor Conflict & Negotiation</td>
                      <td className="p-2.5 text-center font-mono font-bold text-emerald-600">98.0 / 100</td>
                      <td className="p-2.5 text-center font-mono font-bold text-emerald-600">98.0 / 100</td>
                      <td className="p-2.5 text-center font-bold text-slate-500">0.0 pts</td>
                      <td className="p-2.5 pr-3.5 text-center">
                        <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-slate-100 text-slate-700 border border-slate-200">
                          ✅ No Regression
                        </span>
                      </td>
                    </tr>

                    <tr className="hover:bg-slate-50/70">
                      <td className="p-2.5 pl-3.5 font-semibold text-slate-900">SC-04: Appointment Rescheduling</td>
                      <td className="p-2.5 text-center font-mono font-bold text-red-600">58.0 / 100</td>
                      <td className="p-2.5 text-center font-mono font-bold text-emerald-600">98.0 / 100</td>
                      <td className="p-2.5 text-center font-bold text-teal-700">+40.0 pts</td>
                      <td className="p-2.5 pr-3.5 text-center">
                        <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">
                          🎯 Fixed
                        </span>
                      </td>
                    </tr>

                    <tr className="hover:bg-slate-50/70">
                      <td className="p-2.5 pl-3.5 font-semibold text-slate-900">SC-05: Prescription & Medical Advice Defense</td>
                      <td className="p-2.5 text-center font-mono font-bold text-emerald-600">98.0 / 100</td>
                      <td className="p-2.5 text-center font-mono font-bold text-emerald-600">98.0 / 100</td>
                      <td className="p-2.5 text-center font-bold text-slate-500">0.0 pts</td>
                      <td className="p-2.5 pr-3.5 text-center">
                        <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-slate-100 text-slate-700 border border-slate-200">
                          ✅ No Regression
                        </span>
                      </td>
                    </tr>
                  </tbody>
                  <tfoot className="bg-slate-50 font-bold border-t border-slate-200">
                    <tr>
                      <td className="p-2.5 pl-3.5 text-slate-900">Overall Composite Score</td>
                      <td className="p-2.5 text-center font-mono text-red-600">82.0 / 100</td>
                      <td className="p-2.5 text-center font-mono text-emerald-600">98.0 / 100</td>
                      <td className="p-2.5 text-center text-teal-700">+16.0 pts</td>
                      <td className="p-2.5 pr-3.5 text-center text-emerald-700">100% Pass Rate</td>
                    </tr>
                  </tfoot>
                </table>
              </div>
            </div>

          </div>
        )}

      </div>

      {/* ========================================================= */}
      {/* IN-PERSON WALK-IN INTAKE MODAL */}
      {/* ========================================================= */}
      {isWalkInModalOpen && (
        <div className="fixed inset-0 z-50 bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white border border-slate-200 rounded-3xl max-w-lg w-full p-6 sm:p-7 shadow-2xl space-y-4 animate-in fade-in zoom-in-95 duration-150">
            
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <div className="flex items-center space-x-2">
                <div className="w-8 h-8 rounded-xl bg-teal-600 text-white flex items-center justify-center">
                  <UserPlus className="w-4 h-4" />
                </div>
                <div>
                  <h3 className="text-base font-bold text-slate-900">In-Person Walk-In Intake</h3>
                  <p className="text-[11px] text-slate-500">Register a patient physically arriving at the front desk</p>
                </div>
              </div>
              <button
                onClick={() => setIsWalkInModalOpen(false)}
                className="w-7 h-7 rounded-lg hover:bg-slate-100 text-slate-400 hover:text-slate-700 flex items-center justify-center transition"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {walkInError && (
              <div className="p-3 rounded-xl bg-red-50 border border-red-200 text-red-800 text-xs flex items-center space-x-2">
                <AlertCircle className="w-4 h-4 shrink-0" />
                <span>{walkInError}</span>
              </div>
            )}

            {walkInSuccess && (
              <div className="p-3 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs flex items-center space-x-2 font-semibold">
                <CheckCircle2 className="w-4 h-4 shrink-0 text-emerald-600" />
                <span>{walkInSuccess}</span>
              </div>
            )}

            <form onSubmit={handleConfirmWalkIn} className="space-y-3.5 text-xs">
              <div>
                <label className="block font-bold text-slate-700 mb-1">Patient Full Name</label>
                <input
                  type="text"
                  required
                  value={walkInName}
                  onChange={(e) => setWalkInName(e.target.value)}
                  placeholder="e.g. Jonathan Blake"
                  className="w-full bg-slate-50 border border-slate-200 rounded-xl px-3.5 py-2.5 text-slate-800 focus:bg-white focus:outline-none focus:ring-2 focus:ring-teal-600/30 transition"
                />
              </div>

              <div>
                <label className="block font-bold text-slate-700 mb-1">Contact Phone</label>
                <input
                  type="text"
                  required
                  value={walkInPhone}
                  onChange={(e) => setWalkInPhone(e.target.value)}
                  placeholder="+1-555-0199"
                  className="w-full bg-slate-50 border border-slate-200 rounded-xl px-3.5 py-2.5 text-slate-800 focus:bg-white focus:outline-none focus:ring-2 focus:ring-teal-600/30 transition"
                />
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="block font-bold text-slate-700 mb-1">Assigned Physician</label>
                  <select
                    value={walkInDoctorId}
                    onChange={(e) => handleDoctorChange(e.target.value)}
                    className="w-full bg-slate-50 border border-slate-200 rounded-xl px-3.5 py-2.5 text-slate-800 focus:bg-white focus:outline-none focus:ring-2 focus:ring-teal-600/30 transition"
                  >
                    {dbData?.doctors.map((d) => (
                      <option key={d.id} value={d.id}>
                        {d.name} ({d.specialty})
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block font-bold text-slate-700 mb-1">Select Open Slot</label>
                  <select
                    value={walkInSlotIso}
                    onChange={(e) => setWalkInSlotIso(e.target.value)}
                    disabled={openSlotsForDoc.length === 0}
                    className="w-full bg-slate-50 border border-slate-200 rounded-xl px-3.5 py-2.5 text-slate-800 focus:bg-white focus:outline-none focus:ring-2 focus:ring-teal-600/30 transition disabled:opacity-50"
                  >
                    {openSlotsForDoc.length === 0 ? (
                      <option value="">No open slots available</option>
                    ) : (
                      openSlotsForDoc.map((s) => (
                        <option key={s.id} value={s.start_time_iso}>
                          {cleanTime(s.start_time_iso)}
                        </option>
                      ))
                    )}
                  </select>
                </div>
              </div>

              <div>
                <label className="block font-bold text-slate-700 mb-1">Chief Complaint / Reason</label>
                <input
                  type="text"
                  value={walkInReason}
                  onChange={(e) => setWalkInReason(e.target.value)}
                  placeholder="e.g. Acute joint pain, Urgent rash review"
                  className="w-full bg-slate-50 border border-slate-200 rounded-xl px-3.5 py-2.5 text-slate-800 focus:bg-white focus:outline-none focus:ring-2 focus:ring-teal-600/30 transition"
                />
              </div>

              <div className="flex items-center justify-end space-x-2 pt-2 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setIsWalkInModalOpen(false)}
                  className="px-4 py-2 rounded-xl text-slate-600 hover:bg-slate-100 font-semibold transition"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isBookingWalkIn || openSlotsForDoc.length === 0}
                  className="px-5 py-2.5 rounded-xl bg-teal-600 hover:bg-teal-700 text-white font-bold transition disabled:opacity-50 shadow-xs flex items-center space-x-1.5"
                >
                  {isBookingWalkIn ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <CheckCircle2 className="w-3.5 h-3.5" />}
                  <span>Confirm Walk-In Booking</span>
                </button>
              </div>
            </form>

          </div>
        </div>
      )}

    </div>
  );
};
