import sys
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from typing import Dict, Any, List, Literal
from langgraph.graph import StateGraph, END, START
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import interrupt

from backend.config import settings
from backend.graph.state import FinSightState, Finding
from backend.agents.planner import plan_research
from backend.agents.financial_research import execute_financial_research
from backend.agents.market_data import execute_market_data
from backend.agents.news_research import execute_news_research
from backend.agents.risk import execute_risk_analysis
from backend.agents.synthesis import execute_synthesis
from backend.agents.critic import execute_critic
from backend.agents.replanner import execute_replanner
from backend.agents.verifier import (
    validate_causal_claims,
    validate_numerical_and_temporal,
    check_claim_support,
    enforce_confidence_rules
)
from backend.agents.llm_client import telemetry_tracker

# SSE event bus registry keyed by run_id
SSE_CALLBACKS: Dict[str, Any] = {}

def get_sse_callback(run_id: str):
    return SSE_CALLBACKS.get(run_id)

def register_sse_callback(run_id: str, callback):
    SSE_CALLBACKS[run_id] = callback

def unregister_sse_callback(run_id: str):
    SSE_CALLBACKS.pop(run_id, None)

# --- Node implementations with targeted skip checks ---

def planner_node(state: FinSightState) -> Dict[str, Any]:
    run_id = state.get("run_id", "")
    cb = get_sse_callback(run_id)
    if cb:
        cb({"agent": "planner", "status": "planning_tasks", "query": state.get("query")})
    return plan_research(state)

def financial_research_node(state: FinSightState) -> Dict[str, Any]:
    sec_required = state.get("sec_retrieval_required")
    tasks = state.get("tasks", [])
    has_sec_task = any(t.get("agent") == "financial_research" or t.get("category") in ["financial_performance", "risk"] for t in tasks)
    
    if sec_required is False and not has_sec_task:
        return {"financial_evidence": []}

    affected = state.get("affected_categories")
    # SEC retrieval covers both financial metrics (Item 7/8) and regulatory/risk disclosures (Item 1A/3)
    if affected and "financial_performance" not in affected and "risk" not in affected:
        return {}
    run_id = state.get("run_id", "")
    cb = get_sse_callback(run_id)
    return execute_financial_research(state, sse_callback=cb)

def market_data_node(state: FinSightState) -> Dict[str, Any]:
    market_required = state.get("market_data_required")
    tasks = state.get("tasks", [])
    has_market_task = any(t.get("category") == "market_data" or t.get("agent") == "market_data" for t in tasks)
    query = state.get("query", "").lower()
    fallback_keywords = ["price", "price performance", "stock price", "stock performance", "valuation", "p/e", "pe ratio", "market cap", "returns", "volatility", "52-week"]
    needs_market = (market_required is True) or has_market_task or any(k in query for k in fallback_keywords)

    if not needs_market:
        return {"market_data": {}}

    affected = state.get("affected_categories")
    if affected and "market_data" not in affected:
        return {}
    run_id = state.get("run_id", "")
    cb = get_sse_callback(run_id)
    return execute_market_data(state, sse_callback=cb)

def news_research_node(state: FinSightState) -> Dict[str, Any]:
    news_required = state.get("news_required")
    tasks = state.get("tasks", [])
    has_news_task = any(t.get("category") == "news" or t.get("agent") == "news_research" for t in tasks)
    query = state.get("query", "").lower()
    fallback_keywords = ["news", "sentiment", "headline", "headlines", "press release", "recent catalyst", "catalysts", "breaking"]
    needs_news = (news_required is True) or has_news_task or any(k in query for k in fallback_keywords)

    if not needs_news:
        return {"news_evidence": []}

    affected = state.get("affected_categories")
    if affected and "news" not in affected:
        return {}
    run_id = state.get("run_id", "")
    cb = get_sse_callback(run_id)
    return execute_news_research(state, sse_callback=cb)

def risk_node(state: FinSightState) -> Dict[str, Any]:
    tasks = state.get("tasks", [])
    query = state.get("query", "").lower()
    needs_risk = any(t.get("category") == "risk" for t in tasks) or any(k in query for k in ["risk", "regulatory", "regulation", "legal", "export", "trade", "dma", "antitrust"])
    if not needs_risk:
        return {"risk_findings": []}

    affected = state.get("affected_categories")
    if affected and "risk" not in affected:
        return {}
    run_id = state.get("run_id", "")
    cb = get_sse_callback(run_id)
    return execute_risk_analysis(state, sse_callback=cb)

def synthesis_node(state: FinSightState) -> Dict[str, Any]:
    run_id = state.get("run_id", "")
    cb = get_sse_callback(run_id)
    return execute_synthesis(state, sse_callback=cb)

def critic_node(state: FinSightState) -> Dict[str, Any]:
    run_id = state.get("run_id", "")
    cb = get_sse_callback(run_id)
    return execute_critic(state, sse_callback=cb)

CANONICAL_ACTION_MAP = {
    "approve": "approved",
    "approved": "approved",
    "edit": "edited",
    "edited": "edited",
    "reject": "rejected",
    "rejected": "rejected",
    "request_evidence": "request_evidence",
    "request-evidence": "request_evidence",
    "request_more_evidence": "request_evidence",
    "request-more-evidence": "request_evidence",
}

def apply_decision_to_finding(f: Finding, dec: Dict[str, Any], state: FinSightState):
    raw_status = str(dec.get("status", "")).strip().lower()
    canonical = CANONICAL_ACTION_MAP.get(raw_status, f.get("status", "pending"))
    f["status"] = canonical
    
    if canonical == "edited":
        edited_text = dec.get("edited_text") or dec.get("statement") or f.get("statement", "")
        f["statement"] = edited_text
        f["edited_text"] = edited_text
        
        # Revalidate edited text against cited chunks
        fin_evidence = state.get("financial_evidence", [])
        news_evidence = state.get("news_evidence", [])
        cids = f.get("evidence_chunk_ids", [])
        matching_chunks = [c for c in fin_evidence if c.get("chunk_id") in cids]
        if not matching_chunks and f.get("task_id"):
            matching_chunks = [c for c in fin_evidence if c.get("task_id") == f.get("task_id")]
            
        cleaned_stmt, _ = validate_causal_claims(edited_text, matching_chunks)
        f["statement"] = cleaned_stmt
        
        is_supported, _ = check_claim_support(f, fin_evidence, news_evidence)
        f["citation_status"] = "supported" if is_supported else "unsupported"
        
        is_num_valid, matched_figs, temporal, _ = validate_numerical_and_temporal(cleaned_stmt, matching_chunks)
        f["numerically_verified"] = is_num_valid and len(matched_figs) > 0
        f["cited_figures"] = matched_figs
        f["temporal_labels"] = temporal
        f["figure_status"] = "verified" if f["numerically_verified"] else ("not_applicable" if not matched_figs else "unsupported")
        f["confidence"] = enforce_confidence_rules(f, is_supported=is_supported, is_num_valid=is_num_valid)
        
    elif canonical == "rejected":
        f["rejection_reason"] = dec.get("reason", "Rejected by human reviewer.")
    elif canonical == "request_evidence":
        f["evidence_request_note"] = dec.get("note", "Reviewer requested additional evidence.")

def human_review_node(state: FinSightState) -> Dict[str, Any]:
    """
    Human-In-The-Loop review node.
    - Normalizes actions to canonical vocabulary (approved, edited, rejected, request_evidence).
    - Detects pending findings even when previous decisions exist.
    - Revalidates edited findings against cited SEC evidence.
    - Ensures rejected findings never appear as approved findings.
    """
    findings = list(state.get("findings", []))
    human_decisions = dict(state.get("human_decisions", {}))

    # Apply any existing decisions
    for f in findings:
        fid = f.get("id")
        if fid in human_decisions:
            apply_decision_to_finding(f, human_decisions[fid], state)

    # Detect pending findings even if human_decisions already has prior keys
    pending_findings = [f for f in findings if f.get("status") == "pending" or f.get("id") not in human_decisions]

    if pending_findings:
        run_id = state.get("run_id", "")
        cb = get_sse_callback(run_id)
        if cb:
            cb({"agent": "human_review", "status": "awaiting_human_approval", "pending_count": len(pending_findings)})
        
        # Trigger LangGraph interrupt
        user_input = interrupt({
            "message": "Human review required. Approve, edit, reject, or request more evidence for findings.",
            "findings": findings,
            "pending_findings": pending_findings,
            "critic_result": state.get("critic_result", {})
        })
        
        # If user_input was provided on resume:
        if isinstance(user_input, dict) and "decisions" in user_input:
            new_decs = user_input["decisions"]
            human_decisions.update(new_decs)
            for f in findings:
                fid = f.get("id")
                if fid in new_decs:
                    apply_decision_to_finding(f, new_decs[fid], state)

    # If no active evidence requests and all findings have decisions, build the locked final report
    pending_count = sum(1 for f in findings if f.get("status") == "pending")
    has_replan_action = any(
        f.get("status") == "request_evidence" or 
        (f.get("status") in ["rejected", "reject"] and f.get("evidence_request_note"))
        for f in findings
    )
    final_report = ""
    if not has_replan_action and pending_count == 0:
        final_report = compile_final_report(state, findings)
        run_status = "complete"
        run_id = state.get("run_id", "")
        cb = get_sse_callback(run_id)
        if cb:
            cb({"agent": "human_review", "status": "all_approved", "run_status": "complete"})
    else:
        run_status = "awaiting_human" if pending_count > 0 else "replanning"

    return {
        "findings": findings,
        "human_decisions": human_decisions,
        "final_report": final_report,
        "run_status": run_status
    }

def compile_final_report(state: FinSightState, findings: List[Finding]) -> str:
    """
    Compiles locked final institutional report grounded strictly in approved/edited findings.
    - Every narrative sentence maps to an approved finding ID [finding_XXX].
    - Zero outside claims (unbacked prices, consensus ratings, ownership) are included.
    - Only claims 'verified' for figures that were numerically verified.
    - Uses 'Reviewed' for human review status.
    - Uses 'Summary' and eliminates analyst consensus language.
    - Includes 'Coverage' section with Coverage Ledger table and any evidence limitations.
    - 'Critic QC Passed' may appear only when every task is covered.
    - Formats per-company sections + Markdown comparative matrix if multi-company.
    """
    query = state.get("query", "")
    companies = state.get("companies", ["NVIDIA"])
    comp_str = ", ".join(companies)
    coverage_ledger = state.get("coverage_ledger", [])
    
    # Requirement 3: Generated strictly from approved/edited findings
    # Filter out any finding with raw table syntax or empty statements
    approved_findings = [
        f for f in findings 
        if f.get("status") in ["approved", "edited"] 
        and "|" not in f.get("statement", "") 
        and "---" not in f.get("statement", "")
        and len(f.get("statement", "").strip()) > 15
    ]
    total_findings = len(findings)
    reviewed_count = len(approved_findings)
    num_verified_count = sum(1 for f in approved_findings if f.get("numerically_verified"))

    by_category: Dict[str, List[Finding]] = {
        "financial_performance": [],
        "market_data": [],
        "risk": [],
        "news": []
    }
    for f in approved_findings:
        cat = f.get("category", "financial_performance")
        if cat in by_category:
            by_category[cat].append(f)
        else:
            by_category.setdefault(cat, []).append(f)

    # Phase 7 & 9: Truthful audit status labels
    has_failed_tasks = any(e.get("qc_status") == "FAILED" for e in coverage_ledger)
    has_limitations = any(e.get("qc_status") == "LIMITATION" for e in coverage_ledger)
    critic_passed = state.get("critic_result", {}).get("passed", False)
    run_status = state.get("run_status", "")

    if "rate_limit" in run_status:
        qc_label = "Generation Interrupted — Rate Limit"
    elif has_failed_tasks or not critic_passed:
        qc_label = "Review Failed"
    elif has_limitations:
        qc_label = "Reviewed — Evidence Limitations Remain"
    elif all(e.get("qc_status") == "PASSED" for e in coverage_ledger) and critic_passed:
        qc_label = "Reviewed — Complete"
    else:
        qc_label = "Review Incomplete"

    disclaimer = "\n\n---\n**Disclaimer**: *Research output only — not investment advice. FinSight Multi-Agent Intelligence System.*"
    
    header = f"""# FinSight Institutional Research Report
**Target Companies**: {comp_str}  
**Research Focus**: {query}  
**Review Status**: Reviewed ({reviewed_count}/{total_findings} claims approved; {num_verified_count} figures numerically verified)  
**Audit Status**: {qc_label} | Human Review Complete  

---
"""

    # Requirement 1 & 20: Mandatory Coverage section in final report
    # The ledger's evidence column must show the chunks actually cited by that task's findings.
    # List retrieved-but-unused chunks separately.
    coverage_rows = []
    for e in coverage_ledger:
        t_id = e.get("task_id", "")
        task_text = e.get("task", "").replace("|", "-")
        comp = e.get("company", "")
        
        cited = e.get("cited_chunks") or [c for c in e.get("evidence_retrieved", []) if not c.startswith("mkt_") and not c.startswith("news_")]
        unused = e.get("retrieved_unused_chunks") or []
        
        cited_str = ", ".join(cited[:3]) if cited else "None"
        unused_str = ", ".join(unused[:2]) if unused else "None"
        
        f_finding = (e.get("final_finding") or "No direct finding")[:80].replace("|", "-") + ("..." if len(e.get("final_finding") or "") > 80 else "")
        qc_stat = e.get("qc_status", "PENDING")
        limit_note = (e.get("evidence_limitation") or "None").replace("|", "-")
        coverage_rows.append(f"| {t_id} | {comp} | {task_text} | {cited_str} | {unused_str} | {f_finding} | {qc_stat} | {limit_note} |")

    coverage_section = f"""## Coverage

| Task ID | Company | Query Clause / Sub-Question | Cited Chunks | Retrieved-But-Unused Chunks | Final Finding | QC Status | Evidence Limitation |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
""" + "\n".join(coverage_rows) + "\n"

    if len(companies) > 1:
        # Multi-company comparative layout
        summary_sentences = []
        for f in approved_findings[:4]:
            tag = f"[{f['id']}]"
            stmt = f.get("statement", "").strip()
            if not stmt.endswith("."):
                stmt += "."
            summary_sentences.append(f"{stmt} {tag}")

        summary_body = " ".join(summary_sentences) if summary_sentences else f"Comprehensive comparative research conducted for {comp_str}."

        company_sections = []
        matrix_rows = []

        for comp in companies:
            comp_findings = [
                f for f in approved_findings
                if comp.lower() in f.get("statement", "").lower() or any(comp.lower() in str(cid).lower() for cid in f.get("evidence_chunk_ids", []))
            ]
            if not comp_findings:
                comp_findings = approved_findings

            fin_claims = [f for f in comp_findings if f.get("category") == "financial_performance"]
            mkt_claims = [f for f in comp_findings if f.get("category") == "market_data"]
            risk_claims = [f for f in comp_findings if f.get("category") == "risk"]
            news_claims = [f for f in comp_findings if f.get("category") == "news"]

            def format_claims(claim_list):
                lines = []
                for cl in claim_list:
                    stmt = cl.get("statement", "").strip()
                    fid = cl.get("id")
                    ver_tag = " | Figure Verified" if cl.get("numerically_verified") else (" | Figure N/A" if cl.get("figure_status") == "not_applicable" or (cl.get("category") == "risk" and not cl.get("cited_figures")) else "")
                    cit_tag = " | Citation Supported" if cl.get("citation_status") == "supported" else ""
                    chunk_ref = f" | {', '.join(cl.get('evidence_chunk_ids')[:2])}" if cl.get("evidence_chunk_ids") else ""
                    lines.append(f"- {stmt} [{fid}{ver_tag}{cit_tag}{chunk_ref}]")
                return "\n".join(lines)

            # Requirement 22: Hide subsections that have no findings
            subsections = [f"### {comp} — Audited Research Analysis"]
            if fin_claims:
                subsections.append(f"#### Financial Performance & SEC Audited Disclosures\n{format_claims(fin_claims)}")
            if mkt_claims:
                subsections.append(f"#### Valuation & Market Telemetry\n{format_claims(mkt_claims)}")
            if risk_claims:
                subsections.append(f"#### Strategic & Regulatory Risk Disclosures (Item 1A / Item 3)\n{format_claims(risk_claims)}")
            if news_claims:
                subsections.append(f"#### Recent News & Market Landscape\n{format_claims(news_claims)}")

            company_sections.append("\n\n".join(subsections) + "\n")

            f_summary = (fin_claims[0].get("statement", "N/A")[:50] + "...") if fin_claims else "N/A"
            f_id = f" [{fin_claims[0].get('id')}]" if fin_claims else ""
            m_summary = (mkt_claims[0].get("statement", "N/A")[:45] + "...") if mkt_claims else "N/A"
            m_id = f" [{mkt_claims[0].get('id')}]" if mkt_claims else ""
            r_summary = (risk_claims[0].get("statement", "N/A")[:45] + "...") if risk_claims else "N/A"
            r_id = f" [{risk_claims[0].get('id')}]" if risk_claims else ""
            n_summary = (news_claims[0].get("statement", "N/A")[:45] + "...") if news_claims else "N/A"
            n_id = f" [{news_claims[0].get('id')}]" if news_claims else ""

            matrix_rows.append(
                f"| **{comp}** | {f_summary}{f_id} | {m_summary}{m_id} | {r_summary}{r_id} | {n_summary}{n_id} |"
            )

        matrix_table = f"""## Comparative Matrix

| Target Company | Financial Trajectory | Market Telemetry | Primary Risk Exposures | Sentiment & Catalysts |
| :--- | :--- | :--- | :--- | :--- |
""" + "\n".join(matrix_rows) + "\n"

        body = f"""## Summary
{summary_body}

{coverage_section}

## Company-Specific Analysis
{"".join(company_sections)}

{matrix_table}
"""

    else:
        # Single company institutional layout
        comp = companies[0] if companies else "Target Company"
        
        summary_sentences = []
        for f in approved_findings[:3]:
            stmt = f.get("statement", "").strip()
            if not stmt.endswith("."):
                stmt += "."
            summary_sentences.append(f"{stmt} [{f['id']}]")
        summary_text = " ".join(summary_sentences) if summary_sentences else f"Institutional research analysis for {comp}."

        def render_section_claims(category_name):
            cat_list = by_category.get(category_name, [])
            out = []
            for cl in cat_list:
                stmt = cl.get("statement", "").strip()
                fid = cl.get("id")
                tag_parts = [fid]
                if cl.get("numerically_verified"):
                    tag_parts.append("Figure Verified")
                elif cl.get("figure_status") == "not_applicable" or (cl.get("category") == "risk" and not cl.get("cited_figures")):
                    tag_parts.append("Figure N/A")
                if cl.get("citation_status") == "supported":
                    tag_parts.append("Citation Supported")
                if cl.get("evidence_chunk_ids"):
                    tag_parts.append(", ".join(cl.get("evidence_chunk_ids")[:2]))
                if cl.get("news_citation") and isinstance(cl.get("news_citation"), dict):
                    pub = cl["news_citation"].get("publisher")
                    date = cl["news_citation"].get("published_date")
                    if pub:
                        tag_parts.append(f"Source: {pub}, {date}")
                tag = f"[{' | '.join(tag_parts)}]"
                out.append(f"- {stmt} {tag}")
            return "\n".join(out)

        # Requirement 22: Hide report sections that have no findings
        sections = [
            f"## Summary\n{summary_text}",
            coverage_section.strip()
        ]
        if by_category.get("financial_performance"):
            sections.append(f"## Financial Performance & Segment Trajectory\n{render_section_claims('financial_performance')}")
        if by_category.get("market_data"):
            sections.append(f"## Market Valuation & Telemetry Metrics\n{render_section_claims('market_data')}")
        if by_category.get("risk"):
            sections.append(f"## Strategic & Regulatory Risk Disclosures (Item 1A / Item 3)\n{render_section_claims('risk')}")
        if by_category.get("news"):
            sections.append(f"## News, Catalysts & Market Landscape\n{render_section_claims('news')}")

        body = "\n\n".join(sections) + "\n"

    # Add Audited Claims Ledger Table
    ledger_rows = []
    for f in approved_findings:
        fid = f.get("id", "")
        cat = f.get("category", "")
        conf = str(f.get("confidence", "")).upper()
        num_v = "Yes" if f.get("numerically_verified") else "No"
        cids = ", ".join(f.get("evidence_chunk_ids", [])[:2]) or (f.get("news_citation", {}).get("publisher") if isinstance(f.get("news_citation"), dict) else "N/A")
        stmt_short = f.get("statement", "").replace("|", "-")
        ledger_rows.append(f"| {fid} | {cat} | {conf} | {num_v} | {cids} | {stmt_short} |")

    ledger_table = f"""
## Audited Claims Ledger
| ID | Category | Confidence | Figure Verified | Primary Citation | Statement |
| :--- | :--- | :--- | :--- | :--- | :--- |
""" + "\n".join(ledger_rows)

    return header + "\n" + body + "\n" + ledger_table + disclaimer

def replanner_node(state: FinSightState) -> Dict[str, Any]:
    run_id = state.get("run_id", "")
    cb = get_sse_callback(run_id)
    
    # Check bounded recovery / call budget
    metrics = telemetry_tracker.get_run_metrics(run_id)
    if metrics.get("logical_calls", 0) >= settings.MAX_LLM_CALLS_PER_RUN:
        print(f"[Replanner Notice] Call budget reached ({metrics.get('logical_calls')}/{settings.MAX_LLM_CALLS_PER_RUN}). Skipping replan and proceeding to report.")
        return {
            "retry_count": state.get("retry_count", 0) + 1,
            "affected_tasks": [],
            "affected_categories": []
        }
        
    return execute_replanner(state, sse_callback=cb)

# --- Conditional routing functions ---

def route_critic(state: FinSightState) -> Literal["replanner", "human_review"]:
    critic_res = state.get("critic_result", {})
    passed = critic_res.get("passed", False)
    retry_count = state.get("retry_count", 0)
    max_retries = state.get("max_retries", settings.MAX_RETRIES)

    # Check call budget to enforce bounded recovery
    run_id = state.get("run_id", "")
    metrics = telemetry_tracker.get_run_metrics(run_id)
    if metrics.get("logical_calls", 0) >= settings.MAX_LLM_CALLS_PER_RUN:
        print(f"[Graph Notice] Call budget reached ({metrics.get('logical_calls')}/{settings.MAX_LLM_CALLS_PER_RUN}). Finalizing partial report.")
        return "human_review"

    if not passed and retry_count < max_retries:
        return "replanner"
    return "human_review"

def route_human_review(state: FinSightState) -> Literal["replanner", "__end__"]:
    findings = state.get("findings", [])
    retry_count = state.get("retry_count", 0)
    max_retries = state.get("max_retries", settings.MAX_RETRIES)

    # Requirement 3: Replan ONLY when the user explicitly requests additional evidence
    # or a rejected claim genuinely requires replacement research (has explicit request note).
    # Approving remaining findings does NOT automatically rerun research merely because another finding was previously rejected.
    has_evidence_request = any(f.get("status") == "request_evidence" for f in findings)
    has_replacement_needed = any(
        f.get("status") in ["rejected", "reject"] and f.get("evidence_request_note")
        for f in findings
    )

    if (has_evidence_request or has_replacement_needed) and retry_count < max_retries:
        return "replanner"

    return "__end__"

def build_finsight_graph():
    """Constructs the complete FinSight multi-agent research workflow graph."""
    graph = StateGraph(FinSightState)

    # Add all nodes
    graph.add_node("planner", planner_node)
    graph.add_node("financial_research", financial_research_node)
    graph.add_node("market_data", market_data_node)
    graph.add_node("news_research", news_research_node)
    graph.add_node("risk", risk_node)
    graph.add_node("synthesis", synthesis_node)
    graph.add_node("critic", critic_node)
    graph.add_node("human_review", human_review_node)
    graph.add_node("replanner", replanner_node)

    # Edges from START to planner
    graph.add_edge(START, "planner")

    # Parallel fan-out from planner to financial_research, market_data, news_research
    graph.add_edge("planner", "financial_research")
    graph.add_edge("planner", "market_data")
    graph.add_edge("planner", "news_research")

    # Fan-in all three to risk
    graph.add_edge("financial_research", "risk")
    graph.add_edge("market_data", "risk")
    graph.add_edge("news_research", "risk")

    # Risk to synthesis
    graph.add_edge("risk", "synthesis")

    # Synthesis to critic
    graph.add_edge("synthesis", "critic")

    # Critic conditional routing: if QC/coverage fails and under max retries, route to replanner for targeted re-retrieval
    graph.add_conditional_edges(
        "critic",
        route_critic,
        {
            "replanner": "replanner",
            "human_review": "human_review"
        }
    )

    # Human review conditional routing
    graph.add_conditional_edges(
        "human_review",
        route_human_review,
        {
            "replanner": "replanner",
            "__end__": END
        }
    )

    # Replanner fan-out back to the parallel research nodes -> risk -> synthesis -> critic -> human_review
    graph.add_edge("replanner", "financial_research")
    graph.add_edge("replanner", "market_data")
    graph.add_edge("replanner", "news_research")

    memory = MemorySaver()
    app = graph.compile(checkpointer=memory)
    return app
