"use client";

import React from "react";
import { FileText, Shield, Sparkles, Server, AlertTriangle } from "lucide-react";

export const DesignNoteTab: React.FC = () => {
  return (
    <div className="h-full flex flex-col overflow-hidden max-w-5xl mx-auto w-full bg-white rounded-2xl border border-slate-200 shadow-xs">
      
      {/* HEADER (SHRINK-0) */}
      <div className="border-b border-slate-200 p-3 px-5 bg-slate-50/60 shrink-0 flex items-center justify-between">
        <div>
          <span className="text-[10px] font-bold uppercase tracking-wider text-teal-600">
            2care.ai Take-Home Submission
          </span>
          <h2 className="text-sm sm:text-base font-bold text-slate-900">
            CareLoop: 1-Page Engineering Design Note
          </h2>
        </div>
        <span className="text-[10px] text-slate-500 bg-white border border-slate-200 px-2.5 py-1 rounded-md font-medium">
          Architectural Decisions
        </span>
      </div>

      {/* SCROLLABLE BODY (SCROLLS INTERNALLY ONLY WITHIN THE CARD, PRESERVING FULL VIEWPORT) */}
      <div className="flex-1 min-h-0 overflow-y-auto p-4 sm:p-6 space-y-5">
        
        {/* QUESTION 1 */}
        <div className="space-y-2.5">
          <h3 className="text-sm font-bold text-slate-900 flex items-center space-x-2">
            <span className="w-5 h-5 rounded-full bg-teal-100 text-teal-800 flex items-center justify-center text-[11px] font-bold">1</span>
            <span>Where Transcript-Only Judges Fail & Why Dual-Layer Verification is Mandatory</span>
          </h3>
          <p className="text-xs text-slate-700 leading-relaxed">
            In conversational healthcare agents, an LLM judge evaluating only transcripts suffers from <strong>semantic hallucination vulnerability</strong>: an agent can generate a reassuring response like <em>&quot;I&apos;ve successfully booked your 10:00 AM appointment with Dr. Chen&quot;</em> while failing to execute the backend tool or violating atomic slot constraints. In healthcare, an unrecorded booking means a patient arrives to an empty office—a severe clinical failure.
          </p>
          <div className="p-3 bg-slate-50 rounded-xl border border-slate-200 text-xs text-slate-800">
            <strong>CareLoop&apos;s Solution:</strong> We decoupled evaluation into <strong>Layer A (Deterministic EHR State Assertions)</strong> and <strong>Layer B (Semantic Clinical Rubric)</strong>. Layer A directly inspects the SQLite database before Layer B evaluates empathy. If the database row does not exist, the run is immediately awarded 0/100, preventing silent failures.
          </div>
        </div>

        {/* QUESTION 2 */}
        <div className="space-y-2.5">
          <h3 className="text-sm font-bold text-slate-900 flex items-center space-x-2">
            <span className="w-5 h-5 rounded-full bg-teal-100 text-teal-800 flex items-center justify-center text-[11px] font-bold">2</span>
            <span>Closing the Self-Improvement Loop Without Regressions</span>
          </h3>
          <p className="text-xs text-slate-700 leading-relaxed">
            Standard agent updates cause <strong>catastrophic forgetting</strong> or prompt bloat when full transcripts are injected as few-shot examples. CareLoop implements an automated <strong>Failure Reflector &rarr; Policy Generator &rarr; Directive Store</strong> pipeline.
          </p>
          <ul className="text-xs text-slate-700 space-y-1 list-disc list-inside">
            <li><strong>Failure Reflector:</strong> Isolates the root cause into structured failure types (<code className="bg-slate-100 px-1 py-0.5 rounded">EMERGENCY_TRIAGE_BREACH</code>, <code className="bg-slate-100 px-1 py-0.5 rounded">SLOT_COLLISION</code>).</li>
            <li><strong>Scoped Directives:</strong> Generates concise, negative and positive behavioral constraints injected into an isolated <code className="bg-slate-100 px-1 py-0.5 rounded">&lt;clinical_directives&gt;</code> prompt block without modifying foundational tool signatures.</li>
            <li><strong>Regression Harness:</strong> The entire benchmark suite is re-executed. A policy update is only committed if it passes all previously passing scenarios. Our eval demonstrates an <strong>82.0% &rarr; 98.0% (+16.0 pts)</strong> gain with <strong>0 regressions</strong>.</li>
          </ul>
        </div>

        {/* QUESTION 3 */}
        <div className="space-y-2.5">
          <h3 className="text-sm font-bold text-slate-900 flex items-center space-x-2">
            <span className="w-5 h-5 rounded-full bg-teal-100 text-teal-800 flex items-center justify-center text-[11px] font-bold">3</span>
            <span>Scaling to Production: Temporal Orchestration & Distributed State</span>
          </h3>
          <p className="text-xs text-slate-700 leading-relaxed">
            While this take-home employs SQLite and in-memory session handling for single-command portability, a production-grade hospital system requires <strong>durable execution</strong>. In real outpatient environments, patient sessions experience connection dropouts, browser refresh, and asynchronous doctor review delays.
          </p>
          <p className="text-xs text-slate-700 leading-relaxed">
            In production, we replace local sessions with <strong>Temporal workflows</strong> where each patient interaction is a durable workflow instance. Slot reservations utilize two-phase commit locks with automated TTL timeouts. Clinical directives are stored in a distributed vector policy database, enabling semantic retrieval of relevant directives based on patient symptom embeddings.
          </p>
        </div>

        {/* QUESTION 4 */}
        <div className="space-y-2.5">
          <h3 className="text-sm font-bold text-slate-900 flex items-center space-x-2">
            <span className="w-5 h-5 rounded-full bg-teal-100 text-teal-800 flex items-center justify-center text-[11px] font-bold">4</span>
            <span>Clinical Edge Cases & Safety Guardrails</span>
          </h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
            <div className="p-3 bg-red-50 rounded-xl border border-red-200">
              <strong className="text-red-900 flex items-center space-x-1.5 mb-1">
                <AlertTriangle className="w-4 h-4 text-red-600" />
                <span>Emergency Preemption</span>
              </strong>
              <p className="text-red-800">
                Cardiac, respiratory, or stroke red-flags preempt the agent immediately, locking appointment booking and instructing the caller to dial 911 / head to an ER.
              </p>
            </div>
            <div className="p-3 bg-purple-50 rounded-xl border border-purple-200">
              <strong className="text-purple-900 flex items-center space-x-1.5 mb-1">
                <Shield className="w-4 h-4 text-purple-600" />
                <span>Prescription Refusal</span>
              </strong>
              <p className="text-purple-800">
                Strict scope boundaries prevent the agent from giving medical diagnoses or prescribing pharmaceuticals, offering instead an in-person physician consultation.
              </p>
            </div>
          </div>
        </div>

      </div>

    </div>
  );
};
