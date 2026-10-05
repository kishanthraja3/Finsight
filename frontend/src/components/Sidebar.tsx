"use client";

import React from "react";
import { 
  MagnifyingGlassPlus, 
  FileText, 
  Gear, 
  Sparkle, 
  PlusCircle, 
  ChartLineUp, 
  Article,
  Database,
  Lightning
} from "@phosphor-icons/react";

export type SidebarTab = "new_research" | "reports" | "settings";

interface SidebarProps {
  activeTab: SidebarTab;
  onSelectTab: (tab: SidebarTab) => void;
  isRunning?: boolean;
}

export function Sidebar({ activeTab, onSelectTab, isRunning }: SidebarProps) {
  const navItems = [
    {
      id: "new_research" as SidebarTab,
      label: "New Research",
      icon: PlusCircle,
      badge: isRunning ? "Running" : undefined,
      badgeColor: "bg-emerald-50 text-emerald-700 border-emerald-200"
    },
    {
      id: "reports" as SidebarTab,
      label: "Research Reports",
      icon: FileText,
    },
    {
      id: "settings" as SidebarTab,
      label: "Settings",
      icon: Gear,
    }
  ];

  return (
    <aside className="w-64 shrink-0 bg-white border-r border-slate-200/80 flex flex-col justify-between select-none min-h-[calc(100vh-64px)]">
      <div className="p-4">
        {/* Section title */}
        <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-600 px-3 py-2">
          Navigation
        </div>

        {/* Nav Items */}
        <nav className="flex flex-col gap-1.5 mt-1">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = activeTab === item.id;

            return (
              <button
                key={item.id}
                onClick={() => onSelectTab(item.id)}
                className={`w-full flex items-center justify-between px-3.5 py-2.5 rounded-xl text-sm font-medium transition-all text-left ${
                  isActive
                    ? "bg-[#e0f2fe] text-[#0284c7] shadow-xs"
                    : "text-slate-600 hover:text-slate-900 hover:bg-slate-50"
                }`}
              >
                <div className="flex items-center gap-3">
                  <Icon 
                    size={20} 
                    weight={isActive ? "bold" : "regular"} 
                    className={isActive ? "text-[#0284c7]" : "text-slate-400"} 
                  />
                  <span>{item.label}</span>
                </div>

                {item.badge && (
                  <span className={`text-[10px] font-mono px-2 py-0.5 rounded-full border ${item.badgeColor}`}>
                    {item.badge}
                  </span>
                )}
              </button>
            );
          })}
        </nav>

        {/* Quick Info card */}
        <div className="mt-8 p-3.5 rounded-xl bg-slate-50 border border-slate-200/60">
          <div className="flex items-center gap-2 mb-1.5">
            <Lightning size={16} weight="fill" className="text-amber-500" />
            <span className="text-xs font-semibold text-slate-800">Agentic Orchestration</span>
          </div>
          <p className="text-[11px] text-slate-700 leading-relaxed">
            Multi-agent pipeline synthesizing SEC disclosures with live telemetry &amp; critic validation.
          </p>
        </div>
      </div>

      {/* Footer Info */}
      <div className="p-4 border-t border-slate-100">
        <div className="flex items-center justify-between text-[11px] text-slate-600">
          <span>Engine v2.5</span>
          <span className="flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
            Active
          </span>
        </div>
      </div>
    </aside>
  );
}
