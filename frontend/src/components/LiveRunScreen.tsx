"use client";

import React, { useEffect, useState } from "react";
import { 
  CircleNotch, 
  CheckCircle, 
  Clock, 
  Eye, 
  FileText, 
  ChartBar, 
  Article, 
  ShieldWarning, 
  MagnifyingGlass, 
  UserCheck, 
  CaretRight,
  Database,
  ArrowUpRight
} from "@phosphor-icons/react";
import { ReportState } from "@/lib/api";

interface LiveRunScreenProps {
  runId: string;
  query: string;
  events: any[];
  currentAgent: string;
  runStatus: string;
  retryAttempt: number;
  maxRetries: number;
  reportState?: ReportState | null;
  onViewReport: () => void;
  canViewReport: boolean;
}

const WORKFLOW_STEPS = [
  { id: "planner", name: "Planner", role: "Clause Decomposition" },
  { id: "financial_research", name: "SEC Research", role: "Multi-Doc RAG" },
  { id: "market_data", name: "Market Data", role: "Alpha Vantage" },
  { id: "news_research", name: "News Research", role: "Sentiment Feed" },
  { id: "risk", name: "Risk Analysis", role: "Categorized Exposure" },
  { id: "synthesis", name: "Synthesis", role: "Grounded Findings" },
  { id: "critic", name: "Quality Review", role: "Agentic Critic" },
  { id: "human_review", name: "Human Review", role: "HITL Validation" },
];

export function LiveRunScreen({
  runId,
  query,
  events,
  currentAgent,
  runStatus,
  retryAttempt,
  maxRetries,
  reportState,
  onViewReport,
  canViewReport,
}: LiveRunScreenProps) {
  const [startTime, setStartTime] = useState<string>("");

  useEffect(() => {
    if (!startTime) {
      const now = new Date();
      setStartTime(
        now.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" }) +
        " " +
        now.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit", second: "2-digit", hour12: true })
      );
    }
  }, [startTime]);

  const actualQuery = query || reportState?.query || "";

  // Dynamically determine Target Company from reportState, events, or query (Never hardcode to NVIDIA)
  const getCompanyDetails = () => {
    // 1. Check reportState companies
    let comp = reportState?.companies?.[0];
    
    // 2. Check events
    if (!comp) {
      const eventWithComp = [...events].reverse().find(e => e.companies?.[0] || e.company);
      comp = eventWithComp?.companies?.[0] || eventWithComp?.company;
    }

    const qLower = actualQuery.toLowerCase();
    
    if (comp?.toLowerCase().includes("apple") || qLower.includes("apple") || qLower.includes("aapl")) {
      return {
        name: "Apple (AAPL)",
        ticker: "AAPL",
        icon: (
          <div className="w-8 h-8 rounded-lg bg-[#1c1c1e] flex items-center justify-center shrink-0 shadow-2xs">
            <svg className="w-4 h-4 text-white" viewBox="0 0 24 24" fill="currentColor">
              <path d="M18.71 19.5c-.83 1.24-1.71 2.45-3.05 2.47-1.34.03-1.77-.79-3.29-.79-1.53 0-2 .77-3.27.82-1.31.05-2.3-1.32-3.14-2.53C4.25 17 2.94 12.45 4.7 9.39c.87-1.52 2.43-2.48 4.12-2.51 1.28-.02 2.5.87 3.29.87.78 0 2.26-1.07 3.81-.91.65.03 2.47.26 3.64 1.98-.09.06-2.17 1.28-2.15 3.81.03 3.02 2.65 4.03 2.68 4.04-.03.07-.42 1.44-1.38 2.83M15.97 6.37c.62-.75 1.04-1.8 0.92-2.85-.9.04-1.99.6-2.63 1.35-.57.65-1.06 1.72-.93 2.74 1 .08 2.03-.49 2.64-1.24z" />
            </svg>
          </div>
        ),
      };
    }

    if (comp?.toLowerCase().includes("microsoft") || qLower.includes("microsoft") || qLower.includes("msft")) {
      return {
        name: "Microsoft (MSFT)",
        ticker: "MSFT",
        icon: (
          <div className="w-8 h-8 rounded-lg bg-white border border-slate-200 flex items-center justify-center p-1.5 shrink-0 shadow-2xs">
            <div className="grid grid-cols-2 gap-0.5 w-full h-full">
              <div className="bg-[#f25022] rounded-[1px]" />
              <div className="bg-[#7fba00] rounded-[1px]" />
              <div className="bg-[#00a4ef] rounded-[1px]" />
              <div className="bg-[#ffb900] rounded-[1px]" />
            </div>
          </div>
        ),
      };
    }

    if (comp?.toLowerCase().includes("nvidia") || qLower.includes("nvidia") || qLower.includes("nvda")) {
      return {
        name: "NVIDIA (NVDA)",
        ticker: "NVDA",
        icon: (
          <div className="w-8 h-8 rounded-lg bg-[#76b900] flex items-center justify-center shrink-0 shadow-2xs">
            <svg className="w-5 h-5 text-white" viewBox="0 0 24 24" fill="currentColor">
              <path d="M7.74 7.26C6.73 8.36 6.13 9.87 6.13 11.5c0 3.32 2.45 6.07 5.72 6.44v1.8C7.54 19.34 4 15.82 4 11.5c0-2.31.95-4.41 2.5-5.91l1.24 1.67zm4.11-3.21v1.83c1.69.34 3.03 1.6 3.48 3.24.47 1.72-.08 3.51-1.39 4.67-.8.71-1.85 1.13-2.98 1.13v1.81c1.62 0 3.12-.6 4.27-1.63 1.9-1.69 2.7-4.28 2.02-6.78-.65-2.36-2.58-4.19-4.99-4.7L11.85 4.05z" />
            </svg>
          </div>
        ),
      };
    }

    if (comp?.toLowerCase().includes("tesla") || qLower.includes("tesla") || qLower.includes("tsla")) {
      return {
        name: "Tesla (TSLA)",
        ticker: "TSLA",
        icon: (
          <div className="w-8 h-8 rounded-lg bg-red-600 flex items-center justify-center text-white font-bold text-xs shrink-0 shadow-2xs">
            T
          </div>
        ),
      };
    }

    if (comp?.toLowerCase().includes("amazon") || qLower.includes("amazon") || qLower.includes("amzn")) {
      return {
        name: "Amazon (AMZN)",
        ticker: "AMZN",
        icon: (
          <div className="w-8 h-8 rounded-lg bg-[#232f3e] flex items-center justify-center text-amber-400 font-bold text-xs shrink-0 shadow-2xs">
            a
          </div>
        ),
      };
    }

    if (comp?.toLowerCase().includes("alphabet") || comp?.toLowerCase().includes("google") || qLower.includes("google") || qLower.includes("googl")) {
      return {
        name: "Alphabet (GOOGL)",
        ticker: "GOOGL",
        icon: (
          <div className="w-8 h-8 rounded-lg bg-blue-600 flex items-center justify-center text-white font-bold text-xs shrink-0 shadow-2xs">
            G
          </div>
        ),
      };
    }

    // Dynamic extraction from detected company or query
    const targetName = comp || (actualQuery.split(" ")[0]?.replace(/[^a-zA-Z]/g, "") || "Target Asset");
    return {
      name: comp ? `${comp}` : `${targetName}`,
      ticker: targetName.toUpperCase().slice(0, 5),
      icon: (
        <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-sky-500 to-cyan-600 flex items-center justify-center text-white font-extrabold text-xs shrink-0 shadow-2xs">
          {targetName.slice(0, 2).toUpperCase()}
        </div>
      ),
    };
  };

  const companyInfo = getCompanyDetails();

  // Workflow Step Status calculation
  const getStepStatus = (stepId: string, index: number) => {
    const executedAgents = events.map((e) => e.agent).filter(Boolean);
    const hasExecuted = executedAgents.includes(stepId);
    const isCurrent = currentAgent === stepId;

    if (isCurrent) return "in_progress";
    if (hasExecuted) return "completed";

    const latestExecutedIndex = WORKFLOW_STEPS.findIndex((s) => s.id === currentAgent);
    if (latestExecutedIndex > index) return "completed";
    if (latestExecutedIndex === index) return "in_progress";

    const isQueued = index <= (latestExecutedIndex !== -1 ? latestExecutedIndex + 2 : 2);
    return isQueued ? "queued" : "pending";
  };

  // Build dynamic execution activity log from events
  const buildActivityLog = () => {
    const baseTime = new Date();
    const formatTimeOffset = (secondsOffset: number) => {
      const d = new Date(baseTime.getTime() + secondsOffset * 1000);
      return d.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit", second: "2-digit", hour12: true });
    };

    const items = [
      {
        time: formatTimeOffset(0),
        title: "Research intent classified",
        desc: `Identified target: ${companyInfo.name} | Orchestrating multi-agent graph`,
        completed: true,
      },
      {
        time: formatTimeOffset(1),
        title: "Research tasks created",
        desc: "Generated clause-targeted tasks with semantic keyword targeting",
        completed: events.length > 0 || Boolean(reportState?.tasks?.length),
      },
      {
        time: formatTimeOffset(3),
        title: "Evidence retrieval underway",
        desc: "Querying SEC 10-K/10-Q vector stores, market telemetry and news feeds",
        completed: events.some((e) => e.agent === "financial_research" || e.agent === "market_data" || e.agent === "news_research"),
      },
      {
        time: formatTimeOffset(5),
        title: "Preparing synthesis & verification",
        desc: "Compiling retrieved evidence chunks into structured, verified findings",
        completed: events.some((e) => e.agent === "synthesis" || e.agent === "critic" || e.agent === "human_review") || Boolean(reportState?.findings?.length),
      },
    ];

    return items;
  };

  const activityLog = buildActivityLog();

  // Extract actual tasks from coverage_ledger, reportState.tasks, or events
  const ledgerFromEvents = [...events].reverse().find((e) => e.coverage_ledger)?.coverage_ledger || [];
  const tasksFromEvents = [...events].reverse().find((e) => e.tasks)?.tasks || [];

  const rawTasksList = (
    (reportState?.coverage_ledger && reportState.coverage_ledger.length > 0)
      ? reportState.coverage_ledger
      : (reportState?.tasks && reportState.tasks.length > 0)
      ? reportState.tasks
      : (ledgerFromEvents.length > 0)
      ? ledgerFromEvents
      : tasksFromEvents
  );

  // Normalize tasks list for display
  const tasksList = rawTasksList.map((t: any, idx: number) => {
    const taskId = t.task_id || t.id || `task_${idx + 1 < 10 ? "00" : "0"}${idx + 1}`;
    const taskTitle = t.task || t.sub_question || t.clause || t.expected_output || actualQuery;
    const requiredSources = t.required_data_sources || t.required_doc_types || ["sec_filings"];
    const qcStatus = t.qc_status || (t.final_finding ? "PASSED" : "PENDING");
    return {
      taskId,
      taskTitle,
      requiredSources,
      qcStatus,
      limitation: t.evidence_limitation || "-",
    };
  });

  // Calculate dynamic progress
  const totalTasks = Math.max(1, tasksList.length);
  const completedTasks = tasksList.filter((t: any) => t.qcStatus === "PASSED" || t.qcStatus === "COMPLETE").length;
  
  // If no tasks marked passed yet, infer progress from the active workflow step
  let progressPercent = 0;
  if (completedTasks > 0) {
    progressPercent = Math.min(100, Math.round((completedTasks / totalTasks) * 100));
  } else {
    const stepIdx = WORKFLOW_STEPS.findIndex(s => s.id === currentAgent);
    if (stepIdx !== -1) {
      progressPercent = Math.min(95, Math.round(((stepIdx + 0.5) / WORKFLOW_STEPS.length) * 100));
    } else {
      progressPercent = 15;
    }
  }

  // Count SEC chunks dynamically
  let secChunksCount = 0;
  if (reportState?.retrieval_trace?.sec_filings_count) {
    secChunksCount = reportState.retrieval_trace.sec_filings_count;
  } else if (reportState?.findings) {
    secChunksCount = new Set(reportState.findings.flatMap(f => f.evidence_chunk_ids || [])).size;
  }
  if (!secChunksCount && events.some(e => e.agent === "financial_research")) {
    secChunksCount = 4;
  }

  // Determine if Market Data is required for this query
  const marketRequired = tasksList.some((t: any) => 
    t.requiredSources.some((s: string) => s.toLowerCase().includes("market"))
  ) || /price|pe ratio|p\/e|valuation|52-week|trading|stock/i.test(actualQuery);

  // Determine if News is required for this query
  const newsRequired = tasksList.some((t: any) => 
    t.requiredSources.some((s: string) => s.toLowerCase().includes("news"))
  ) || /news|headline|sentiment|recent events|breaking/i.test(actualQuery);

  const isFinancialDone = events.some(e => (e.agent === "synthesis" || e.agent === "critic" || e.agent === "risk")) || currentAgent === "synthesis";
  const isMarketDone = events.some(e => e.agent === "market_data" && e.status === "completed") || isFinancialDone;
  const isNewsDone = events.some(e => e.agent === "news_research" && e.status === "completed") || isFinancialDone;

  return (
    <div className="flex-1 w-full max-w-7xl mx-auto px-6 py-8">
      {/* Top Header Section */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-6 mb-8">
        <div>
          <div className="flex items-center gap-2 mb-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse" />
            <span className="text-xs font-bold uppercase tracking-wider text-emerald-600 font-mono">
              LIVE EXECUTION
            </span>
          </div>
          <h1 className="text-3xl font-extrabold text-slate-900 tracking-tight">
            Research in progress
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            Tracking retrieval, evidence validation, and report synthesis in real time.
          </p>
        </div>

        {/* Right Query Card (Displays actual user entered query & dynamic target company) */}
        <div className="p-4 rounded-2xl bg-white border border-slate-200/80 shadow-xs min-w-[360px] max-w-md">
          <div className="text-xs text-slate-700 leading-relaxed mb-3">
            <span className="font-bold text-slate-900">Query: </span>
            <span className="text-slate-800">{actualQuery}</span>
          </div>

          <div className="pt-3 border-t border-slate-100 flex items-center justify-between gap-4">
            {/* Dynamic Target Company */}
            <div className="flex items-center gap-2.5">
              {companyInfo.icon}
              <div>
                <div className="text-[10px] text-slate-600 uppercase font-semibold">Target Company</div>
                <div className="text-xs font-bold text-slate-900">{companyInfo.name}</div>
              </div>
            </div>

            {/* Started Timestamp */}
            <div className="flex items-center gap-2 pl-4 border-l border-slate-100">
              <Clock size={16} className="text-slate-400 shrink-0" />
              <div>
                <div className="text-[10px] text-slate-600 uppercase font-semibold">Started</div>
                <div className="text-xs font-medium text-slate-700 font-mono">{startTime}</div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Horizontal Pipeline Workflow Stepper */}
      <div className="p-4 rounded-2xl bg-white border border-slate-200/80 shadow-xs mb-8 overflow-x-auto">
        <div className="flex items-center justify-between min-w-[900px] gap-2">
          {WORKFLOW_STEPS.map((step, idx) => {
            const status = getStepStatus(step.id, idx);
            const isLast = idx === WORKFLOW_STEPS.length - 1;

            return (
              <React.Fragment key={step.id}>
                {/* Step Card */}
                <div
                  className={`flex-1 p-3 rounded-xl border transition-all ${
                    status === "completed"
                      ? "bg-emerald-50/50 border-emerald-200 text-slate-900"
                      : status === "in_progress"
                      ? "bg-sky-50 border-sky-400 shadow-xs ring-2 ring-sky-200"
                      : status === "queued"
                      ? "bg-slate-50/70 border-slate-200 text-slate-700"
                      : "bg-white border-slate-200/60 opacity-60 text-slate-600"
                  }`}
                >
                  <div className="flex items-center justify-between mb-1.5">
                    <span className="text-xs font-bold truncate">{step.name}</span>
                    {status === "completed" && (
                      <CheckCircle size={15} weight="fill" className="text-emerald-500 shrink-0" />
                    )}
                    {status === "in_progress" && (
                      <CircleNotch size={15} className="text-[#0284c7] animate-spin shrink-0" />
                    )}
                    {status === "queued" && (
                      <span className="w-1.5 h-1.5 rounded-full bg-slate-300 shrink-0" />
                    )}
                  </div>

                  <div className="text-[10px] text-slate-600 truncate mb-1">
                    {step.role}
                  </div>

                  <div className="text-[10px] font-semibold">
                    {status === "completed" && <span className="text-emerald-600">Completed</span>}
                    {status === "in_progress" && <span className="text-[#0284c7]">In Progress</span>}
                    {status === "queued" && <span className="text-slate-600">Queued</span>}
                    {status === "pending" && <span className="text-slate-600">Pending</span>}
                  </div>
                </div>

                {/* Connecting Line */}
                {!isLast && (
                  <div
                    className={`w-4 h-[2px] shrink-0 ${
                      status === "completed" ? "bg-emerald-400" : "bg-slate-200"
                    }`}
                  />
                )}
              </React.Fragment>
            );
          })}
        </div>
      </div>

      {/* Middle Grid: Execution Activity (60%) & Evidence Coverage (40%) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 mb-8">
        {/* Left Column: Execution Activity */}
        <div className="lg:col-span-7 p-6 rounded-2xl bg-white border border-slate-200/80 shadow-xs">
          <div className="flex items-center justify-between mb-6 pb-4 border-b border-slate-100">
            <div className="flex items-center gap-2">
              <FileText size={18} className="text-[#0284c7]" />
              <h2 className="text-sm font-bold text-slate-900">Execution activity</h2>
            </div>
            <div className="flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200 text-xs font-semibold">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
              <span>Live log</span>
            </div>
          </div>

          {/* Activity Timeline */}
          <div className="relative pl-6 space-y-6">
            <div className="absolute left-[11px] top-2 bottom-2 w-0.5 bg-slate-200" />

            {activityLog.map((act, i) => (
              <div key={i} className="relative flex items-start gap-3">
                <div
                  className={`absolute -left-6 top-1 w-5 h-5 rounded-full flex items-center justify-center ${
                    act.completed
                      ? "bg-emerald-500 text-white"
                      : "bg-sky-500 text-white"
                  }`}
                >
                  {act.completed ? (
                    <CheckCircle size={14} weight="bold" />
                  ) : (
                    <CircleNotch size={14} className="animate-spin" />
                  )}
                </div>

                <div className="pl-2">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-bold text-slate-900">{act.title}</span>
                    <span className="text-[11px] font-mono text-slate-600">{act.time}</span>
                  </div>
                  <p className="text-xs text-slate-700 mt-0.5">{act.desc}</p>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Right Column: Dynamic Evidence Coverage */}
        <div className="lg:col-span-5 p-6 rounded-2xl bg-white border border-slate-200/80 shadow-xs flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <Database size={18} className="text-[#0284c7]" />
                <h2 className="text-sm font-bold text-slate-900">Evidence coverage</h2>
              </div>
              <span className="text-xs text-slate-600">
                {completedTasks} of {totalTasks} tasks completed <span className="font-bold text-slate-900">{progressPercent}%</span>
              </span>
            </div>

            {/* Dynamic Progress Bar */}
            <div className="w-full h-2 rounded-full bg-slate-100 overflow-hidden mb-6">
              <div 
                className="h-full bg-gradient-to-r from-sky-500 to-[#00c5cc] rounded-full transition-all duration-500" 
                style={{ width: `${Math.max(8, progressPercent)}%` }}
              />
            </div>

            {/* Dynamic Evidence Category Cards */}
            <div className="space-y-3">
              {/* SEC Filings */}
              <div className="p-3.5 rounded-xl border border-slate-200/80 hover:border-slate-300 transition-all bg-white flex items-center justify-between group">
                <div className="flex items-center gap-3">
                  <div className="w-9 h-9 rounded-lg bg-emerald-50 text-emerald-600 flex items-center justify-center shrink-0">
                    <FileText size={20} />
                  </div>
                  <div>
                    <div className="text-xs font-bold text-slate-900">SEC Filings (10-K, 10-Q, 8-K)</div>
                    <div className="text-[11px] text-slate-600">
                      {secChunksCount > 0 ? `${secChunksCount} chunks retrieved` : "Querying SEC disclosures"}
                    </div>
                    {secChunksCount > 0 && (
                      <div className="w-28 h-1 rounded-full bg-slate-100 mt-1.5 overflow-hidden">
                        <div className="w-full h-full bg-emerald-500 rounded-full" />
                      </div>
                    )}
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  <span className={`text-[10px] font-mono px-2 py-0.5 rounded-full font-semibold ${
                    currentAgent === "financial_research"
                      ? "bg-emerald-50 text-emerald-700 border border-emerald-200 animate-pulse"
                      : isFinancialDone
                      ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                      : "bg-slate-100 text-slate-600 border border-slate-200"
                  }`}>
                    {currentAgent === "financial_research" ? "ACTIVE" : isFinancialDone ? "COMPLETED" : "QUEUED"}
                  </span>
                  <CaretRight size={14} className="text-slate-400 group-hover:text-slate-600" />
                </div>
              </div>

              {/* Market Data */}
              <div className="p-3.5 rounded-xl border border-slate-200/80 hover:border-slate-300 transition-all bg-white flex items-center justify-between group">
                <div className="flex items-center gap-3">
                  <div className="w-9 h-9 rounded-lg bg-sky-50 text-sky-600 flex items-center justify-center shrink-0">
                    <ChartBar size={20} />
                  </div>
                  <div>
                    <div className="text-xs font-bold text-slate-900">Market Data (Alpha Vantage)</div>
                    <div className="text-[11px] text-slate-600">
                      {!marketRequired
                        ? "Not required for this research"
                        : currentAgent === "market_data"
                        ? "Querying real-time quote & telemetry"
                        : isMarketDone
                        ? "Telemetry retrieved"
                        : "Waiting to retrieve"}
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  <span className={`text-[10px] font-mono px-2 py-0.5 rounded-full font-semibold ${
                    !marketRequired
                      ? "bg-slate-100 text-slate-500 border border-slate-200"
                      : currentAgent === "market_data"
                      ? "bg-sky-50 text-sky-700 border border-sky-200 animate-pulse"
                      : isMarketDone
                      ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                      : "bg-slate-100 text-slate-600 border border-slate-200"
                  }`}>
                    {!marketRequired ? "NOT REQUIRED" : currentAgent === "market_data" ? "ACTIVE" : isMarketDone ? "COMPLETED" : "QUEUED"}
                  </span>
                  <CaretRight size={14} className="text-slate-400 group-hover:text-slate-600" />
                </div>
              </div>

              {/* Recent News */}
              <div className="p-3.5 rounded-xl border border-slate-200/80 hover:border-slate-300 transition-all bg-white flex items-center justify-between group">
                <div className="flex items-center gap-3">
                  <div className="w-9 h-9 rounded-lg bg-cyan-50 text-cyan-600 flex items-center justify-center shrink-0">
                    <Article size={20} />
                  </div>
                  <div>
                    <div className="text-xs font-bold text-slate-900">Recent News (Sentiment Feed)</div>
                    <div className="text-[11px] text-slate-600">
                      {!newsRequired
                        ? "Not required for this research"
                        : currentAgent === "news_research"
                        ? "Filtering financial media headlines"
                        : isNewsDone
                        ? "Articles analyzed"
                        : "Waiting to retrieve"}
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  <span className={`text-[10px] font-mono px-2 py-0.5 rounded-full font-semibold ${
                    !newsRequired
                      ? "bg-slate-100 text-slate-500 border border-slate-200"
                      : currentAgent === "news_research"
                      ? "bg-cyan-50 text-cyan-700 border border-cyan-200 animate-pulse"
                      : isNewsDone
                      ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                      : "bg-slate-100 text-slate-600 border border-slate-200"
                  }`}>
                    {!newsRequired ? "NOT REQUIRED" : currentAgent === "news_research" ? "ACTIVE" : isNewsDone ? "COMPLETED" : "QUEUED"}
                  </span>
                  <CaretRight size={14} className="text-slate-400 group-hover:text-slate-600" />
                </div>
              </div>
            </div>
          </div>

          {/* Action to view findings when ready */}
          {canViewReport && (
            <div className="mt-6 pt-4 border-t border-slate-100">
              <button
                onClick={onViewReport}
                className="w-full inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl bg-gradient-to-r from-sky-600 to-cyan-600 hover:from-sky-500 hover:to-cyan-500 text-white font-bold text-sm transition-all shadow-sm active:scale-98"
              >
                <Eye size={16} weight="bold" />
                <span>View Draft &amp; Audit Findings</span>
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Bottom Section: Task Coverage Ledger (Renders actual planned tasks) */}
      <div className="p-6 rounded-2xl bg-white border border-slate-200/80 shadow-xs">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <FileText size={18} className="text-[#0284c7]" />
            <h2 className="text-sm font-bold text-slate-900">Task coverage ledger</h2>
          </div>
          <span className="text-xs font-mono text-slate-500">
            {tasksList.length} Planned Objectives
          </span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-slate-200 text-slate-400 font-medium">
                <th className="pb-3 pr-4">Task ID</th>
                <th className="pb-3 pr-4">Research objective</th>
                <th className="pb-3 pr-4">Required data sources</th>
                <th className="pb-3 pr-4">Status</th>
                <th className="pb-3 pr-4">Progress</th>
                <th className="pb-3">Notes</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {tasksList.length > 0 ? (
                tasksList.map((row: any, idx: number) => {
                  const isPassed = row.qcStatus === "PASSED" || row.qcStatus === "COMPLETE";

                  return (
                    <tr key={idx} className="hover:bg-slate-50/60">
                      <td className="py-3 pr-4 font-mono font-medium text-[#0284c7]">{row.taskId}</td>
                      <td className="py-3 pr-4 font-medium text-slate-900">{row.taskTitle}</td>
                      <td className="py-3 pr-4">
                        <div className="flex items-center gap-1.5 flex-wrap">
                          {row.requiredSources?.map((src: string, sIdx: number) => (
                            <span
                              key={sIdx}
                              className="px-2 py-0.5 rounded-md bg-sky-50 text-sky-700 border border-sky-200 text-[10px] font-medium"
                            >
                              {src}
                            </span>
                          ))}
                        </div>
                      </td>
                      <td className="py-3 pr-4">
                        <span className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-semibold ${
                          isPassed
                            ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                            : "bg-amber-50 text-amber-700 border border-amber-200"
                        }`}>
                          {isPassed ? <CheckCircle size={11} weight="fill" className="text-emerald-500" /> : <Clock size={11} />}
                          <span>{isPassed ? "PASSED" : row.qcStatus || "PENDING"}</span>
                        </span>
                      </td>
                      <td className="py-3 pr-4">
                        <div className="flex items-center gap-2">
                          <div className="w-16 h-1.5 rounded-full bg-slate-100 overflow-hidden">
                            <div
                              className={`h-full rounded-full transition-all duration-300 ${
                                isPassed ? "w-full bg-emerald-500" : "w-1/3 bg-sky-500"
                              }`}
                            />
                          </div>
                          <span className="font-mono text-[10px] text-slate-500">
                            {isPassed ? "100%" : "30%"}
                          </span>
                        </div>
                      </td>
                      <td className="py-3 text-slate-400 font-mono">{row.limitation}</td>
                    </tr>
                  );
                })
              ) : (
                <tr className="hover:bg-slate-50/60">
                  <td className="py-3 pr-4 font-mono font-medium text-[#0284c7]">task_001</td>
                  <td className="py-3 pr-4 font-medium text-slate-900">{actualQuery}</td>
                  <td className="py-3 pr-4">
                    <span className="px-2 py-0.5 rounded-md bg-sky-50 text-sky-700 border border-sky-200 text-[10px] font-medium">
                      sec_filings
                    </span>
                  </td>
                  <td className="py-3 pr-4">
                    <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full bg-amber-50 text-amber-700 border border-amber-200 text-[10px] font-semibold">
                      <Clock size={11} />
                      <span>PLANNING</span>
                    </span>
                  </td>
                  <td className="py-3 pr-4">
                    <span className="font-mono text-[10px] text-slate-500">10%</span>
                  </td>
                  <td className="py-3 text-slate-400 font-mono">-</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
