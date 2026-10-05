import sys
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from typing import Dict, Any, List
from backend.config import settings
from backend.agents.llm_client import call_gemini, extract_json_from_llm
from backend.graph.state import FinSightState, Finding

RISK_SYSTEM_PROMPT = """You are a Principal Financial Risk Officer and Regulatory Analyst.
Analyze the provided SEC financial disclosures and news articles to identify material risks across 4 distinct categories:
- regulatory (export controls, antitrust, compliance, government scrutiny)
- competitive (rival architecture, pricing pressure, market share threats)
- financial (margins pressure, currency volatility, debt, capital expenditure burden)
- operational (supply chain concentration, foundry dependence, datacenter outages, energy limits)

For each distinct risk, cite the specific chunk_ids or news sources from the evidence that support it.
Output JSON ONLY in this format:
{
  "risks": [
    {
      "id": "risk_01",
      "statement": "Clear, objective, evidence-based statement of the risk.",
      "risk_type": "regulatory" | "competitive" | "financial" | "operational",
      "confidence": "high" | "medium" | "low",
      "evidence_chunk_ids": ["chunk_id_1", "chunk_id_2"]
    }
  ]
}
"""

def execute_risk_analysis(state: FinSightState, sse_callback=None) -> Dict[str, Any]:
    """
    Risk Agent: analyzes financial filings and news to generate structured risk findings.
    Only executes when the query or planner tasks contain a relevant risk or regulatory task.
    Never fabricates generic risks without supporting evidence.
    """
    tasks = state.get("tasks", [])
    query = state.get("query", "")
    risk_tasks = [t for t in tasks if t.get("category") == "risk"]
    
    # Phase 2.3: Skip Risk Agent if query/tasks contain no risk or regulatory requirement
    if not risk_tasks and not any(k in query.lower() for k in ["risk", "regulatory", "regulation", "legal", "export", "trade", "antitrust"]):
        return {"risk_findings": [], "run_status": "synthesizing"}

    if sse_callback:
        sse_callback({
            "agent": "risk",
            "status": "evaluating_risks"
        })

    fin_evidence = state.get("financial_evidence", [])
    news_evidence = state.get("news_evidence", [])
    companies = state.get("companies", [])
    if not companies:
        companies = list(dict.fromkeys([t.get("company") for t in tasks if t.get("company")]))

    # Only include relevant risk evidence (Item 1A, Item 3, trade, etc.)
    risk_evidence = [
        f for f in fin_evidence 
        if any(sec in str(f.get("metadata", {}).get("section", "")).lower() for sec in ["item 1a", "item 3", "legal", "risk", "preamble"]) or f.get("task_id") in [t["id"] for t in risk_tasks]
    ] or fin_evidence

    evidence_snippets = []
    for f in risk_evidence[:12]:
        evidence_snippets.append(f"[{f['chunk_id']}] ({f['metadata'].get('company')} | {f['metadata'].get('section', 'SEC Filing')}):\n{f['text'][:500]}")

    news_snippets = []
    for n in news_evidence[:6]:
        news_snippets.append(f"[News: {n.get('ticker')}] {n.get('title')}: {n.get('summary')}")

    tasks_context = "\n".join([
        f"- [Task ID: {t.get('id')}] For {t.get('company')}: {t.get('sub_question')}"
        for t in risk_tasks
    ])

    prompt = f"""Companies: {', '.join(companies)}

Risk Tasks to Address:
{tasks_context if tasks_context else 'Identify disclosed regulatory, legal, and operational risks.'}

SEC Financial Disclosures (Item 1A / Item 3 / MD&A):
{chr(10).join(evidence_snippets) if evidence_snippets else 'No direct SEC chunks available.'}

Recent News & Sentiment Evidence:
{chr(10).join(news_snippets) if news_snippets else 'No recent news available.'}

Analyze the evidence above and extract discrete risk findings addressing each task. Cite the exact chunk_ids from the SEC evidence. Do not fabricate claims.
"""

    run_id = state.get("run_id")
    raw_response = call_gemini(
        prompt, 
        system_instruction=RISK_SYSTEM_PROMPT,
        model=settings.MODEL_RISK,
        component="risk",
        run_id=run_id
    )
    risk_findings: List[Finding] = []

    try:
        parsed = extract_json_from_llm(raw_response, run_id=run_id)
        risks_list = parsed.get("risks", [])
        for idx, r in enumerate(risks_list, 1):
            stmt = r.get("statement", "").strip()
            cids = r.get("evidence_chunk_ids", [])
            
            # Match to corresponding risk task
            assigned_task = None
            for rt in risk_tasks:
                if any(k.lower() in stmt.lower() for k in rt.get("semantic_keywords", [])) or rt.get("company", "").lower() in stmt.lower():
                    assigned_task = rt
                    break
            if not assigned_task and risk_tasks:
                assigned_task = risk_tasks[min(idx - 1, len(risk_tasks) - 1)]

            if stmt and len(stmt) > 15:
                finding: Finding = {
                    "id": f"finding_risk_{idx:03d}",
                    "task_id": assigned_task["id"] if assigned_task else None,
                    "category": "risk",
                    "statement": stmt,
                    "confidence": r.get("confidence", "high"),
                    "evidence_chunk_ids": cids,
                    "status": "pending",
                    "edited_text": None,
                    "rejection_reason": None,
                    "evidence_request_note": None,
                    "news_citation": None,
                    "numerically_verified": None,
                    "figure_status": "not_applicable",
                    "citation_status": "supported" if cids else "unsupported",
                    "approval_status": "pending",
                    "cited_figures": [],
                    "temporal_labels": [],
                    "validation_status": "valid"
                }
                risk_findings.append(finding)
    except Exception as e:
        print(f"Error parsing risk findings from LLM: {e}")

    # No generic risk fabrication: if parsing failed or no evidence, return empty
    return {
        "risk_findings": risk_findings,
        "run_status": "synthesizing"
    }
