from typing import TypedDict, Optional, List, Dict, Any, Annotated

def reduce_run_status(current: str, update: str) -> str:
    return update if update else current

class Finding(TypedDict):
    id: str
    task_id: Optional[str]
    category: str  # "financial_performance" | "market_data" | "risk" | "news"
    statement: str
    confidence: str  # "high" | "medium" | "low"
    evidence_chunk_ids: List[str]
    status: str  # "pending" | "approved" | "edited" | "rejected" | "request_evidence"
    edited_text: Optional[str]
    rejection_reason: Optional[str]
    evidence_request_note: Optional[str]
    news_citation: Optional[Dict[str, str]]
    numerically_verified: Optional[bool]
    cited_figures: Optional[List[str]]
    temporal_labels: Optional[List[str]]
    validation_status: Optional[str]  # "valid" | "downgraded" | "dropped"
    citation_status: Optional[str]    # "supported" | "unsupported" | "not_applicable"
    figure_status: Optional[str]      # "verified" | "unverified" | "not_applicable"
    approval_status: Optional[str]    # "pending" | "approved" | "edited" | "rejected"

class CoverageLedgerEntry(TypedDict):
    task_id: str
    task: str
    company: str
    required_doc_types: List[str]
    required_sections: List[str]
    required_evidence_type: str
    semantic_keywords: List[str]
    evidence_retrieved: List[str]
    cited_chunks: Optional[List[str]]
    retrieved_unused_chunks: Optional[List[str]]
    final_finding: Optional[str]
    finding_id: Optional[str]
    finding_ids: Optional[List[str]]
    required_data_sources: Optional[List[str]]
    qc_status: str  # "PENDING" | "PASSED" | "FAILED" | "LIMITATION"
    evidence_limitation: Optional[str]

class RetrievalTraceEntry(TypedDict):
    task_id: str
    query_used: str
    expanded_terms: List[str]
    retrieved_chunk_ids: List[Dict[str, Any]]  # [{"chunk_id": "...", "score": 0.42, "doc_type": "...", "section": "..."}]
    selected_chunks: List[str]
    cited_chunks: List[str]

class FinSightState(TypedDict):
    query: str
    run_id: str                                      # unique run identifier for SSE routing
    companies: List[str]
    market_data_required: Optional[bool]
    news_required: Optional[bool]
    sec_retrieval_required: Optional[bool]
    intent_classification: Optional[Dict[str, Any]]
    tasks: List[Dict[str, Any]]                     # planner's decomposed sub-tasks
    coverage_ledger: List[CoverageLedgerEntry]      # mandatory coverage ledger
    retrieval_trace: Dict[str, Any]                 # task_id -> retrieval trace metrics
    financial_evidence: List[Dict[str, Any]]        # retrieved chunks + metadata
    market_data: Dict[str, Any]                     # per-company price/fundamentals
    news_evidence: List[Dict[str, Any]]             # articles + sentiment scores
    risk_findings: List[Finding]
    findings: List[Finding]                         # full merged set after synthesis
    synthesis_draft: str
    critic_result: Dict[str, Any]                   # {"passed": bool, "issues": list[str]}
    retry_count: int
    max_retries: int                                # from config.MAX_RETRIES
    human_decisions: Dict[str, Any]                 # finding_id -> decision payload
    affected_categories: List[str]                  # set by replanner on rejection
    affected_tasks: List[str]                       # surgical task-level replanning
    final_report: str
    run_status: Annotated[str, reduce_run_status]   # "planning" | "retrieving" | "synthesizing" | "critiquing" | "awaiting_human" | "replanning" | "complete"

