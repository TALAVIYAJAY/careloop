"use client";

import React from "react";
import { Activity, MessageSquare, Database, FileText, ShieldCheck } from "lucide-react";

interface NavbarProps {
  activeTab: "patient" | "receptionist" | "design";
  setActiveTab: (tab: "patient" | "receptionist" | "design") => void;
  directivesCount: number;
}

export const Navbar: React.FC<NavbarProps> = ({ activeTab, setActiveTab, directivesCount }) => {
  return (
    <header className="bg-white border-b border-slate-200/80 sticky top-0 z-50 backdrop-blur-md bg-white/95 shrink-0">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 h-14 flex items-center justify-between">
        
        {/* CLINIC BRANDING */}
        <div className="flex items-center space-x-2.5">
          <div className="w-9 h-9 rounded-xl bg-teal-600 flex items-center justify-center text-white shadow-sm shadow-teal-600/20">
            <Activity className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center space-x-1.5">
              <span className="text-base font-bold tracking-tight text-slate-900">CareLoop</span>
              <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
            </div>
            <p className="text-[11px] text-slate-500 font-medium">Autonomous Clinical Front-Office System</p>
          </div>
        </div>

        {/* CENTER TABS (PATIENT PORTAL VS CLINIC FRONT DESK VS DESIGN NOTE) */}
        <nav className="flex items-center bg-slate-100/90 p-1 rounded-2xl border border-slate-200/60">
          <button
            onClick={() => setActiveTab("patient")}
            className={`px-3.5 py-1.5 text-xs font-semibold rounded-xl transition-all flex items-center space-x-1.5 ${
              activeTab === "patient"
                ? "bg-white text-slate-900 shadow-xs border border-slate-200/60"
                : "text-slate-600 hover:text-slate-900"
            }`}
          >
            <MessageSquare className="w-3.5 h-3.5 text-teal-600" />
            <span>Patient Portal</span>
          </button>

          <button
            onClick={() => setActiveTab("receptionist")}
            className={`px-3.5 py-1.5 text-xs font-semibold rounded-xl transition-all flex items-center space-x-1.5 ${
              activeTab === "receptionist"
                ? "bg-white text-slate-900 shadow-xs border border-slate-200/60"
                : "text-slate-600 hover:text-slate-900"
            }`}
          >
            <Database className="w-3.5 h-3.5 text-slate-700" />
            <span>Clinic Front Desk (EHR)</span>
          </button>

          <button
            onClick={() => setActiveTab("design")}
            className={`px-3.5 py-1.5 text-xs font-semibold rounded-xl transition-all flex items-center space-x-1.5 ${
              activeTab === "design"
                ? "bg-white text-slate-900 shadow-xs border border-slate-200/60"
                : "text-slate-600 hover:text-slate-900"
            }`}
          >
            <FileText className="w-3.5 h-3.5 text-blue-500" />
            <span>Design Note</span>
          </button>
        </nav>

        {/* RIGHT CLINICAL STATUS CHIP */}
        <div className="hidden sm:flex items-center space-x-2 text-xs">
          <div className="px-3 py-1 rounded-full bg-emerald-50 text-emerald-800 font-medium border border-emerald-200/70 flex items-center space-x-1.5 shadow-2xs">
            <ShieldCheck className="w-3.5 h-3.5 text-emerald-600" />
            <span>Safety Guardrails Active</span>
          </div>

          <div className="px-2.5 py-1 rounded-full bg-slate-100 text-slate-600 font-medium border border-slate-200/60 flex items-center space-x-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500"></span>
            <span>Gemini 3.5</span>
          </div>
        </div>

      </div>
    </header>
  );
};
