"use client";

import React, { useState, useEffect } from "react";
import { Navbar } from "@/components/Navbar";
import { PatientPortalTab } from "@/components/PatientPortalTab";
import { ReceptionistEhrTab } from "@/components/ReceptionistEhrTab";
import { DesignNoteTab } from "@/components/DesignNoteTab";
import { fetchSystemStatus } from "@/lib/api";

export default function Home() {
  const [activeTab, setActiveTab] = useState<"patient" | "receptionist" | "design">(() => {
    if (typeof window !== "undefined") {
      try {
        const saved = localStorage.getItem("careloop_active_tab");
        if (saved === "receptionist" || saved === "design" || saved === "patient") {
          return saved;
        }
      } catch (e) {
        console.warn("Could not load activeTab from localStorage:", e);
      }
    }
    return "patient";
  });
  const [directivesCount, setDirectivesCount] = useState<number>(0);
  const [dbVersion, setDbVersion] = useState<number>(0);

  const loadStatus = async () => {
    try {
      const status = await fetchSystemStatus();
      setDirectivesCount(status.active_directives_count);
    } catch (err) {
      console.warn("Could not fetch status, using default:", err);
    }
  };

  const handleDatabaseChange = () => {
    setDbVersion((v) => v + 1);
    loadStatus();
  };

  useEffect(() => {
    if (typeof window !== "undefined") {
      try {
        localStorage.setItem("careloop_active_tab", activeTab);
      } catch (e) {
        console.warn("Could not save activeTab to localStorage:", e);
      }
    }
    loadStatus();
    if (activeTab === "receptionist") {
      // Auto-sync EHR database whenever switching to front desk
      setDbVersion((v) => v + 1);
    }
  }, [activeTab]);

  return (
    <div className="h-screen h-[100dvh] flex flex-col bg-slate-50 text-slate-900 overflow-hidden">
      <Navbar
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        directivesCount={directivesCount}
      />

      <main className="flex-1 min-h-0 max-w-7xl w-full mx-auto px-3 sm:px-4 py-2 sm:py-2.5 flex flex-col overflow-hidden">
        <div className={`h-full flex flex-col overflow-hidden ${activeTab === "patient" ? "" : "hidden"}`}>
          <PatientPortalTab onDatabaseChange={handleDatabaseChange} />
        </div>
        <div className={`h-full flex flex-col overflow-hidden ${activeTab === "receptionist" ? "" : "hidden"}`}>
          <ReceptionistEhrTab onDirectivesUpdated={loadStatus} dbVersion={dbVersion} />
        </div>
        <div className={`h-full flex flex-col overflow-hidden ${activeTab === "design" ? "" : "hidden"}`}>
          <DesignNoteTab />
        </div>
      </main>
    </div>
  );
}
