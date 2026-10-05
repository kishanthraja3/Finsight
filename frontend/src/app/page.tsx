"use client";

import React, { useState, useEffect, useRef } from "react";
import { Navbar } from "@/components/Navbar";
import { Sidebar, SidebarTab } from "@/components/Sidebar";
import { QueryScreen } from "@/components/QueryScreen";
import { LiveRunScreen } from "@/components/LiveRunScreen";
import { DraftReviewScreen } from "@/components/DraftReviewScreen";
import { FinalReportScreen } from "@/components/FinalReportScreen";
import { ReportsScreen } from "@/components/ReportsScreen";
import { SettingsScreen } from "@/components/SettingsScreen";
import { 
  createRun, 
  getReportState, 
  submitFindingDecision, 
  approveAllFindings,
  getFinalReport, 
  getStreamUrl, 
  ReportState 
} from "@/lib/api";

type Screen = "query" | "live" | "review" | "final";

export default function FinSightApp() {
  const [activeTab, setActiveTab] = useState<SidebarTab>("new_research");
  const [activeScreen, setActiveScreen] = useState<Screen>("query");
  const [runId, setRunId] = useState<string>("");
  const [query, setQuery] = useState<string>("");
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [events, setEvents] = useState<any[]>([]);
  const [currentAgent, setCurrentAgent] = useState<string>("");
  const [runStatus, setRunStatus] = useState<string>("planning");
  const [retryAttempt, setRetryAttempt] = useState<number>(1);
  const [maxRetries, setMaxRetries] = useState<number>(3);
  const [reportState, setReportState] = useState<ReportState | null>(null);
  const [finalReportText, setFinalReportText] = useState<string>("");
  const [isSubmittingDecision, setIsSubmittingDecision] = useState<boolean>(false);
  const [activeModel, setActiveModel] = useState<string>("GPT-OSS 120B");
  const [isFallback, setIsFallback] = useState<boolean>(false);

  const eventSourceRef = useRef<EventSource | null>(null);

  // Poll report periodically when in review or live
  useEffect(() => {
    let interval: any;
    if (runId && (activeScreen === "live" || activeScreen === "review")) {
      const fetchState = async () => {
        try {
          const st = await getReportState(runId);
          setReportState(st);
          setRunStatus(st.run_status);
          if (st.query) {
            setQuery((prev) => prev || st.query);
          }
          if (st.active_model) {
            setActiveModel(st.active_model);
          }
          if (st.fallback_active !== undefined) {
            setIsFallback(st.fallback_active);
          }
          if (st.retry_count !== undefined) {
            setRetryAttempt(st.retry_count + 1);
          }
          if (st.max_retries !== undefined) {
            setMaxRetries(st.max_retries);
          }
          // If awaiting human review and user is on live screen, transition smoothly
          if (st.run_status === "awaiting_human" && activeScreen === "live") {
            setActiveScreen("review");
          }
        } catch (e) {
          // ignore transient poll error
        }
      };
      fetchState();
      interval = setInterval(fetchState, 2000);
    }
    return () => clearInterval(interval);
  }, [runId, activeScreen]);

  // Connect SSE Stream
  const connectSSE = (id: string) => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }

    const streamUrl = getStreamUrl(id);
    const es = new EventSource(streamUrl);
    eventSourceRef.current = es;

    es.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data);
        setEvents((prev) => [...prev, data]);

        if (data.agent) {
          setCurrentAgent(data.agent);
        }
        if (data.status) {
          setRunStatus(data.status);
        }
        if (data.attempt) {
          setRetryAttempt(data.attempt);
        }
        if (data.active_model) {
          setActiveModel(data.active_model);
        }
        if (data.fallback_active !== undefined) {
          setIsFallback(data.fallback_active);
        }
        if (data.run_status) {
          setRunStatus(data.run_status);
          if (data.run_status === "awaiting_human") {
            setActiveScreen("review");
          } else if (data.run_status === "complete") {
            if (data.final_report) {
              setFinalReportText(data.final_report);
            }
          }
        }
      } catch (err) {
        // Ping or non-json message
      }
    };

    es.onerror = () => {
      // EventSource reconnects automatically
    };
  };

  const handleStartResearch = async (searchQuery: string) => {
    try {
      setIsLoading(true);
      setQuery(searchQuery);
      setEvents([]);
      setCurrentAgent("planner");
      setRunStatus("planning");

      const res = await createRun(searchQuery);
      setRunId(res.run_id);
      connectSSE(res.run_id);
      setActiveScreen("live");
      setActiveTab("new_research");
    } catch (e: any) {
      alert(`Error starting research: ${e.message}`);
    } finally {
      setIsLoading(false);
    }
  };

  const handleDecision = async (
    findingId: string,
    status: "approve" | "edit" | "reject" | "request_evidence",
    editedText?: string,
    reason?: string,
    note?: string
  ) => {
    if (!runId) return;
    try {
      setIsSubmittingDecision(true);
      await submitFindingDecision(runId, findingId, {
        status,
        edited_text: editedText,
        reason,
        note,
      });

      // Refresh report state
      const updated = await getReportState(runId);
      setReportState(updated);
      setRunStatus(updated.run_status);

      // Only if explicit re-retrieval requested switch to live view
      if (status === "request_evidence") {
        setActiveScreen("live");
      }
    } catch (e: any) {
      alert(`Error recording decision: ${e.message}`);
    } finally {
      setIsSubmittingDecision(false);
    }
  };

  const handleApproveAll = async () => {
    if (!runId) return;
    try {
      setIsSubmittingDecision(true);
      await approveAllFindings(runId);
      const updated = await getReportState(runId);
      setReportState(updated);
      setRunStatus(updated.run_status);
    } catch (e: any) {
      alert(`Error approving all findings: ${e.message}`);
    } finally {
      setIsSubmittingDecision(false);
    }
  };

  const handleProceedToFinal = async () => {
    if (!runId) return;
    try {
      const res = await getFinalReport(runId);
      setFinalReportText(res.final_report);

      // Save to localStorage for instant dashboard rendering
      try {
        const existing = JSON.parse(localStorage.getItem("finsight_published_reports") || "[]");
        const newEntry = {
          run_id: runId,
          query: query || reportState?.query || "Institutional Research",
          companies: reportState?.companies || [],
          findings_count: reportState?.findings?.length || 0,
          approved_count: reportState?.findings?.filter((f: any) => f.status === "approved" || f.status === "edited").length || 0,
          created_at: new Date().toLocaleString(),
          run_status: "complete",
        };
        const filtered = existing.filter((item: any) => item.run_id !== runId);
        localStorage.setItem("finsight_published_reports", JSON.stringify([newEntry, ...filtered]));
      } catch {}

      // Transition directly to the actual final deliverable report screen
      setActiveScreen("final");
    } catch (e: any) {
      alert(`Error generating final report: ${e.message}`);
    }
  };

  const handleViewReportFromDashboard = async (targetRunId: string) => {
    try {
      const res = await getFinalReport(targetRunId);
      setRunId(targetRunId);
      setFinalReportText(res.final_report);
      setActiveTab("new_research");
      setActiveScreen("final");
    } catch (e: any) {
      alert(`Error opening report: ${e.message}`);
    }
  };

  const handleNewResearch = () => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }
    setRunId("");
    setQuery("");
    setEvents([]);
    setReportState(null);
    setFinalReportText("");
    setActiveScreen("query");
    setActiveTab("new_research");
  };

  const handleSelectTab = (tab: SidebarTab) => {
    setActiveTab(tab);
    if (tab === "new_research" && !runId) {
      setActiveScreen("query");
    }
  };

  const isRunning = isLoading || runStatus === "planning" || runStatus === "retrieving" || runStatus === "synthesizing";

  return (
    <div className="flex flex-col min-h-screen bg-slate-50 ambient-bg">
      {/* Top Header Navbar */}
      <Navbar
        activeScreen={activeScreen}
        onNavigateHome={handleNewResearch}
        runStatus={runStatus}
        runId={runId}
        activeModel={activeModel}
        isFallback={isFallback}
      />

      {/* Main Body with Sidebar + Workspace */}
      <div className="flex flex-1">
        {/* Left Sidebar */}
        <Sidebar 
          activeTab={activeTab} 
          onSelectTab={handleSelectTab} 
          isRunning={isRunning}
        />

        {/* Content Area */}
        <main className="flex-1 flex flex-col overflow-y-auto">
          {activeTab === "new_research" && (
            <>
              {activeScreen === "query" && (
                <QueryScreen onSubmit={handleStartResearch} isLoading={isLoading} />
              )}

              {activeScreen === "live" && (
                <LiveRunScreen
                  runId={runId}
                  query={query || reportState?.query || ""}
                  events={events}
                  currentAgent={currentAgent}
                  runStatus={runStatus}
                  retryAttempt={retryAttempt}
                  maxRetries={maxRetries}
                  reportState={reportState}
                  onViewReport={() => setActiveScreen("review")}
                  canViewReport={Boolean(reportState && reportState.findings && reportState.findings.length > 0)}
                />
              )}

              {activeScreen === "review" && reportState && (
                <DraftReviewScreen
                  report={reportState}
                  onDecision={handleDecision}
                  onApproveAll={handleApproveAll}
                  onProceedToFinal={handleProceedToFinal}
                  isSubmittingDecision={isSubmittingDecision}
                />
              )}

              {activeScreen === "final" && (
                <FinalReportScreen
                  runId={runId}
                  query={query}
                  finalReport={finalReportText || reportState?.final_report || reportState?.synthesis_draft || ""}
                  findings={reportState?.findings || []}
                  reportState={reportState}
                  onNewResearch={handleNewResearch}
                />
              )}
            </>
          )}

          {activeTab === "reports" && (
            <ReportsScreen 
              onNewResearch={handleNewResearch} 
              onViewReport={handleViewReportFromDashboard}
            />
          )}

          {activeTab === "settings" && (
            <SettingsScreen />
          )}
        </main>
      </div>
    </div>
  );
}
