"use client";

import React from "react";
import { Gear, Cpu, Database, SlidersHorizontal, Key, ShieldCheck } from "@phosphor-icons/react";

export function SettingsScreen() {
  return (
    <div className="flex-1 max-w-5xl mx-auto px-6 py-10">
      <div className="pb-6 border-b border-slate-200 mb-8">
        <h1 className="text-2xl font-bold text-slate-900 tracking-tight">System Settings</h1>
        <p className="text-sm text-slate-500 mt-1">
          Configure model parameters, API credentials, and multi-agent execution constraints.
        </p>
      </div>

      <div className="space-y-6">
        {/* Model Configuration */}
        <div className="p-6 rounded-2xl bg-white border border-slate-200/80 shadow-xs">
          <div className="flex items-center gap-2.5 text-base font-bold text-slate-900 mb-2">
            <Cpu size={20} className="text-[#0284c7]" />
            <span>LLM Model Priorities</span>
          </div>
          <p className="text-xs text-slate-500 mb-4">
            FinSight prioritizes high-capacity models with automatic fallback upon quota exhaustion.
          </p>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="p-4 rounded-xl border border-emerald-200 bg-emerald-50/40">
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs font-bold text-emerald-900">Primary Models</span>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-100 text-emerald-800 font-semibold">Active</span>
              </div>
              <div className="font-mono text-sm font-semibold text-slate-800 mt-1">GPT-OSS 120B / 20B</div>
              <p className="text-[11px] text-slate-500 mt-1">Default for planner, synthesis, and critic QC nodes.</p>
            </div>

            <div className="p-4 rounded-xl border border-amber-200 bg-amber-50/40">
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs font-bold text-amber-900">Fallback Model</span>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-amber-100 text-amber-800 font-semibold">Standby</span>
              </div>
              <div className="font-mono text-sm font-semibold text-slate-800 mt-1">Qwen 3.8 27B</div>
              <p className="text-[11px] text-slate-500 mt-1">Automatically invoked on 429 rate limit or quota exhaustion.</p>
            </div>
          </div>
        </div>

        {/* Data Integrations */}
        <div className="p-6 rounded-2xl bg-white border border-slate-200/80 shadow-xs">
          <div className="flex items-center gap-2.5 text-base font-bold text-slate-900 mb-2">
            <Database size={20} className="text-purple-600" />
            <span>Data Providers &amp; Telemetry</span>
          </div>
          <p className="text-xs text-slate-500 mb-4">
            Live connectors and local disk caches for financial filings and market feeds.
          </p>

          <div className="space-y-3">
            <div className="flex items-center justify-between p-3.5 rounded-xl border border-slate-200 bg-slate-50/50">
              <div>
                <div className="text-xs font-bold text-slate-800">SEC EDGAR Vector Index</div>
                <div className="text-[11px] text-slate-500">1,063 pre-computed and indexed chunks for 10-K, 10-Q, and 8-K tables.</div>
              </div>
              <span className="text-[10px] font-mono px-2.5 py-1 rounded-full bg-emerald-100 text-emerald-800 font-semibold">Connected</span>
            </div>

            <div className="flex items-center justify-between p-3.5 rounded-xl border border-slate-200 bg-slate-50/50">
              <div>
                <div className="text-xs font-bold text-slate-800">Alpha Vantage Market Data &amp; News</div>
                <div className="text-[11px] text-slate-500">Quotes, 52-week telemetry, and semantic news sentiment feed.</div>
              </div>
              <span className="text-[10px] font-mono px-2.5 py-1 rounded-full bg-emerald-100 text-emerald-800 font-semibold">Rate-Limited &amp; Cached</span>
            </div>
          </div>
        </div>

        {/* Verification Thresholds */}
        <div className="p-6 rounded-2xl bg-white border border-slate-200/80 shadow-xs">
          <div className="flex items-center gap-2.5 text-base font-bold text-slate-900 mb-2">
            <ShieldCheck size={20} className="text-emerald-600" />
            <span>Audit &amp; Verification Rules</span>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mt-3">
            <div className="p-3 rounded-lg border border-slate-200 bg-slate-50 text-center">
              <div className="text-xs text-slate-500">Max Replanner Retries</div>
              <div className="text-lg font-bold text-slate-800 font-mono mt-0.5">3 Attempts</div>
            </div>
            <div className="p-3 rounded-lg border border-slate-200 bg-slate-50 text-center">
              <div className="text-xs text-slate-500">Numerical Precision</div>
              <div className="text-lg font-bold text-slate-800 font-mono mt-0.5">±0.05% Tol.</div>
            </div>
            <div className="p-3 rounded-lg border border-slate-200 bg-slate-50 text-center">
              <div className="text-xs text-slate-500">News Confidence Cap</div>
              <div className="text-lg font-bold text-slate-800 font-mono mt-0.5">Medium Max</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
