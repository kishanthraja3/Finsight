"use client";

import React from "react";
import { ChartLineUp, Database, Cpu, Plus } from "@phosphor-icons/react";

interface NavbarProps {
  activeScreen: "query" | "live" | "review" | "final";
  onNavigateHome: () => void;
  runStatus?: string;
  runId?: string;
  activeModel?: string;
  isFallback?: boolean;
}

export function Navbar({ activeScreen, onNavigateHome, runStatus, runId, activeModel, isFallback }: NavbarProps) {
  const formatModelName = (name?: string) => {
    if (!name) return "GPT-OSS 120B";
    if (name.includes("120b")) return "GPT-OSS 120B";
    if (name.includes("20b")) return "GPT-OSS 20B";
    if (name.includes("qwen")) return "Qwen 3.8 27B (Fallback)";
    return name;
  };

  const getStatusBadge = () => {
    if (!runStatus) return null;
    const statusLower = runStatus.toLowerCase();
    if (statusLower.includes("complete")) {
      return <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200 font-semibold uppercase">COMPLETE</span>;
    }
    if (statusLower.includes("fail") || statusLower.includes("error")) {
      return <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-rose-50 text-rose-700 border border-rose-200 font-semibold uppercase">FAILED</span>;
    }
    if (statusLower.includes("awaiting")) {
      return <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-amber-50 text-amber-700 border border-amber-200 font-semibold uppercase">REVIEW</span>;
    }
    return <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200 font-semibold uppercase">RUNNING</span>;
  };

  return (
    <header className="sticky top-0 z-40 border-b border-slate-200/80 bg-white shadow-xs">
      <div className="w-full px-4 sm:px-6 h-16 flex items-center justify-between">
        {/* Brand */}
        <div 
          onClick={onNavigateHome}
          className="flex items-center gap-3 cursor-pointer group select-none"
        >
          <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-cyan-600 to-slate-900 p-[1px] shadow-sm transition-transform group-hover:scale-105">
            <div className="w-full h-full bg-[#0a1120] rounded-[11px] flex items-center justify-center">
              <ChartLineUp size={20} weight="bold" className="text-cyan-400" />
            </div>
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-extrabold text-xl tracking-tight text-slate-900 font-sans">
                Fin<span className="text-[#0284c7]">Sight</span>
              </span>
              <span className="text-[10px] font-mono font-bold tracking-wider uppercase px-2 py-0.5 rounded-full bg-sky-50 text-sky-700 border border-sky-200">
                AGENTIC V2.5
              </span>
            </div>
            <p className="text-[11px] text-slate-600 hidden sm:block">Multi-Agent Financial Research Intelligence</p>
          </div>
        </div>

        {/* Status Indicators */}
        <div className="flex items-center gap-2.5 sm:gap-3">
          {runId && (
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-slate-50 border border-slate-200/80 text-xs font-mono text-slate-700">
              <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
              <span>{runId}</span>
              {getStatusBadge()}
            </div>
          )}

          {/* Model Badge */}
          <div className="hidden md:flex items-center gap-2 px-3 py-1.5 rounded-xl bg-slate-50 border border-slate-200/80 text-xs text-slate-700">
            <Cpu size={15} className={isFallback ? "text-amber-500" : "text-sky-600"} />
            <span className="font-mono text-[11px] font-medium">{formatModelName(activeModel)}</span>
            {isFallback && (
              <span className="text-[9px] px-1.5 py-0.2 rounded bg-amber-100 text-amber-800 font-mono font-bold border border-amber-200">
                FALLBACK
              </span>
            )}
          </div>

          {/* Chunks Badge */}
          <div className="hidden lg:flex items-center gap-2 px-3 py-1.5 rounded-xl bg-slate-50 border border-slate-200/80 text-xs text-slate-700">
            <Database size={15} className="text-sky-600" />
            <span className="font-mono text-[11px] font-medium">1,063 SEC Chunks</span>
          </div>

          {/* + New Query Button */}
          <button
            onClick={onNavigateHome}
            className="inline-flex items-center gap-1.5 text-xs font-semibold px-3.5 py-2 rounded-xl bg-[#00a3c4] hover:bg-[#0091af] text-white shadow-xs transition-all active:scale-95"
          >
            <Plus size={14} weight="bold" />
            <span>New Query</span>
          </button>
        </div>
      </div>
    </header>
  );
}
