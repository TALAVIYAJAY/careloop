/**
 * CareLoop Client API Library
 * Handles communication with the FastAPI backend with complete TypeScript typing.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

export interface SystemStatus {
  status: string;
  model: string;
  active_directives_count: number;
  doctors_count: number;
  appointments_count: number;
}

export interface ToolCallExecution {
  tool_name: string;
  arguments: Record<string, any>;
  result?: any;
}

export interface ActiveAppointmentItem {
  id: string;
  doctor_id?: string;
  doctor_name: string;
  specialty?: string;
  slot_iso: string;
  status: string;
  visit_type?: string;
  patient_id?: string;
}

export interface PatientSessionState {
  patient_name: string;
  patient_phone?: string;
  patient_id?: string;
  active_doctor_name: string;
  selected_slot: string;
  appointment_id?: string;
  active_appointments?: ActiveAppointmentItem[];
  stage?: string;
  triage_level: string;
  emergency_triggered: boolean;
}

export interface ChatResponse {
  response: string;
  session: PatientSessionState;
  recent_tool_calls: ToolCallExecution[];
  emergency_triggered: boolean;
}

export interface ScenarioEvaluation {
  scenario_id: string;
  scenario_name: string;
  category: string;
  passed: boolean;
  total_score: number;
  state_assert_passed: boolean;
  state_assert_details: string[];
  rubric: {
    clinical_safety: number;
    protocol_adherence: number;
    info_gathering_empathy: number;
    goal_completion: number;
  };
  failure_reason?: string;
}

export interface SuiteEvaluationSummary {
  total_scenarios: number;
  passed_scenarios: number;
  failed_scenarios: number;
  composite_score: number;
  pass_rate_percentage: number;
  scenario_results: ScenarioEvaluation[];
}

export interface ReflectionAnalysis {
  scenario_id: string;
  scenario_name: string;
  failure_type: string;
  root_cause: string;
  vulnerability: string;
  policy_recommendation: string;
}

export interface ClinicalDirective {
  id: string;
  title: string;
  priority: string;
  scope: string;
  instruction: string;
  rational: string;
}

export interface EvaluationLoopResult {
  baseline_summary: SuiteEvaluationSummary;
  reflected_analyses: ReflectionAnalysis[];
  generated_directives: ClinicalDirective[];
  improved_summary: SuiteEvaluationSummary;
  score_delta: number;
  regressions_detected: number;
  loop_closed_successfully: boolean;
}

export interface DoctorRecord {
  id: string;
  name: string;
  specialty: string;
  available_slots: string[];
}

export interface PatientRecord {
  id: string;
  name: string;
  phone: string;
  created_at_iso: string;
  notes?: string;
}

export interface AppointmentRecord {
  id: string;
  patient_id?: string;
  patient_name: string;
  patient_phone?: string;
  doctor_name: string;
  doctor_id: string;
  specialty?: string;
  slot_time: string;
  status: string;
  visit_type?: string;
}

export interface EscalationRecord {
  id: string;
  patient_name: string;
  emergency_type: string;
  action_taken: string;
  escalated_at: string;
}

export interface DatabaseState {
  doctors: DoctorRecord[];
  appointments: AppointmentRecord[];
  patients?: PatientRecord[];
  escalations: EscalationRecord[];
}

// ============================================================
// API CALL FUNCTIONS
// ============================================================

export async function fetchSystemStatus(): Promise<SystemStatus> {
  const res = await fetch(`${API_BASE}/api/status`);
  if (!res.ok) throw new Error("Failed to fetch system status");
  return res.json();
}

export async function sendChatMessage(sessionId: string, message: string): Promise<ChatResponse> {
  const res = await fetch(`${API_BASE}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId, message }),
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({ detail: "Unknown error" }));
    throw new Error(errorData.detail || "Chat request failed");
  }
  return res.json();
}

export async function resetChatSession(sessionId: string): Promise<void> {
  await fetch(`${API_BASE}/api/chat/reset`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId }),
  });
}

export async function runEvaluationLoop(): Promise<EvaluationLoopResult> {
  const res = await fetch(`${API_BASE}/api/evaluation/run`, {
    method: "POST",
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({ detail: "Evaluation failed" }));
    throw new Error(errorData.detail || "Evaluation loop failed");
  }
  return res.json();
}

export async function fetchDatabaseState(): Promise<DatabaseState> {
  const res = await fetch(`${API_BASE}/api/database`);
  if (!res.ok) throw new Error("Failed to fetch database state");
  return res.json();
}

export async function resetDatabaseSeeds(): Promise<void> {
  const res = await fetch(`${API_BASE}/api/database/reset`, {
    method: "POST",
  });
  if (!res.ok) throw new Error("Failed to reset database");
}

export async function fetchAvailableSlots(specialty?: string, doctorName?: string): Promise<any[]> {
  const params = new URLSearchParams();
  if (specialty) params.append("specialty", specialty);
  if (doctorName) params.append("doctor_name", doctorName);
  const res = await fetch(`${API_BASE}/api/slots?${params.toString()}`);
  if (!res.ok) throw new Error("Failed to fetch available slots");
  const data = await res.json();
  return data.slots || [];
}

export async function bookWalkInAppointment(payload: {
  patient_name: string;
  patient_phone: string;
  doctor_id: string;
  slot_iso: string;
  reason?: string;
}): Promise<any> {
  const res = await fetch(`${API_BASE}/api/appointments/walk-in`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({ detail: "Walk-in booking failed" }));
    throw new Error(errorData.detail || "Walk-in booking failed");
  }
  return res.json();
}

export async function cancelAppointment(appointmentId: string): Promise<void> {
  const res = await fetch(`${API_BASE}/api/appointments/cancel`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ appointment_id: appointmentId }),
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({ detail: "Failed to cancel appointment" }));
    throw new Error(errorData.detail || "Cancellation failed");
  }
}

export interface AgentManifestItem {
  id: string;
  name: string;
  role: string;
  level: "ORCHESTRATOR" | "PRIMARY" | "SUBAGENT" | "META" | string;
  mandate: string;
  authority_scope: string;
  status: string;
}

export interface ClinicalDirectiveItem {
  id: string;
  trigger_condition: string;
  directive_text: string;
  category: string;
  target_subagent: string;
  status: "ACTIVE" | "CANDIDATE" | "QUARANTINED" | string;
  canary_verification_score?: number | null;
  shadow_verification_notes?: string | null;
  created_at_iso: string;
}

export interface EvolutionSimulateResult {
  status: string;
  scenario_tested: string;
  baseline_score: number;
  improved_score: number;
  score_delta: number;
  regressions_detected: number;
  active_directives: ClinicalDirectiveItem[];
  reflections: any[];
}

export async function fetchAgentManifest(): Promise<AgentManifestItem[]> {
  const res = await fetch(`${API_BASE}/api/agents`);
  if (!res.ok) throw new Error("Failed to fetch agent hierarchy");
  return res.json();
}

export async function fetchDirectives(): Promise<ClinicalDirectiveItem[]> {
  const res = await fetch(`${API_BASE}/api/directives`);
  if (!res.ok) throw new Error("Failed to fetch directives");
  return res.json();
}

export async function clearDirectives(): Promise<void> {
  const res = await fetch(`${API_BASE}/api/directives/clear`, {
    method: "POST",
  });
  if (!res.ok) throw new Error("Failed to clear directives");
}

export async function simulateAutonomousEvolution(): Promise<EvolutionSimulateResult> {
  const res = await fetch(`${API_BASE}/api/evolution/simulate`, {
    method: "POST",
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({ detail: "Simulation failed" }));
    throw new Error(errorData.detail || "Simulation failed");
  }
  return res.json();
}

