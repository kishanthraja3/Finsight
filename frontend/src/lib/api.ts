const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

export interface Finding {
  id: string;
  company?: string;
  task_id?: string;
  category: "financial_performance" | "market_data" | "risk" | "news";
  statement: string;
  confidence: "high" | "medium" | "low";
  evidence_chunk_ids: string[];
  status: "pending" | "approved" | "edited" | "rejected" | "request_evidence";
  edited_text?: string | null;
  rejection_reason?: string | null;
  evidence_request_note?: string | null;
  news_citation?: {
    title: string;
    publisher: string;
    url: string;
    published_date: string;
  } | null;
  numerically_verified?: boolean | null;
  cited_figures?: string[];
  temporal_labels?: string[];
  validation_status?: string;
  citation_status?: "supported" | "unsupported" | "not_applicable";
  figure_status?: "verified" | "unverified" | "not_applicable";
  approval_status?: "pending" | "approved" | "edited" | "rejected";
}

export interface CoverageLedgerEntry {
  task_id: string;
  task: string;
  company: string;
  required_doc_types: string[];
  required_sections: string[];
  required_evidence_type: string;
  semantic_keywords?: string[];
  evidence_retrieved: string[];
  final_finding?: string | null;
  finding_id?: string | null;
  qc_status: "PENDING" | "PASSED" | "FAILED" | "LIMITATION";
  evidence_limitation?: string | null;
}

export interface ReportState {
  run_id: string;
  query: string;
  companies: string[];
  tasks: any[];
  coverage_ledger?: CoverageLedgerEntry[];
  retrieval_trace?: Record<string, any>;
  synthesis_draft: string;
  findings: Finding[];
  critic_result: {
    passed: boolean;
    issues: string[];
  };
  retry_count: number;
  max_retries: number;
  run_status: "planning" | "retrieving" | "synthesizing" | "critiquing" | "awaiting_human" | "replanning" | "complete" | "error";
  affected_categories?: string[];
  affected_tasks?: string[];
  final_report?: string;
  active_model?: string;
  fallback_active?: boolean;
}

export async function createRun(query: string): Promise<{ run_id: string; status: string }> {
  const res = await fetch(`${API_BASE_URL}/api/runs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query }),
  });
  if (!res.ok) {
    throw new Error(`Failed to create run: ${res.statusText}`);
  }
  return res.json();
}

export async function getReportState(runId: string): Promise<ReportState> {
  const res = await fetch(`${API_BASE_URL}/api/runs/${runId}/report`, { cache: "no-store" });
  if (!res.ok) {
    throw new Error(`Failed to get report: ${res.statusText}`);
  }
  return res.json();
}

export async function submitFindingDecision(
  runId: string,
  findingId: string,
  decision: { 
    status: "approve" | "edit" | "reject" | "request_evidence"; 
    edited_text?: string | null; 
    reason?: string | null;
    note?: string | null;
  }
): Promise<any> {
  const res = await fetch(`${API_BASE_URL}/api/runs/${runId}/findings/${findingId}/decision`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(decision),
  });
  if (!res.ok) {
    throw new Error(`Failed to submit decision: ${res.statusText}`);
  }
  return res.json();
}

export async function approveAllFindings(runId: string): Promise<any> {
  const res = await fetch(`${API_BASE_URL}/api/runs/${runId}/findings/approve-all`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
  });
  if (!res.ok) {
    throw new Error(`Failed to approve all findings: ${res.statusText}`);
  }
  return res.json();
}

export async function getFinalReport(runId: string): Promise<{ 
  run_id: string; 
  run_status: string; 
  final_report: string; 
  findings: Finding[];
  coverage_ledger?: CoverageLedgerEntry[];
  retrieval_trace?: Record<string, any>;
}> {
  const res = await fetch(`${API_BASE_URL}/api/runs/${runId}/report/final`, { cache: "no-store" });
  if (!res.ok) {
    throw new Error(`Failed to get final report: ${res.statusText}`);
  }
  return res.json();
}

export function getDownloadUrl(runId: string): string {
  return `${API_BASE_URL}/api/runs/${runId}/report/download`;
}

export function getPdfDownloadUrl(runId: string): string {
  return `${API_BASE_URL}/api/runs/${runId}/report/pdf`;
}

export async function fetchReportsList(): Promise<any[]> {
  try {
    const res = await fetch(`${API_BASE_URL}/api/reports`, { cache: "no-store" });
    if (!res.ok) return [];
    const data = await res.json();
    return data.reports || [];
  } catch {
    return [];
  }
}

export function getStreamUrl(runId: string): string {
  return `${API_BASE_URL}/api/runs/${runId}/stream`;
}
