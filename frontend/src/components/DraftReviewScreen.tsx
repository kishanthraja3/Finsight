"use client";

import React, { useState } from "react";
import { 
  Check, 
  PencilSimple, 
  X, 
  CheckCircle, 
  Sparkle, 
  FileText, 
  ListBullets, 
  ArrowRight, 
  ShieldCheck, 
  TrendUp 
} from "@phosphor-icons/react";
import { Finding, ReportState } from "@/lib/api";
import { extractReportVisuals, formatResearcherSources } from "@/lib/reportVisuals";
import { ExecutiveSummaryView } from "./ExecutiveSummaryView";

interface DraftReviewScreenProps {
  report: ReportState;
  onDecision: (
    findingId: string, 
    status: "approve" | "edit" | "reject" | "request_evidence", 
    editedText?: string, 
    reason?: string,
    note?: string
  ) => Promise<void>;
  onApproveAll?: () => Promise<void> | void;
  onProceedToFinal: () => void;
  isSubmittingDecision: boolean;
}

export function DraftReviewScreen({
  report,
  onDecision,
  onApproveAll,
  onProceedToFinal,
  isSubmittingDecision,
}: DraftReviewScreenProps) {
  // Only two toggle tabs as requested: "findings" and "executive_summary"
  const [activeTab, setActiveTab] = useState<"findings" | "executive_summary">("findings");
  
  // Local findings state for instantaneous UI updates
  const [localFindings, setLocalFindings] = useState<Finding[]>(report.findings || []);
  
  // Editing finding state
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editText, setEditText] = useState("");

  // Reject confirmation popup state (simple confirmation, no reasons/details asked)
  const [confirmRejectId, setConfirmRejectId] = useState<string | null>(null);

  // Sync if report findings change from external polling
  React.useEffect(() => {
    if (report.findings) {
      setLocalFindings(report.findings);
    }
  }, [report.findings]);

  const findings = localFindings;
  const approvedCount = findings.filter((f) => f.status === "approved" || f.status === "edited").length;
  const pendingCount = findings.filter((f) => f.status === "pending").length;
  const rejectedCount = findings.filter((f) => f.status === "rejected").length;

  // Only enable Generate Final Report after accepting/approving all findings
  const canGenerateReport = pendingCount === 0 && approvedCount > 0;

  // Dynamic visuals derived directly from current local findings
  const visuals = extractReportVisuals({
    ...report,
    findings: localFindings
  });

  const handleStartEdit = (f: Finding) => {
    setEditingId(f.id);
    setEditText(f.statement);
  };

  const handleSaveEdit = async (findingId: string) => {
    if (!editText.trim()) return;
    // Optimistic update
    setLocalFindings(prev => prev.map(f => f.id === findingId ? { ...f, statement: editText.trim(), status: "edited" } : f));
    setEditingId(null);
    await onDecision(findingId, "edit", editText.trim());
  };

  const handleApprove = async (findingId: string) => {
    // Optimistic update
    setLocalFindings(prev => prev.map(f => f.id === findingId ? { ...f, status: "approved" } : f));
    await onDecision(findingId, "approve");
  };

  // Rejection: prompt simple confirmation modal without asking for details
  const handleOpenRejectConfirm = (findingId: string) => {
    setConfirmRejectId(findingId);
  };

  const handleConfirmReject = async () => {
    if (!confirmRejectId) return;
    const targetId = confirmRejectId;
    setConfirmRejectId(null);

    // Optimistic update to rejected (simply excluded from report, no replanner loop)
    setLocalFindings(prev => prev.map(f => f.id === targetId ? { ...f, status: "rejected" } : f));
    await onDecision(targetId, "reject");
  };

  // Accept All: marks all findings as approved/accepted, does NOT lock or redirect to final report
  const handleAcceptAll = async () => {
    setLocalFindings(prev => prev.map(f => ({ ...f, status: "approved" })));
    if (onApproveAll) {
      await onApproveAll();
    }
  };


  const getConfidenceBadge = (confidence: string) => {
    switch (confidence?.toLowerCase()) {
      case "high":
        return <span className="px-2 py-0.5 rounded-full text-[10.5px] font-mono font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">HIGH CONFIDENCE</span>;
      case "medium":
        return <span className="px-2 py-0.5 rounded-full text-[10.5px] font-mono font-bold bg-amber-50 text-amber-700 border border-amber-200">MEDIUM CONFIDENCE</span>;
      default:
        return <span className="px-2 py-0.5 rounded-full text-[10.5px] font-mono font-bold bg-rose-50 text-rose-700 border border-rose-200">LOW CONFIDENCE</span>;
    }
  };

  const getCategoryBadge = (category: string) => {
    const map: Record<string, { label: string; color: string }> = {
      financial_performance: { label: "FINANCIAL METRIC", color: "text-sky-700 bg-sky-50 border-sky-200" },
      market_data: { label: "MARKET VALUATION", color: "text-blue-700 bg-blue-50 border-blue-200" },
      news: { label: "NEWS & SENTIMENT", color: "text-purple-700 bg-purple-50 border-purple-200" },
      risk: { label: "RISK EXPOSURE", color: "text-amber-700 bg-amber-50 border-amber-200" },
    };
    const c = map[category] || { label: category?.toUpperCase() || "METRIC", color: "text-slate-700 bg-slate-100 border-slate-200" };
    return <span className={`px-2 py-0.5 rounded-md text-[10.5px] font-mono font-bold border ${c.color}`}>{c.label}</span>;
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 sm:py-8 space-y-6">
      {/* Top Header matching user picture */}
      <div className="flex flex-col gap-4">
        {/* Breadcrumb & Action Buttons */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs">
          <div className="text-slate-600 font-medium">
            <span>Research Reports</span>
            <span className="mx-2 text-slate-600">›</span>
            <span className="text-slate-900 font-semibold">{visuals.companyName} {visuals.targetPeriod}</span>
          </div>

          {/* Top Right Action: Generate Final Report only (PDF/Markdown download available on final report screen) */}
          <div className="flex items-center">
            <button
              onClick={canGenerateReport ? onProceedToFinal : undefined}
              disabled={!canGenerateReport}
              title={!canGenerateReport ? "Please click 'Accept All' or approve all findings before generating final report" : "Generate Final Audited Report"}
              className={`inline-flex items-center gap-2 px-4 py-2 rounded-xl font-bold text-xs tracking-wide shadow-sm transition-all ${
                canGenerateReport
                  ? "bg-gradient-to-r from-sky-600 to-cyan-600 hover:from-sky-500 hover:to-cyan-500 text-white cursor-pointer hover:shadow active:scale-[0.98]"
                  : "bg-slate-200 text-slate-400 border border-slate-300/80 cursor-not-allowed shadow-none"
              }`}
            >
              <span>Generate Final Report</span>
              <ArrowRight size={14} weight="bold" />
            </button>
          </div>
        </div>

        {/* Title & Badges */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
          <div className="space-y-1">
            <div className="flex flex-wrap items-center gap-2.5">
              <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 tracking-tight font-sans">
                {visuals.reportTitle}
              </h1>

              {/* Reviewed badge */}
              <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-emerald-50 border border-emerald-200 text-emerald-700 text-xs font-semibold font-mono">
                <CheckCircle size={13} weight="fill" className="text-emerald-500" />
                <span>Reviewed ({approvedCount}/{findings.length} claims approved)</span>
              </span>

              {/* Critic QC Passed badge */}
              <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-sky-50 border border-sky-200 text-sky-700 text-xs font-semibold font-mono">
                <CheckCircle size={13} weight="fill" className="text-sky-500" />
                <span>Critic QC Passed</span>
              </span>
            </div>

            <p className="text-xs sm:text-sm text-slate-600 max-w-4xl leading-relaxed">
              {report.query}
            </p>
          </div>
        </div>

        {/* The Two Toggle Tabs */}
        <div className="flex items-center gap-2 border-b border-slate-200 pt-2">
          {/* Tab 1: Findings */}
          <button
            onClick={() => setActiveTab("findings")}
            className={`px-5 py-3 text-sm font-bold border-b-2 transition-all flex items-center gap-2 ${
              activeTab === "findings"
                ? "border-sky-600 text-sky-600 bg-sky-50/40 rounded-t-lg"
                : "border-transparent text-slate-600 hover:text-slate-900"
            }`}
          >
            <ListBullets size={18} weight={activeTab === "findings" ? "bold" : "regular"} />
            <span>Findings ({findings.length})</span>
          </button>

          {/* Tab 2: Executive Summary */}
          <button
            onClick={() => setActiveTab("executive_summary")}
            className={`px-5 py-3 text-sm font-bold border-b-2 transition-all flex items-center gap-2 ${
              activeTab === "executive_summary"
                ? "border-sky-600 text-sky-600 bg-sky-50/40 rounded-t-lg"
                : "border-transparent text-slate-600 hover:text-slate-900"
            }`}
          >
            <FileText size={18} weight={activeTab === "executive_summary" ? "bold" : "regular"} />
            <span>Executive Summary</span>
          </button>
        </div>
      </div>

      {/* Tab 1 Content: Findings */}
      {activeTab === "findings" && (
        <div className="space-y-4">
          {/* Top Findings Action Bar: Audit Summary + Accept All */}
          <div className="p-4 rounded-xl bg-white border border-slate-200 shadow-xs flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div className="flex items-center gap-3 text-xs font-mono">
              <span className="text-emerald-700 font-bold bg-emerald-50 px-2 py-1 rounded border border-emerald-200">
                {approvedCount} Approved
              </span>
              <span className="text-slate-300">•</span>
              <span className="text-amber-700 font-bold bg-amber-50 px-2 py-1 rounded border border-amber-200">
                {pendingCount} Pending
              </span>
              {rejectedCount > 0 && (
                <>
                  <span className="text-slate-300">•</span>
                  <span className="text-rose-700 font-bold bg-rose-50 px-2 py-1 rounded border border-rose-200">
                    {rejectedCount} Rejected
                  </span>
                </>
              )}
            </div>

            {/* Accept All Button: Changes status to accepted/approved without locking */}
            <div className="flex items-center gap-3">
              <button
                onClick={handleAcceptAll}
                disabled={isSubmittingDecision}
                className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-xs shadow-xs transition-all active:scale-[0.98]"
              >
                <Check size={14} weight="bold" />
                <span>Accept All ({findings.length})</span>
              </button>
              <span className="text-xs text-slate-600 hidden md:inline">
                Marks all claims as approved without locking report
              </span>
            </div>
          </div>

          {/* Discrete Claims List */}
          <div className="space-y-3.5">
            {findings.map((f, idx) => {
              const isEditing = editingId === f.id;
              const isApproved = f.status === "approved" || f.status === "edited";
              const isRejected = f.status === "rejected";
              const sources = formatResearcherSources(f.evidence_chunk_ids, f);

              return (
                <div
                  key={f.id}
                  className={`p-5 rounded-2xl border transition-all duration-150 ${
                    isRejected
                      ? "bg-slate-50/60 border-slate-200 opacity-60"
                      : isApproved
                      ? "bg-white border-emerald-200/80 shadow-xs"
                      : "bg-white border-slate-200/90 shadow-sm"
                  }`}
                >
                  {/* Card Header */}
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-3">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-mono text-xs text-slate-600 font-bold">#{idx + 1}</span>
                      {getCategoryBadge(f.category)}
                      {getConfidenceBadge(f.confidence)}

                      {/* Verified Badge */}
                      {f.numerically_verified ? (
                        <span className="px-2 py-0.5 rounded-full text-[10.5px] font-mono font-bold bg-emerald-50 text-emerald-700 border border-emerald-200 flex items-center gap-1">
                          <Check size={11} weight="bold" />
                          <span>FIGURE VERIFIED</span>
                        </span>
                      ) : null}

                      {/* Status indicator */}
                      {isApproved && (
                        <span className="text-[10px] font-mono uppercase px-2 py-0.5 rounded-full font-bold bg-emerald-100 text-emerald-800 border border-emerald-300">
                          {f.status === "edited" ? "Edited & Approved" : "Approved"}
                        </span>
                      )}
                      {isRejected && (
                        <span className="text-[10px] font-mono uppercase px-2 py-0.5 rounded-full font-bold bg-rose-100 text-rose-800 border border-rose-300">
                          Excluded from Report
                        </span>
                      )}
                    </div>

                    {/* Action buttons: Approve, Edit, Reject (NO request evidence button) */}
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => handleApprove(f.id)}
                        disabled={isSubmittingDecision}
                        className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-all ${
                          isApproved
                            ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                            : "bg-slate-100 hover:bg-emerald-50 text-slate-700 hover:text-emerald-700 border border-slate-200 hover:border-emerald-200"
                        }`}
                      >
                        <Check size={13} weight="bold" />
                        <span>Approve</span>
                      </button>

                      <button
                        onClick={() => handleStartEdit(f)}
                        disabled={isSubmittingDecision}
                        className="px-3 py-1.5 rounded-lg bg-slate-100 hover:bg-sky-50 text-slate-700 hover:text-sky-700 border border-slate-200 hover:border-sky-200 text-xs font-semibold flex items-center gap-1.5 transition-all"
                      >
                        <PencilSimple size={13} />
                        <span>Edit</span>
                      </button>

                      <button
                        onClick={() => handleOpenRejectConfirm(f.id)}
                        disabled={isSubmittingDecision}
                        className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-all ${
                          isRejected
                            ? "bg-rose-50 text-rose-700 border border-rose-200"
                            : "bg-slate-100 hover:bg-rose-50 text-slate-700 hover:text-rose-700 border border-slate-200 hover:border-rose-200"
                        }`}
                      >
                        <X size={13} weight="bold" />
                        <span>Reject</span>
                      </button>
                    </div>
                  </div>

                  {/* Body Text */}
                  {isEditing ? (
                    <div className="space-y-3 mt-2">
                      <textarea
                        value={editText}
                        onChange={(e) => setEditText(e.target.value)}
                        rows={3}
                        className="w-full p-3 rounded-xl bg-slate-50 border border-sky-400 text-slate-900 text-sm focus:outline-none font-sans"
                      />
                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => handleSaveEdit(f.id)}
                          className="px-4 py-1.5 rounded-lg bg-sky-600 text-white font-semibold text-xs hover:bg-sky-700 transition-colors"
                        >
                          Save Changes
                        </button>
                        <button
                          onClick={() => setEditingId(null)}
                          className="px-4 py-1.5 rounded-lg bg-slate-100 text-slate-700 text-xs hover:bg-slate-200 transition-colors"
                        >
                          Cancel
                        </button>
                      </div>
                    </div>
                  ) : (
                    <p className={`text-sm sm:text-base leading-relaxed ${isRejected ? "line-through text-slate-600" : "text-slate-800"}`}>
                      {f.statement}
                    </p>
                  )}

                  {/* Audited Figures */}
                  {f.numerically_verified && f.cited_figures && f.cited_figures.length > 0 && (
                    <div className="mt-3 flex items-center gap-2 text-xs">
                      <span className="font-mono text-emerald-700 font-semibold">Audited Figures:</span>
                      <div className="flex flex-wrap items-center gap-1.5">
                        {Array.from(new Set(f.cited_figures.map(fig => fig.replace(/\u202f|\xa0/g, " ").trim()))).map((fig, i) => (
                          <span key={i} className="px-1.5 py-0.5 rounded bg-emerald-50 text-emerald-700 font-mono text-[11px] font-bold border border-emerald-200/60">
                            {fig}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Clean Researcher Sources (No raw chunk tokens) */}
                  <div className="mt-3 pt-3 border-t border-slate-100 flex flex-wrap items-center gap-2">
                    <span className="text-[11px] font-semibold text-slate-600 uppercase font-mono">
                      Institutional Sources:
                    </span>
                    {sources.map((src, i) => (
                      <span
                        key={i}
                        className="px-2 py-0.5 rounded-md text-[11px] font-medium bg-slate-100 text-slate-700 border border-slate-200"
                      >
                        {src}
                      </span>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Tab 2 Content: Executive Summary (Card exactly like image with graphs, figures, matrix) */}
      {activeTab === "executive_summary" && (
        <ExecutiveSummaryView 
          visuals={visuals} 
          approvedCount={approvedCount} 
          totalFindings={findings.length} 
        />
      )}

      {/* Simple Reject Confirmation Modal (No details asked) */}
      {confirmRejectId && (
        <div className="fixed inset-0 z-50 bg-black/40 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-2xl border border-slate-200 space-y-4 animate-in fade-in zoom-in-95 duration-150">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-full bg-rose-50 border border-rose-200 flex items-center justify-center text-rose-600 shrink-0">
                <X size={20} weight="bold" />
              </div>
              <div>
                <h3 className="text-base font-bold text-slate-900">
                  Reject this finding?
                </h3>
                <p className="text-xs text-slate-600">
                  Are you sure you want to reject it? It will simply be excluded from the final report.
                </p>
              </div>
            </div>

            <div className="flex items-center justify-end gap-2.5 pt-2">
              <button
                onClick={() => setConfirmRejectId(null)}
                className="px-4 py-2 rounded-xl text-slate-600 hover:bg-slate-100 text-xs font-semibold transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleConfirmReject}
                className="px-4 py-2 rounded-xl bg-rose-600 hover:bg-rose-700 text-white text-xs font-bold shadow-xs transition-colors"
              >
                Yes, Reject Finding
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
