"use client";

import React, { useState } from "react";
import { 
  ArrowUpRight, 
  Sparkle, 
  ShieldCheck, 
  TreeStructure, 
  FileText, 
  MagnifyingGlass, 
  ArrowRight
} from "@phosphor-icons/react";

interface QueryScreenProps {
  onSubmit: (query: string) => void;
  isLoading: boolean;
}

export function QueryScreen({ onSubmit, isLoading }: QueryScreenProps) {
  const [query, setQuery] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim() || isLoading) return;
    onSubmit(query.trim());
  };

  const handleSelectExample = (exQuery: string) => {
    setQuery(exQuery);
  };

  return (
    <div className="w-full flex flex-col items-center px-4 sm:px-6 py-10 md:py-16 max-w-6xl mx-auto">
      {/* Eyebrow Pill */}
      <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-sky-50 border border-sky-200/80 text-[#0284c7] text-xs font-semibold tracking-wide mb-6 shadow-2xs">
        <Sparkle size={14} weight="fill" className="text-cyan-500" />
        <span>AUTONOMOUS MULTI-AGENT EQUITY RESEARCH</span>
      </div>

      {/* Main Hero Headline */}
      <h1 className="text-3xl sm:text-5xl font-extrabold tracking-tight text-center text-slate-900 max-w-3xl leading-[1.15] mb-4">
        Financial Intelligence with{" "}
        <span className="text-transparent bg-clip-text bg-gradient-to-r from-[#0099cc] via-[#00b4d8] to-[#00c5cc]">
          Agentic RAG &amp; Audit Verification
        </span>
      </h1>

      <p className="text-slate-500 text-center text-sm sm:text-base max-w-2xl mb-8 leading-relaxed">
        Autonomous multi-agent synthesis across SEC 10-K, 10-Q, and 8-K filings, real-time Alpha Vantage telemetry, automated critic QC, and surgical human-in-the-loop replanning.
      </p>

      {/* Double-Bezel Search Card */}
      <div className="w-full max-w-3xl rounded-3xl p-2 bg-white/70 border border-slate-200/90 shadow-lg backdrop-blur-xs mb-12">
        <form onSubmit={handleSubmit} className="bg-white rounded-2xl p-4 sm:p-5 border border-slate-100 shadow-inner">
          <div className="flex flex-col gap-3">
            <div className="flex items-start gap-3">
              <MagnifyingGlass size={22} className="text-slate-400 mt-1 shrink-0" />
              <textarea
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    handleSubmit(e);
                  }
                }}
                rows={2}
                placeholder="Ask any research question (e.g. 'Analyze NVIDIA's growth opportunities, revenue mix, and regulatory risks')..."
                className="w-full bg-transparent text-slate-900 placeholder-slate-400 focus:outline-none resize-none text-sm sm:text-base leading-relaxed font-sans"
              />
            </div>

            <div className="flex flex-wrap items-center justify-between gap-3 pt-3 border-t border-slate-100">
              <div className="flex items-center gap-2 text-xs text-slate-400 font-mono">
                <span>Enter to submit</span>
                <span>•</span>
                <span>Shift+Enter for newline</span>
              </div>

              {/* Start Research Button */}
              <button
                type="submit"
                disabled={!query.trim() || isLoading}
                className="group relative inline-flex items-center gap-2 px-6 py-2.5 rounded-full bg-[#00c5cc] hover:bg-[#00b2b8] text-white font-semibold text-sm transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed shadow-md hover:shadow-lg active:scale-98"
              >
                <span>{isLoading ? "Starting Research..." : "Start Research"}</span>
                <ArrowUpRight size={15} weight="bold" className="transition-transform group-hover:translate-x-0.5 group-hover:-translate-y-0.5" />
              </button>
            </div>
          </div>
        </form>
      </div>

      {/* Curated Institutional Research Prompts Section */}
      <div className="w-full max-w-5xl mb-12">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-slate-800">
            <Sparkle size={14} weight="fill" className="text-cyan-600" />
            <span>Curated Institutional Research Prompts</span>
          </div>
          <button 
            type="button"
            onClick={() => handleSelectExample("Analyze NVIDIA's financial performance, Data Center revenue trajectory, margin trends, and export control risks in Q2 FY2027.")}
            className="text-xs font-semibold text-[#0284c7] hover:underline flex items-center gap-1 cursor-pointer"
          >
            <span>View All Prompts</span>
            <ArrowRight size={12} weight="bold" />
          </button>
        </div>

        {/* 4 Prompt Cards Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {/* Card 1: NVIDIA */}
          <div 
            onClick={() => handleSelectExample("Analyze NVIDIA's financial performance, Data Center revenue trajectory, margin trends, and export control risks in Q2 FY2027.")}
            className="p-4 rounded-2xl bg-white border border-slate-200/80 hover:border-cyan-400/60 shadow-xs hover:shadow-md transition-all duration-200 cursor-pointer flex flex-col justify-between group"
          >
            <div>
              <div className="flex items-center justify-between mb-3">
                {/* NVIDIA Logo Square */}
                <div className="w-8 h-8 rounded-lg bg-[#76b900] flex items-center justify-center shadow-xs">
                  <svg className="w-5 h-5 text-white" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M7.74 7.26C6.73 8.36 6.13 9.87 6.13 11.5c0 3.32 2.45 6.07 5.72 6.44v1.8C7.54 19.34 4 15.82 4 11.5c0-2.31.95-4.41 2.5-5.91l1.24 1.67zm4.11-3.21v1.83c1.69.34 3.03 1.6 3.48 3.24.47 1.72-.08 3.51-1.39 4.67-.8.71-1.85 1.13-2.98 1.13v1.81c1.62 0 3.12-.6 4.27-1.63 1.9-1.69 2.7-4.28 2.02-6.78-.65-2.36-2.58-4.19-4.99-4.7L11.85 4.05z" />
                  </svg>
                </div>
                <span className="text-[10px] font-mono font-medium px-2 py-0.5 rounded-md bg-slate-100 text-slate-600 border border-slate-200/60">
                  NVDA 8-K + 10-K
                </span>
                <div className="w-7 h-7 rounded-full bg-slate-100 text-slate-500 group-hover:bg-cyan-50 group-hover:text-cyan-600 flex items-center justify-center transition-colors">
                  <ArrowRight size={13} weight="bold" />
                </div>
              </div>

              <h3 className="font-bold text-slate-900 text-sm mb-1.5 group-hover:text-cyan-600 transition-colors">
                NVIDIA Q2 FY2027 Deep Dive
              </h3>
              <p className="text-xs text-slate-500 leading-relaxed">
                Analyze NVIDIA&apos;s financial performance, Data Center revenue trajectory, margin trends, and export control risks in Q2 FY2027.
              </p>
            </div>
          </div>

          {/* Card 2: Apple */}
          <div 
            onClick={() => handleSelectExample("Evaluate Apple's Services revenue growth, gross margin impact, and Item 1A regulatory risks in European markets.")}
            className="p-4 rounded-2xl bg-white border border-slate-200/80 hover:border-cyan-400/60 shadow-xs hover:shadow-md transition-all duration-200 cursor-pointer flex flex-col justify-between group"
          >
            <div>
              <div className="flex items-center justify-between mb-3">
                {/* Apple Logo Square */}
                <div className="w-8 h-8 rounded-lg bg-[#1c1c1e] flex items-center justify-center shadow-xs">
                  <svg className="w-4 h-4 text-white" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M18.71 19.5c-.83 1.24-1.71 2.45-3.05 2.47-1.34.03-1.77-.79-3.29-.79-1.53 0-2 .77-3.27.82-1.31.05-2.3-1.32-3.14-2.53C4.25 17 2.94 12.45 4.7 9.39c.87-1.52 2.43-2.48 4.12-2.51 1.28-.02 2.5.87 3.29.87.78 0 2.26-1.07 3.81-.91.65.03 2.47.26 3.64 1.98-.09.06-2.17 1.28-2.15 3.81.03 3.02 2.65 4.03 2.68 4.04-.03.07-.42 1.44-1.38 2.83M15.97 6.37c.62-.75 1.04-1.8 0.92-2.85-.9.04-1.99.6-2.63 1.35-.57.65-1.06 1.72-.93 2.74 1 .08 2.03-.49 2.64-1.24z" />
                  </svg>
                </div>
                <span className="text-[10px] font-mono font-medium px-2 py-0.5 rounded-md bg-slate-100 text-slate-600 border border-slate-200/60">
                  AAPL 10-K + 10-Q
                </span>
                <div className="w-7 h-7 rounded-full bg-slate-100 text-slate-500 group-hover:bg-cyan-50 group-hover:text-cyan-600 flex items-center justify-center transition-colors">
                  <ArrowRight size={13} weight="bold" />
                </div>
              </div>

              <h3 className="font-bold text-slate-900 text-sm mb-1.5 group-hover:text-cyan-600 transition-colors">
                Apple Services &amp; Regulatory Scrutiny
              </h3>
              <p className="text-xs text-slate-500 leading-relaxed">
                Evaluate Apple&apos;s Services revenue growth, gross margin impact, and Item 1A regulatory risks in European markets.
              </p>
            </div>
          </div>

          {/* Card 3: Microsoft */}
          <div 
            onClick={() => handleSelectExample("Analyze Microsoft's Cloud and Azure revenue acceleration against capital expenditure requirements for AI datacenters.")}
            className="p-4 rounded-2xl bg-white border border-slate-200/80 hover:border-cyan-400/60 shadow-xs hover:shadow-md transition-all duration-200 cursor-pointer flex flex-col justify-between group"
          >
            <div>
              <div className="flex items-center justify-between mb-3">
                {/* Microsoft 4-Color Logo Square */}
                <div className="w-8 h-8 rounded-lg bg-white border border-slate-200 flex items-center justify-center p-1.5 shadow-xs">
                  <div className="grid grid-cols-2 gap-0.5 w-full h-full">
                    <div className="bg-[#f25022] rounded-[1px]" />
                    <div className="bg-[#7fba00] rounded-[1px]" />
                    <div className="bg-[#00a4ef] rounded-[1px]" />
                    <div className="bg-[#ffb900] rounded-[1px]" />
                  </div>
                </div>
                <span className="text-[10px] font-mono font-medium px-2 py-0.5 rounded-md bg-slate-100 text-slate-600 border border-slate-200/60">
                  MSFT 10-K + 8-K
                </span>
                <div className="w-7 h-7 rounded-full bg-slate-100 text-slate-500 group-hover:bg-cyan-50 group-hover:text-cyan-600 flex items-center justify-center transition-colors">
                  <ArrowRight size={13} weight="bold" />
                </div>
              </div>

              <h3 className="font-bold text-slate-900 text-sm mb-1.5 group-hover:text-cyan-600 transition-colors">
                Microsoft Cloud vs AI Datacenter Capex
              </h3>
              <p className="text-xs text-slate-500 leading-relaxed">
                Analyze Microsoft&apos;s Cloud and Azure revenue acceleration against capital expenditure requirements for AI datacenters.
              </p>
            </div>
          </div>

          {/* Card 4: Multi-Entity */}
          <div 
            onClick={() => handleSelectExample("Compare semiconductor supply chain dependencies and geopolitical trade exposure across NVIDIA and Apple.")}
            className="p-4 rounded-2xl bg-white border border-slate-200/80 hover:border-cyan-400/60 shadow-xs hover:shadow-md transition-all duration-200 cursor-pointer flex flex-col justify-between group"
          >
            <div>
              <div className="flex items-center justify-between mb-3">
                {/* Multi-Entity Purple Logo Square */}
                <div className="w-8 h-8 rounded-lg bg-gradient-to-tr from-purple-600 to-indigo-500 flex items-center justify-center shadow-xs">
                  <svg className="w-4 h-4 text-white" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                    <rect x="3" y="12" width="4" height="8" rx="1" />
                    <rect x="10" y="8" width="4" height="12" rx="1" />
                    <rect x="17" y="4" width="4" height="16" rx="1" />
                  </svg>
                </div>
                <span className="text-[10px] font-mono font-medium px-2 py-0.5 rounded-md bg-purple-50 text-purple-700 border border-purple-200/60">
                  Multi-Entity
                </span>
                <div className="w-7 h-7 rounded-full bg-slate-100 text-slate-500 group-hover:bg-cyan-50 group-hover:text-cyan-600 flex items-center justify-center transition-colors">
                  <ArrowRight size={13} weight="bold" />
                </div>
              </div>

              <h3 className="font-bold text-slate-900 text-sm mb-1.5 group-hover:text-cyan-600 transition-colors">
                Cross-Company Risk &amp; Supply Chain
              </h3>
              <p className="text-xs text-slate-500 leading-relaxed">
                Compare semiconductor supply chain dependencies and geopolitical trade exposure across NVIDIA and Apple.
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Platform Pillars Section */}
      <div className="w-full max-w-5xl grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Pillar 1 */}
        <div className="p-5 rounded-2xl bg-white border border-slate-200/80 shadow-xs flex items-start gap-4">
          <div className="w-10 h-10 rounded-xl bg-sky-50 border border-sky-100 flex items-center justify-center shrink-0">
            <TreeStructure size={22} className="text-[#0284c7]" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-slate-900 mb-1">Agentic RAG with 4 Criteria</h3>
            <p className="text-xs text-slate-500 leading-relaxed">
              Multi-turn retrieval loop auditing coverage, source quality, recency, and contradictions across SEC tables and items.
            </p>
          </div>
        </div>

        {/* Pillar 2 */}
        <div className="p-5 rounded-2xl bg-white border border-slate-200/80 shadow-xs flex items-start gap-4">
          <div className="w-10 h-10 rounded-xl bg-emerald-50 border border-emerald-100 flex items-center justify-center shrink-0">
            <ShieldCheck size={22} className="text-emerald-600" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-slate-900 mb-1">Targeted HITL Re-Planning</h3>
            <p className="text-xs text-slate-500 leading-relaxed">
              Human reviewers audit discrete findings. Rejections trigger surgical re-runs only for affected categories.
            </p>
          </div>
        </div>

        {/* Pillar 3 */}
        <div className="p-5 rounded-2xl bg-white border border-slate-200/80 shadow-xs flex items-start gap-4">
          <div className="w-10 h-10 rounded-xl bg-purple-50 border border-purple-100 flex items-center justify-center shrink-0">
            <FileText size={22} className="text-purple-600" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-slate-900 mb-1">Citable SEC Disclosures</h3>
            <p className="text-xs text-slate-500 leading-relaxed">
              Every synthesized metric is tagged with deterministic chunk citations linked back to original 10-K, 10-Q, and 8-K tables.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
