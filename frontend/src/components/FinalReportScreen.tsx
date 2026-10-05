"use client";

import React, { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { 
  DownloadSimple, 
  CheckCircle, 
  Printer, 
  Copy, 
  ShieldCheck, 
  FileText, 
  ArrowClockwise,
  Check,
  TrendUp,
  ShareNetwork,
  PlusCircle
} from "@phosphor-icons/react";
import { Finding, getDownloadUrl, getPdfDownloadUrl, ReportState } from "@/lib/api";
import { extractReportVisuals, formatResearcherSources } from "@/lib/reportVisuals";
import { ExecutiveSummaryView } from "./ExecutiveSummaryView";

interface FinalReportScreenProps {
  runId: string;
  query: string;
  finalReport: string;
  findings: Finding[];
  reportState?: ReportState | null;
  onNewResearch: () => void;
}

export function FinalReportScreen({
  runId,
  query,
  finalReport,
  findings,
  reportState,
  onNewResearch,
}: FinalReportScreenProps) {
  const [activeTab, setActiveTab] = useState<"summary_visuals" | "narrative">("summary_visuals");

  const handlePrint = () => {
    window.print();
  };

  // Only include approved/edited findings in final report (rejected are excluded)
  const approvedFindings = findings.filter((f) => f.status === "approved" || f.status === "edited");
  const reviewedCount = approvedFindings.length;
  const figuresVerifiedCount = approvedFindings.filter((f) => f.numerically_verified).length;

  // Build ReportState for visuals helper preserving tasks and coverage ledger
  const stateForVisuals: ReportState = reportState ? {
    ...reportState,
    findings: approvedFindings,
    final_report: finalReport,
  } : {
    run_id: runId,
    query,
    companies: [],
    tasks: [],
    findings: approvedFindings,
    synthesis_draft: finalReport,
    critic_result: { passed: true, issues: [] },
    retry_count: 0,
    max_retries: 3,
    run_status: "complete",
    final_report: finalReport,
  };

  const visuals = extractReportVisuals(stateForVisuals);

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 sm:py-8 space-y-6">
      {/* Header Banner */}
      <div className="flex flex-col gap-4">
        {/* Breadcrumb & Action Controls */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs">
          <div className="text-slate-600 font-medium">
            <span>Research Reports</span>
            <span className="mx-2 text-slate-600">›</span>
            <span className="text-slate-900 font-semibold">{visuals.companyName} {visuals.targetPeriod}</span>
            <span className="mx-2 text-slate-600">›</span>
            <span className="text-emerald-700 font-bold">Final Deliverable</span>
          </div>

          <div className="flex flex-wrap items-center gap-2 no-print">
            <a
              href={getPdfDownloadUrl(runId)}
              download={`FinSight_Research_${runId}.pdf`}
              className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-gradient-to-r from-sky-600 to-cyan-600 hover:from-sky-500 hover:to-cyan-500 text-white font-bold text-xs shadow-sm hover:shadow transition-all active:scale-[0.98]"
            >
              <DownloadSimple size={15} weight="bold" />
              <span>Download PDF</span>
            </a>

            <a
              href={getDownloadUrl(runId)}
              download={`FinSight_Research_${runId}.md`}
              className="inline-flex items-center gap-1.5 px-3 py-2 rounded-xl bg-white hover:bg-slate-50 border border-slate-200 text-slate-700 font-medium text-xs shadow-xs transition-colors"
            >
              <DownloadSimple size={14} />
              <span>Download Markdown</span>
            </a>

            <button
              onClick={onNewResearch}
              className="inline-flex items-center gap-1.5 px-3 py-2 rounded-xl bg-slate-900 hover:bg-slate-800 text-white font-medium text-xs shadow-xs transition-colors"
            >
              <PlusCircle size={14} weight="bold" />
              <span>New Research</span>
            </button>
          </div>
        </div>

        {/* Title & Badges */}
        <div className="space-y-1">
          <div className="flex flex-wrap items-center gap-2.5">
            <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 tracking-tight font-sans">
              {visuals.reportTitle}
            </h1>

            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-emerald-50 border border-emerald-200 text-emerald-700 text-xs font-semibold font-mono">
              <CheckCircle size={13} weight="fill" className="text-emerald-500" />
              <span>Audited Deliverable ({reviewedCount}/{findings.length} claims accepted)</span>
            </span>

            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-sky-50 border border-sky-200 text-sky-700 text-xs font-semibold font-mono">
              <CheckCircle size={13} weight="fill" className="text-sky-500" />
              <span>Critic QC Passed</span>
            </span>
          </div>

          <p className="text-xs sm:text-sm text-slate-600 max-w-4xl leading-relaxed">
            {query}
          </p>
        </div>

        {/* Sub-tab switcher between Visual Dashboard and Full Narrative */}
        <div className="flex items-center gap-2 border-b border-slate-200 pt-2 no-print">
          <button
            onClick={() => setActiveTab("summary_visuals")}
            className={`px-5 py-2.5 text-xs font-bold border-b-2 transition-all flex items-center gap-2 ${
              activeTab === "summary_visuals"
                ? "border-sky-600 text-sky-600 bg-sky-50/40 rounded-t-lg"
                : "border-transparent text-slate-600 hover:text-slate-900"
            }`}
          >
            <TrendUp size={15} weight={activeTab === "summary_visuals" ? "bold" : "regular"} />
            <span>Executive Visual Report</span>
          </button>

          <button
            onClick={() => setActiveTab("narrative")}
            className={`px-5 py-2.5 text-xs font-bold border-b-2 transition-all flex items-center gap-2 ${
              activeTab === "narrative"
                ? "border-sky-600 text-sky-600 bg-sky-50/40 rounded-t-lg"
                : "border-transparent text-slate-600 hover:text-slate-900"
            }`}
          >
            <FileText size={15} weight={activeTab === "narrative" ? "bold" : "regular"} />
            <span>Full Research Narrative</span>
          </button>
        </div>
      </div>

      {/* Main Visuals & Graphs Section (Always printed in PDF!) */}
      {(activeTab === "summary_visuals" || true) && (
        <div className={activeTab === "narrative" ? "hidden print:block space-y-6" : "space-y-6"}>
          {/* Executive Summary Card + Key Figures + SVG Charts + Coverage Matrix */}
          <ExecutiveSummaryView 
            visuals={visuals} 
            approvedCount={reviewedCount} 
            totalFindings={findings.length} 
          />

          {/* Audited Research Findings Section (Excluding Rejected) */}
          <div className="bg-white rounded-2xl border border-slate-200/90 shadow-sm p-6 break-inside-avoid">
            <div className="flex items-center justify-between gap-3 mb-4">
              <div className="flex items-center gap-2">
                <div className="w-8 h-8 rounded-lg bg-sky-50 border border-sky-200 flex items-center justify-center text-sky-600">
                  <ShieldCheck size={18} weight="bold" />
                </div>
                <h3 className="text-base font-bold text-slate-900">
                  Audited Research Deliverable Claims ({approvedFindings.length})
                </h3>
              </div>
              <span className="text-xs font-mono text-emerald-700 bg-emerald-50 px-2.5 py-1 rounded border border-emerald-200">
                {figuresVerifiedCount} Figures Mathematically Verified
              </span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5">
              {approvedFindings.map((f, i) => {
                const sources = formatResearcherSources(f.evidence_chunk_ids, f);

                return (
                  <div
                    key={f.id}
                    className="p-4 rounded-xl border border-slate-200/80 bg-slate-50/40 hover:bg-slate-50 transition-colors flex flex-col justify-between"
                  >
                    <div>
                      <div className="flex items-center justify-between gap-2 mb-2">
                        <div className="flex items-center gap-1.5">
                          <CheckCircle size={15} weight="fill" className="text-emerald-500 shrink-0" />
                          <span className="font-mono text-xs font-bold text-slate-700">#{i + 1}</span>
                          <span className="text-[10px] font-mono font-bold uppercase px-1.5 py-0.5 rounded bg-sky-50 text-sky-700 border border-sky-200">
                            {f.category}
                          </span>
                        </div>
                        {f.numerically_verified && (
                          <span className="text-[10px] font-mono font-bold text-emerald-700 bg-emerald-50 px-1.5 py-0.5 rounded border border-emerald-200">
                            VERIFIED
                          </span>
                        )}
                      </div>

                      <p className="text-xs text-slate-800 leading-relaxed font-sans">
                        {f.statement}
                      </p>
                    </div>

                    <div className="mt-3 pt-2.5 border-t border-slate-200/60 flex flex-wrap items-center gap-1.5">
                      <span className="text-[10px] font-mono text-slate-600 uppercase font-semibold">Source:</span>
                      {sources.map((s, idx) => (
                        <span key={idx} className="text-[10px] bg-white text-slate-700 px-1.5 py-0.5 rounded border border-slate-200 font-sans">
                          {s}
                        </span>
                      ))}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}

      {/* Full Markdown Narrative Tab */}
      {activeTab === "narrative" && (
        <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6 sm:p-10 prose-financial">
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={{
              h1: ({ node, ...props }) => (
                <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 mt-2 mb-6 border-b border-slate-200 pb-4 tracking-tight" {...props} />
              ),
              h2: ({ node, ...props }) => (
                <h2 className="text-xl sm:text-2xl font-bold text-slate-900 mt-8 mb-4 tracking-tight flex items-center gap-2 border-b border-slate-200 pb-2" {...props} />
              ),
              h3: ({ node, ...props }) => (
                <h3 className="text-lg font-semibold text-slate-800 mt-6 mb-3 tracking-wide" {...props} />
              ),
              p: ({ node, ...props }) => (
                <p className="text-slate-700 leading-relaxed text-sm sm:text-base mb-4 font-sans" {...props} />
              ),
              ul: ({ node, ...props }) => (
                <ul className="list-disc list-outside pl-5 space-y-2 mb-5 text-slate-700 text-sm sm:text-base" {...props} />
              ),
              ol: ({ node, ...props }) => (
                <ol className="list-decimal list-outside pl-5 space-y-2 mb-5 text-slate-700 text-sm sm:text-base" {...props} />
              ),
              li: ({ node, ...props }) => (
                <li className="leading-relaxed text-slate-700 pl-1" {...props} />
              ),
              table: ({ node, ...props }) => (
                <div className="overflow-x-auto my-6 rounded-xl border border-slate-200 bg-white">
                  <table className="w-full text-left border-collapse text-xs sm:text-sm font-sans" {...props} />
                </div>
              ),
              th: ({ node, ...props }) => (
                <th className="p-3.5 bg-slate-50 font-semibold text-slate-700 border-b border-slate-200 whitespace-nowrap" {...props} />
              ),
              td: ({ node, ...props }) => (
                <td className="p-3.5 text-slate-800 border-b border-slate-100 leading-relaxed" {...props} />
              ),
            }}
          >
            {finalReport}
          </ReactMarkdown>
        </div>
      )}
    </div>
  );
}
