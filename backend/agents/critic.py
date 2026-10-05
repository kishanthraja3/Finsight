import sys
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import re
from typing import Dict, Any, List
from backend.config import settings
from backend.agents.llm_client import call_gemini, extract_json_from_llm
from backend.graph.state import FinSightState, CoverageLedgerEntry
from backend.agents.verifier import extract_reporting_periods, extract_numbers_from_text

CRITIC_SYSTEM_PROMPT = """You are the Senior Editorial Director and Chief Compliance Critic at an elite financial research institution.
Your job is to perform an uncompromising Quality Control (QC) review on the generated research findings and report draft.

Evaluate rigorously against 3 criteria:
1. Coverage: Are all the planner's original sub-questions and key financial metrics (revenue, segment breakdown, growth, risks) addressed?
2. Contradictions: Are there numerical or narrative contradictions between findings (e.g. conflicting margin numbers or dates)?
3. Unsupported Certainty: Does any finding make definitive claims not supported by evidence or claim 'high' confidence when evidence is vague?

Output JSON ONLY in this format:
{
  "passed": true/false,
  "issues": [
    "Issue 1 description: specific chunk or sub-task deficiency",
    "Issue 2 description: potential contradiction or certainty overstatement"
  ],
  "recommendations": "Concise guidance on what financial_research needs to re-retrieve"
}
"""

def execute_critic(state: FinSightState, sse_callback=None) -> Dict[str, Any]:
    """
    Critic Agent:
    - Enforces that EVERY task in the Coverage Ledger has either a supported finding OR an explicit "evidence limitation" (after max retries).
    - Semantic check: a margin task needs actual margin figures, not just any finding.
    - If not passed and retries < max_retries: fails run and sets affected_tasks for surgical re-retrieval.
    - If retries >= max_retries: writes explicit evidence limitations and passes.
    """
    tasks = state.get("tasks", [])
    findings = state.get("findings", [])
    draft = state.get("synthesis_draft", "")
    retry_count = state.get("retry_count", 0)
    max_retries = state.get("max_retries", settings.MAX_RETRIES)
    coverage_ledger = list(state.get("coverage_ledger", []))

    if sse_callback:
        sse_callback({
            "agent": "critic",
            "status": "evaluating_report",
            "retry_count": retry_count,
            "max_retries": max_retries
        })

    tasks_str = "\n".join([f"- [Task {t.get('id')}] ({t.get('category')}): {t.get('sub_question')}" for t in tasks])
    findings_str = "\n".join([
        f"- [{f.get('id', 'fid')}] ({f.get('category', 'financial_performance')} | Conf: {f.get('confidence', 'medium')}): {f.get('statement', '')} (Citations: {f.get('evidence_chunk_ids', [])})"
        for f in findings
    ])

    prompt = f"""Planner Tasks to Cover:
{tasks_str}

Synthesized Findings (Figures and growth rates verified deterministically against SEC filings):
{findings_str}

Draft Excerpt (first 1500 chars):
{draft[:1500]}

Perform the QC review. Note that numerical figures and calculated YoY growth rates (e.g. Services revenue and gross margins) are verified deterministically by the Verifier against SEC audited financial tables.
If all planner tasks are covered with evidence and there are no direct contradictions or missing sections, mark passed as true.
"""

    # Requirement 1, 18 & 20: Completeness Check & Ledger Integrity
    # Run deterministic checks FIRST. If deterministic checks fail, route directly to replanner without wasting an LLM call.
    affected_tasks = []
    affected_categories = []
    ledger_failures = []
    passed = False
    issues: List[str] = []

    for entry in coverage_ledger:
        tid = entry.get("task_id")
        task_text = entry.get("task", "")
        company = entry.get("company", "")
        sem_kws = [k.lower() for k in entry.get("semantic_keywords", [])]
        task_findings = [f for f in findings if f.get("task_id") == tid]
        
        # Requirement 20: The ledger's evidence column must show the chunks actually cited by that task's findings.
        # List retrieved-but-unused chunks separately. Allow several findings per task.
        cited_cids = list(dict.fromkeys([
            cid for f in task_findings 
            for cid in f.get("evidence_chunk_ids", [])
            if cid and not cid.startswith("mkt_") and not cid.startswith("news_")
        ]))
        all_retrieved_cids = list(entry.get("evidence_retrieved", []))
        unused_cids = [cid for cid in all_retrieved_cids if cid not in cited_cids]

        entry["cited_chunks"] = cited_cids
        entry["retrieved_unused_chunks"] = unused_cids
        # Ledger's evidence column reflects cited chunks when available
        entry["evidence_retrieved"] = cited_cids if cited_cids else all_retrieved_cids[:3]
        entry["finding_ids"] = [f["id"] for f in task_findings]
        
        combined_finding_text = " ".join([f["statement"] for f in task_findings]) if task_findings else str(entry.get("final_finding") or "")
        entry["final_finding"] = combined_finding_text if combined_finding_text else None

        # Base semantic presence check
        has_finding = len(task_findings) > 0 or bool(entry.get("final_finding"))
        task_lower = (task_text + " " + " ".join(sem_kws)).lower()
        finding_lower = combined_finding_text.lower()

        completeness_failed = False
        completeness_issue = ""

        if not has_finding:
            completeness_failed = True
            completeness_issue = f"Missing required evidence or findings for '{task_text}'."
        else:
            # Substantive claim support check: every finding for this task must have supported citations
            unsupported_findings = [
                f for f in task_findings 
                if (f.get("citation_status") == "unsupported" or f.get("validation_status") == "dropped")
                and "no sufficiently relevant news retrieved" not in f.get("statement", "").lower()
            ]
            if unsupported_findings:
                completeness_failed = True
                completeness_issue = f"Task '{tid}' contains substantive claims unsupported by cited evidence."

            # News semantic relevance & entity check
            is_news_task = (
                any(t.get("category") == "news" for t in tasks if t.get("id") == tid) or
                "news" in task_lower
            )
            if is_news_task and not completeness_failed:
                has_limitation = any("no sufficiently relevant news retrieved" in f.get("statement", "").lower() for f in task_findings)
                if has_limitation:
                    entry["qc_status"] = "LIMITATION"
                    entry["evidence_limitation"] = next((f.get("statement") for f in task_findings if "no sufficiently relevant news retrieved" in f.get("statement", "").lower()), f"No sufficiently relevant news retrieved for {company}.")
                else:
                    for nf in task_findings:
                        nc = nf.get("news_citation")
                        if not nc or not isinstance(nc, dict) or not nc.get("title"):
                            completeness_failed = True
                            completeness_issue = f"News task '{tid}' missing valid news citation."
                            break
                        from backend.agents.news_research import evaluate_news_article_relevance
                        from backend.agents.market_data import get_ticker_for_company
                        ticker = get_ticker_for_company(company)
                        is_rel, _, reason = evaluate_news_article_relevance(nc, company, target_ticker=ticker)
                        if not is_rel:
                            completeness_failed = True
                            completeness_issue = f"News task '{tid}' cites irrelevant news for {company}: {reason}"
                            break

            # Semantic domain checks
            if not completeness_failed and ("margin" in sem_kws or "margin" in task_lower):
                if not any(m in finding_lower for m in ["%", "percent", "basis points", "margin"]):
                    completeness_failed = True
                    completeness_issue = f"Margin task '{tid}' missing actual margin figures/percentages."

            if not completeness_failed and ("revenue" in sem_kws or "revenue" in task_lower) and "margin" not in task_lower:
                if not any(r in finding_lower for r in ["$", "billion", "million", "revenue"]):
                    completeness_failed = True
                    completeness_issue = f"Revenue task '{tid}' missing quantified revenue figures."

            # Requirement 18: COMPLETENESS CHECK
            # A "trend" or "trajectory" clause needs three or more periods with basis labelled.
            is_trend_task = any(w in task_lower for w in ["trend", "trajectory", "historical", "over time", "sequential", "evolution", "growth rate"])
            if is_trend_task and not completeness_failed:
                periods = extract_reporting_periods(combined_finding_text)
                quarters_years = re.findall(r'\b(?:Q[1-4]\s*(?:FY)?202[0-9]|FY202[0-9]|202[0-9])\b', combined_finding_text, re.IGNORECASE)
                all_periods = list(dict.fromkeys(periods + [qy.strip() for qy in quarters_years]))
                
                has_basis = any(b in finding_lower for b in ["gaap", "non-gaap", "yoy", "qoq", "year-over-year", "sequential", "basis", "gross margin", "net sales", "constant currency", "as reported", "growth", "percentage", "%"])
                
                if len(all_periods) < 3:
                    completeness_failed = True
                    completeness_issue = f"Trend/trajectory task '{tid}' incomplete: requires 3 or more reporting periods (found {len(all_periods)}: {all_periods})."
                elif not has_basis:
                    completeness_failed = True
                    completeness_issue = f"Trend/trajectory task '{tid}' incomplete: reporting basis (GAAP/non-GAAP, YoY/QoQ) must be explicitly labelled."

            # A "risk / impact" clause needs named specifics (the restriction or event, its date, and quantified impact when sources give one).
            is_risk_task = (
                any(t.get("category") == "risk" for t in tasks if t.get("id") == tid) or
                any(w in task_lower for w in ["regulatory", "regulation", "export control", "exposure", "dependency", "dependencies", "restriction", "sanction"]) or
                ("risk" in task_lower and "margin" not in task_lower)
            )
            if is_risk_task and not completeness_failed:
                has_named_specifics = bool(re.search(
                    r'\b(?:EAR|BIS|DMA|FTC|DOJ|Digital Markets Act|Export Administration|antitrust|sanctions?|restrictions?|licens(?:e|ing)|concentration|foundry|TSMC|supplier|vendor|tariffs?|H20|H200|Blackwell|Hopper|App Store|European Commission|European Union|EU)\b',
                    combined_finding_text,
                    re.IGNORECASE
                ))
                has_date_timeline = bool(re.search(
                    r'\b(?:202[0-9]|fiscal|quarter|annual|October|August|November|January|February|March|April|May|June|July|September|December|ongoing|current|currently|effective|compliance|pending|inquir(?:y|ies)|investigations?|proceedings?|disclosures?|actions?)\b',
                    combined_finding_text,
                    re.IGNORECASE
                ))
                if not has_named_specifics or not has_date_timeline:
                    completeness_failed = True
                    completeness_issue = f"Risk/impact task '{tid}' incomplete: needs named specifics (named restriction/event and date/timeline)."

        # Raw SEC table check: findings must be synthesized text, not dumped tables
        if has_finding and ("|" in combined_finding_text or "---" in combined_finding_text):
            completeness_failed = True
            completeness_issue = f"Task '{tid}' contains unparsed raw SEC table syntax instead of synthesized analysis."

        # Determine task QC status
        if completeness_failed:
            if retry_count < max_retries:
                entry["qc_status"] = "FAILED"
                affected_tasks.append(tid)
                fail_msg = f"Task Incompleteness on '{tid}' ({company}): {completeness_issue}"
                ledger_failures.append(fail_msg)
                matching_task = next((t for t in tasks if t.get("id") == tid), {})
                cat = matching_task.get("category", "financial_performance")
                if cat not in affected_categories:
                    affected_categories.append(cat)
            else:
                # Requirement 15, 18 & 20: Record explicit evidence limitation whenever a task is still incomplete after MAX_RETRIES
                limitation_msg = f"Evidence limitation for {company}: Disclosures in audited filings did not contain complete granular figures or disclosures to fully satisfy '{task_text}' after {max_retries} targeted gap-fill attempts."
                entry["evidence_limitation"] = limitation_msg
                entry["qc_status"] = "LIMITATION"
        else:
            entry["qc_status"] = "PASSED"

    # A failed coverage check must not be represented as a completed or approved report
    if ledger_failures or any(e.get("qc_status") == "FAILED" for e in coverage_ledger):
        passed = False
        issues = ledger_failures + [i for i in issues if i not in ledger_failures]
    else:
        all_tasks_accounted_for = (
            len(coverage_ledger) > 0 and 
            all(e.get("qc_status") in ["PASSED", "LIMITATION"] for e in coverage_ledger)
        )
        if all_tasks_accounted_for:
            # Deterministic checks passed; perform semantic compliance & contradiction review
            try:
                run_id = state.get("run_id")
                raw_response = call_gemini(
                    prompt, 
                    system_instruction=CRITIC_SYSTEM_PROMPT,
                    model=settings.MODEL_CRITIC,
                    run_id=run_id,
                    component="critic"
                )
                parsed = extract_json_from_llm(raw_response, run_id=run_id)
                llm_passed = bool(parsed.get("passed", False))
                llm_issues = parsed.get("issues", [])
                passed = llm_passed
                issues.extend(llm_issues)
            except Exception as e:
                print(f"Error during Critic LLM review: {e}")
                passed = False
                issues.append(f"Critic verification error: {str(e)}")
        else:
            passed = False
            issues.append("Coverage ledger is incomplete or uninitialized.")

    new_retry_count = retry_count + (1 if not passed else 0)

    if sse_callback:
        sse_callback({
            "agent": "critic",
            "status": "critic_passed" if passed else "critic_failed",
            "passed": passed,
            "issues": issues,
            "retry_count": new_retry_count,
            "max_retries": max_retries,
            "coverage_ledger": coverage_ledger
        })

    return {
        "critic_result": {
            "passed": passed,
            "issues": issues
        },
        "coverage_ledger": coverage_ledger,
        "retry_count": new_retry_count,
        "affected_tasks": affected_tasks if not passed else [],
        "affected_categories": affected_categories if not passed else [],
        "run_status": "awaiting_human" if passed else "replanning"
    }
