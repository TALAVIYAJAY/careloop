"use client";

import React, { useState, useEffect } from "react";
import { Navbar } from "@/components/Navbar";
import { PatientPortalTab } from "@/components/PatientPortalTab";
import { ReceptionistEhrTab } from "@/components/ReceptionistEhrTab";
import { DesignNoteTab } from "@/components/DesignNoteTab";
import { fetchSystemStatus } from "@/lib/api";

export default function Home() {
  const [activeTab, setActiveTab] = useState<"patient" | "receptionist" | "design">("patient");
  const [directivesCount, setDirectivesCount] = useState<number>(0);

  const loadStatus = async () => {
    try {
      const status = await fetchSystemStatus();
      setDirectivesCount(status.active_directives_count);
    } catch (err) {
      console.warn("Could not fetch status, using default:", err);
    }
  };

  useEffect(() => {
    loadStatus();
  }, [activeTab]);

  return (
    <div className="h-screen h-[100dvh] flex flex-col bg-slate-50 text-slate-900 overflow-hidden">
      <Navbar
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        directivesCount={directivesCount}
      />

      <main className="flex-1 min-h-0 max-w-7xl w-full mx-auto px-3 sm:px-4 py-2 sm:py-2.5 flex flex-col overflow-hidden">
        {activeTab === "patient" && <PatientPortalTab onDatabaseChange={loadStatus} />}
        {activeTab === "receptionist" && <ReceptionistEhrTab onDirectivesUpdated={loadStatus} />}
        {activeTab === "design" && <DesignNoteTab />}
      </main>
    </div>
  );
}
