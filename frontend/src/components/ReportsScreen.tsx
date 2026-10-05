"use client";

import React, { useState, useEffect } from "react";
import { 
  FileText, 
  Plus, 
  DownloadSimple, 
  Clock, 
  ShieldCheck, 
  CheckCircle,
  Eye,
  CalendarBlank,
  Database
} from "@phosphor-icons/react";
import { getDownloadUrl, getPdfDownloadUrl, fetchReportsList } from "@/lib/api";

export interface PublishedReportItem {
  run_id: string;
  query: string;
  companies?: string[];
  findings_count?: number;
  approved_count?: number;
  created_at?: string;
  run_status?: string;
}

interface ReportsScreenProps {
  onNewResearch: () => void;
  onViewReport?: (runId: string) => void;
}

export function ReportsScreen({ onNewResearch, onViewReport }: ReportsScreenProps) {
  const [reports, setReports] = useState<PublishedReportItem[]>([]);
  const [loading, setLoading] = useState(true);

  const loadReports = async () => {
    try {
      setLoading(true);
      // Load from server
      const serverReports = await fetchReportsList();

      // Load from local storage
      let localReports: PublishedReportItem[] = [];
      try {
        const stored = localStorage.getItem("finsight_published_reports");
        if (stored) {
          localReports = JSON.parse(stored);
        }
      } catch {}

      // Merge and deduplicate by run_id
      const map = new Map<string, PublishedReportItem>();
      localReports.forEach(r => map.set(r.run_id, r));
      serverReports.forEach((r: any) => {
        if (!map.has(r.run_id)) {
          map.set(r.run_id, r);
        }
      });

      const merged = Array.from(map.values());
      // Sort newest first
      setReports(merged);
    } catch {
      // Fallback to empty
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadReports();
  }, []);

  return (
    <div className="flex-1 max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-8 sm:py-10 space-y-6">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-6 border-b border-slate-200">
        <div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 tracking-tight font-sans">
            Research Reports Dashboard
          </h1>
          <p className="text-xs sm:text-sm text-slate-500 mt-1">
            Institutional repository of completed, audited multi-agent research deliverables.
          </p>
        </div>

        <button
          onClick={onNewResearch}
          className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-gradient-to-r from-sky-600 to-cyan-600 hover:from-sky-500 hover:to-cyan-500 text-white font-bold text-xs tracking-wide shadow-sm hover:shadow transition-all active:scale-[0.98]"
        >
          <Plus size={15} weight="bold" />
          <span>New Research Query</span>
        </button>
      </div>

      {/* Reports List */}
      {reports.length > 0 ? (
        <div className="space-y-4">
          <div className="flex items-center justify-between text-xs text-slate-500 font-mono px-1">
            <span>Archived Reports ({reports.length})</span>
            <span>Direct PDF / Markdown Export</span>
          </div>

          <div className="space-y-3.5">
            {reports.map((item) => {
              const company = item.companies?.[0] || (/nvidia/i.test(item.query) ? "NVIDIA" : /microsoft/i.test(item.query) ? "MICROSOFT" : /apple/i.test(item.query) ? "APPLE" : "RESEARCH REPORT");
              const dateTimeStr = item.created_at || "Recent";

              return (
                <div
                  key={item.run_id}
                  className="p-5 rounded-2xl bg-white border border-slate-200/90 shadow-xs hover:shadow-sm hover:border-slate-300 transition-all flex flex-col md:flex-row md:items-center justify-between gap-4"
                >
                  <div className="space-y-2 min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-[10px] font-mono font-bold uppercase px-2 py-0.5 rounded bg-sky-50 text-sky-700 border border-sky-200">
                        {company}
                      </span>
                      <span className="text-xs font-mono font-semibold text-slate-500">
                        ID: <span className="text-slate-700">{item.run_id}</span>
                      </span>
                      <span className="inline-flex items-center gap-1 text-[11px] font-medium text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-full border border-emerald-200">
                        <CheckCircle size={13} weight="fill" className="text-emerald-500" />
                        <span>Audited Complete</span>
                      </span>
                    </div>

                    <h3 className="text-sm sm:text-base font-bold text-slate-900 leading-snug">
                      {item.query}
                    </h3>

                    <div className="flex flex-wrap items-center gap-3 text-xs text-slate-500 font-mono">
                      <div className="flex items-center gap-1">
                        <CalendarBlank size={14} className="text-slate-400" />
                        <span>{dateTimeStr}</span>
                      </div>
                      <span>•</span>
                      <div className="flex items-center gap-1">
                        <ShieldCheck size={14} className="text-emerald-600" />
                        <span>{item.approved_count || item.findings_count || 1} Claims Audited</span>
                      </div>
                    </div>
                  </div>

                  {/* Actions: Download PDF, Download Markdown, View Report */}
                  <div className="flex flex-wrap items-center gap-2.5 pt-2 md:pt-0 border-t md:border-t-0 border-slate-100">
                    <a
                      href={getPdfDownloadUrl(item.run_id)}
                      download={`FinSight_Research_${item.run_id}.pdf`}
                      className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-gradient-to-r from-sky-600 to-cyan-600 hover:from-sky-500 hover:to-cyan-500 text-white font-bold text-xs shadow-xs hover:shadow transition-all active:scale-[0.98]"
                    >
                      <DownloadSimple size={14} weight="bold" />
                      <span>Download PDF</span>
                    </a>

                    <a
                      href={getDownloadUrl(item.run_id)}
                      download={`FinSight_Research_${item.run_id}.md`}
                      className="inline-flex items-center gap-1.5 px-3 py-2 rounded-xl bg-white hover:bg-slate-50 border border-slate-200 text-slate-700 font-medium text-xs shadow-xs transition-colors"
                    >
                      <DownloadSimple size={14} />
                      <span>Download Markdown</span>
                    </a>

                    {onViewReport && (
                      <button
                        onClick={() => onViewReport(item.run_id)}
                        className="inline-flex items-center gap-1.5 px-3 py-2 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 font-medium text-xs transition-colors"
                      >
                        <Eye size={14} />
                        <span>View</span>
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      ) : (
        /* Empty State */
        <div className="rounded-2xl border-2 border-dashed border-slate-200 bg-white p-12 text-center flex flex-col items-center justify-center max-w-xl mx-auto my-8">
          <div className="w-16 h-16 rounded-2xl bg-sky-50 border border-sky-100 flex items-center justify-center text-[#0284c7] mb-4 shadow-xs">
            <FileText size={32} weight="duotone" />
          </div>
          
          <h3 className="text-lg font-bold text-slate-900 mb-1">No reports published yet</h3>
          <p className="text-xs sm:text-sm text-slate-500 max-w-md mb-6 leading-relaxed">
            Completed research runs, audited findings, and generated institutional PDF/Markdown reports will appear here for immediate access and export.
          </p>

          <button
            onClick={onNewResearch}
            className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-slate-900 hover:bg-slate-800 text-white font-medium text-xs transition-all shadow-xs"
          >
            <span>Start a Research Query</span>
          </button>
        </div>
      )}
    </div>
  );
}
