import sys
import json
import re
import datetime
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from typing import Dict, Any, List, Optional, Tuple, Union
from backend.config import settings
from backend.agents.llm_client import call_gemini, extract_json_from_llm
from backend.graph.state import FinSightState, Finding, CoverageLedgerEntry
from backend.agents.market_data import get_ticker_for_company
from backend.agents.news_research import evaluate_news_article_relevance
from backend.agents.verifier import (
    validate_numerical_and_temporal,
    check_claim_support,
    relevance_filter,
    validate_and_format_news_citation,
    deduplicate_findings,
    enforce_confidence_rules,
    extract_numbers_from_text,
    validate_causal_claims,
    resolve_chunk_id,
    match_figure_against_chunk_text
)

SYNTHESIS_SYSTEM_PROMPT = """You are a Lead Financial Equity Research Partner synthesizing verified evidence into discrete findings.
Synthesize all collected evidence into compact, verified structured findings directly addressing each Planner task.
Do NOT generate a full markdown report (the full report is compiled deterministically downstream from approved findings).

Output JSON ONLY matching this structure:
{
  "findings": [
    {
      "id": "finding_001",
      "task_id": "task_001",
      "category": "financial_performance",
      "statement": "Apple's Services gross margin percentage was 70.8% in FY2023, 73.9% in FY2024, and 75.4% in FY2025; total company gross margin was 44.1% in FY2023, 46.2% in FY2024, and 46.9% in FY2025.",
      "periods": ["FY2023", "FY2024", "FY2025"],
      "metrics": ["Services gross margin", "total company gross margin"],
      "figures": ["70.8%", "73.9%", "75.4%", "44.1%", "46.2%", "46.9%"],
      "confidence": "high",
      "evidence_chunk_ids": ["apple_10_k_fy2025_item_7_managements_discus_064"]
    }
  ]
}

Rules:
- Provide discrete findings for each Task ID in Planner Tasks to Answer.
- Categories: "financial_performance", "risk", "market_data", "news".
- Every financial finding must specify its task_id, exact reporting periods, metric names, figures, and supporting chunk IDs.
- For revenue/margin tasks: report exact verified figures across periods. Do NOT assert causal relationships between segment drivers and total company metrics unless the cited chunk explicitly establishes that causality.
- For regulatory and risk tasks: incorporate Item 1A and Item 3 disclosures citing their exact chunk IDs.
- For news findings: include complete news_citation and NEVER cite SEC chunk IDs.
- Never output raw SEC markdown tables or separator rows into statements.
"""

def normalize_company_name(name: Optional[str]) -> str:
    if not name:
        return ""
    n = str(name).lower().strip()
    if "apple" in n:
        return "Apple"
    if "nvidia" in n:
        return "NVIDIA"
    if "microsoft" in n:
        return "Microsoft"
    if "google" in n or "alphabet" in n:
        return "Google"
    if "amazon" in n:
        return "Amazon"
    if "meta" in n:
        return "Meta"
    if "tesla" in n:
        return "Tesla"
    return str(name).strip()

def execute_synthesis(state: FinSightState, sse_callback=None) -> Dict[str, Any]:
    """
    Synthesis Agent: integrates financial evidence, market data, news, and risk into structured findings.
    Enforces Claim Support, Relevance Filtering, Numerical & Temporal Validation, and Coverage Ledger synchronization.
    """
    if sse_callback:
        sse_callback({
            "agent": "synthesis",
            "status": "synthesizing_report"
        })

    query = state.get("query", "")
    companies = state.get("companies", ["NVIDIA"])
    tasks = state.get("tasks", [])
    fin_evidence = state.get("financial_evidence", [])
    market_data = state.get("market_data", {})
    news_evidence = state.get("news_evidence", [])
    risk_findings = state.get("risk_findings", [])
    human_decisions = state.get("human_decisions", {})
    retrieval_trace = dict(state.get("retrieval_trace", {}))
    coverage_ledger = list(state.get("coverage_ledger", []))
    draft = ""
    candidate_findings: List[Finding] = []
    parse_errors: List[str] = []

    # Compact, task-specific structured finding generation
    # Rather than sending a monolithic 24-chunk prompt that overflows max_tokens,
    # generate compact findings per task with only the relevant evidence for that task.
    for t_idx, t in enumerate(tasks, 1):
        tid = t.get("id", f"task_{t_idx:03d}")
        t_comp = t.get("company", companies[0] if companies else "Target Company")
        t_cat = t.get("category", "financial_performance")
        t_sub_q = t.get("sub_question", "")

        # 1. Market Data synthesis
        if t_cat == "market_data":
            mkt_info = market_data.get(t_comp) or market_data.get(t_comp.upper())
            if not mkt_info:
                ticker = get_ticker_for_company(t_comp)
                for c_k, c_v in market_data.items():
                    if c_v.get("ticker") == ticker:
                        mkt_info = c_v
                        break

            if mkt_info and mkt_info.get("price") not in [None, "N/A"]:
                price = mkt_info.get("price")
                change_pct = mkt_info.get("change_percent", "0.0%")
                mkt_cap = mkt_info.get("market_cap", "N/A")
                pe_ratio = mkt_info.get("pe_ratio", "N/A")
                h52 = mkt_info.get("52_week_high", "N/A")
                l52 = mkt_info.get("52_week_low", "N/A")
                mkt_date = mkt_info.get("date", datetime.date.today().isoformat())
                source_label = mkt_info.get("source", "Alpha Vantage")
                ticker = mkt_info.get("ticker", t_comp)

                cap_str = str(mkt_cap)
                try:
                    cap_val = float(mkt_cap)
                    if cap_val >= 1e12:
                        cap_str = f"${cap_val / 1e12:.2f} trillion"
                    elif cap_val >= 1e9:
                        cap_str = f"${cap_val / 1e9:.2f} billion"
                except (ValueError, TypeError):
                    pass

                stmt = (
                    f"As of {mkt_date}, {t_comp} ({ticker}) traded at ${price} (recent change: {change_pct}). "
                    f"The 52-week trading range is ${l52} to ${h52}. "
                    f"The company has a market capitalization of {cap_str} and a P/E ratio of {pe_ratio}."
                )

                fid = f"finding_{len(candidate_findings) + 1:03d}"
                decision = human_decisions.get(fid, {})
                status = decision.get("status", "pending")
                mkt_chunk_id = f"mkt_{ticker}_{mkt_date}"

                candidate_findings.append({
                    "id": fid,
                    "task_id": tid,
                    "category": "market_data",
                    "statement": decision.get("edited_text") or stmt,
                    "confidence": "high",
                    "evidence_chunk_ids": [mkt_chunk_id],
                    "status": status,
                    "edited_text": decision.get("edited_text"),
                    "rejection_reason": decision.get("reason"),
                    "evidence_request_note": decision.get("note"),
                    "news_citation": None,
                    "numerically_verified": True,
                    "cited_figures": [f"${price}", change_pct, f"${l52}", f"${h52}", str(pe_ratio)],
                    "temporal_labels": [mkt_date],
                    "validation_status": "valid",
                    "citation_status": "supported",
                    "figure_status": "verified"
                })
            else:
                limitation_msg = (mkt_info.get("limitation") if mkt_info else None) or f"Live market data telemetry unavailable for {t_comp}."
                for entry in coverage_ledger:
                    if entry.get("task_id") == tid:
                        entry["qc_status"] = "LIMITATION"
                        entry["evidence_limitation"] = limitation_msg
            continue

        # 2. News synthesis
        if t_cat == "news":
            ticker = get_ticker_for_company(t_comp)
            comp_articles = [
                n for n in news_evidence 
                if (n.get("company", "").lower() == t_comp.lower() or n.get("ticker") == ticker)
                and n.get("is_relevant", True)
            ]
            comp_articles.sort(key=lambda x: x.get("relevance_score", 0.0), reverse=True)

            valid_art = None
            valid_score = 0.0
            for art in comp_articles:
                is_rel, rel_score, _ = evaluate_news_article_relevance(art, t_comp, ticker)
                if is_rel:
                    valid_art = art
                    valid_score = rel_score
                    break

            if valid_art:
                top_art = valid_art
                art_title = top_art.get("title", "")
                art_source = top_art.get("source", "News Feed")
                art_pub = top_art.get("published", "")
                art_sentiment = top_art.get("sentiment_label", "Neutral")
                art_score = top_art.get("sentiment_score", 0.0)
                art_summary = top_art.get("summary", "")

                stmt = (
                    f"Recent market news for {t_comp}: '{art_title}' ({art_source}, {art_pub}). "
                    f"Sentiment: {art_sentiment} (score: {art_score}). {art_summary}"
                )
                fid = f"finding_{len(candidate_findings) + 1:03d}"
                decision = human_decisions.get(fid, {})
                status = decision.get("status", "pending")
                news_chunk_id = f"news_{ticker}_{art_pub or 'recent'}"

                candidate_findings.append({
                    "id": fid,
                    "task_id": tid,
                    "category": "news",
                    "statement": decision.get("edited_text") or stmt,
                    "confidence": "medium",
                    "evidence_chunk_ids": [news_chunk_id],
                    "status": status,
                    "edited_text": decision.get("edited_text"),
                    "rejection_reason": decision.get("reason"),
                    "evidence_request_note": decision.get("note"),
                    "news_citation": {
                        "title": art_title,
                        "source": art_source,
                        "date": art_pub,
                        "url": top_art.get("url", "")
                    },
                    "numerically_verified": None,
                    "cited_figures": [str(art_score)],
                    "temporal_labels": [art_pub] if art_pub else [],
                    "validation_status": "valid",
                    "citation_status": "supported",
                    "figure_status": "not_applicable"
                })
            else:
                limitation_msg = f"No sufficiently relevant news retrieved for {t_comp}."
                fid = f"finding_{len(candidate_findings) + 1:03d}"
                candidate_findings.append({
                    "id": fid,
                    "task_id": tid,
                    "category": "news",
                    "statement": limitation_msg,
                    "confidence": "low",
                    "evidence_chunk_ids": [],
                    "status": "pending",
                    "news_citation": None,
                    "numerically_verified": None,
                    "cited_figures": [],
                    "temporal_labels": [],
                    "validation_status": "valid",
                    "citation_status": "unsupported",
                    "figure_status": "not_applicable"
                })
                for entry in coverage_ledger:
                    if entry.get("task_id") == tid:
                        entry["qc_status"] = "LIMITATION"
                        entry["evidence_limitation"] = limitation_msg
            continue

        # 3. Check for pre-validated risk findings (enriching with recent news catalysts)
        if t_cat == "risk":
            matching_rfs = [rf for rf in risk_findings if rf.get("task_id") == tid]
            if not matching_rfs:
                matching_rfs = [rf for rf in risk_findings if normalize_company_name(rf.get("company")) == normalize_company_name(t_comp)]
            
            ticker = get_ticker_for_company(t_comp)
            recent_risk_news = [
                n for n in news_evidence 
                if (n.get("company", "").lower() == t_comp.lower() or n.get("ticker") == ticker)
                and n.get("is_relevant", True)
                and evaluate_news_article_relevance(n, t_comp, ticker)[0]
                and (n.get("sentiment_score", 0.0) < 0.1 or any(k in n.get("title", "").lower() for k in ["risk", "antitrust", "investigation", "export", "scrutiny", "probe"]))
            ]

            if matching_rfs:
                for rf in matching_rfs:
                    fid = f"finding_{len(candidate_findings) + 1:03d}"
                    decision = human_decisions.get(fid, {})
                    stmt = rf.get("statement", "")
                    news_cit = None
                    if recent_risk_news:
                        art = recent_risk_news[0]
                        stmt = f"{stmt} Recent news catalyst: '{art.get('title')}' ({art.get('source')}, sentiment: {art.get('sentiment_label')})."
                        news_cit = {"title": art.get("title"), "source": art.get("source"), "date": art.get("published"), "url": art.get("url")}

                    candidate_findings.append({
                        "id": fid,
                        "task_id": tid,
                        "category": "risk",
                        "statement": stmt,
                        "confidence": rf.get("confidence", "high"),
                        "evidence_chunk_ids": rf.get("evidence_chunk_ids", []),
                        "status": decision.get("status", "pending"),
                        "edited_text": decision.get("edited_text"),
                        "rejection_reason": decision.get("reason"),
                        "evidence_request_note": decision.get("note"),
                        "news_citation": news_cit,
                        "numerically_verified": None,
                        "cited_figures": rf.get("cited_figures", []),
                        "temporal_labels": rf.get("temporal_labels", []),
                        "validation_status": "valid"
                    })
                continue

        # 4. Gather task-specific evidence (top 2-3 chunks max)
        t_ev = [c for c in fin_evidence if c.get("task_id") == tid or tid in c.get("task_ids", [])]
        if not t_ev:
            norm_c = normalize_company_name(t_comp)
            t_ev = [c for c in fin_evidence if normalize_company_name(c.get("metadata", {}).get("company")) == norm_c]

        if not t_ev and t_cat == "financial_performance":
            # No evidence available: do NOT fabricate a fake finding.
            # Mark explicit evidence limitation in coverage ledger instead.
            for entry in coverage_ledger:
                if entry.get("task_id") == tid:
                    entry["qc_status"] = "LIMITATION"
                    entry["evidence_limitation"] = f"No relevant SEC evidence found for {t_comp}."
            continue

        # Format compact task prompt
        ev_text = "\n".join([f"[{c['chunk_id']}]: {c.get('text', '')[:650]}" for c in t_ev[:3]])
        task_prompt = f"""Target Company: {t_comp}
Task ID: {tid}
Objective: {t_sub_q}

Verified SEC Evidence:
{ev_text if ev_text else 'No direct SEC evidence.'}

Instructions:
Generate a single compact JSON object with this exact structure:
{{
  "statement": "Clear factual finding answering the objective with exact figures and periods.",
  "periods": ["FY2023", "FY2024", "FY2025"],
  "metrics": ["Metric 1", "Metric 2"],
  "figures": ["figure1", "figure2"],
  "confidence": "high",
  "evidence_chunk_ids": ["{t_ev[0]['chunk_id'] if t_ev else ''}"]
}}
Rules:
- State verified figures from evidence. Do not claim causality unless explicitly evidenced.
- Never output raw table formatting.
"""
        try:
            task_resp, meta = call_gemini(
                task_prompt,
                system_instruction=SYNTHESIS_SYSTEM_PROMPT,
                model=settings.MODEL_SYNTHESIS,
                component="synthesis",
                run_id=state.get("run_id"),
                max_tokens=1200,
                return_metadata=True
            )
            finish_reason = meta.get("finish_reason", "stop")
            if finish_reason == "length":
                print(f"[Synthesis Notice] Output truncated for task {tid}. Attempting bounded repair.")

            task_json = extract_json_from_llm(task_resp, run_id=state.get("run_id"))
            # Could be dict or list under 'findings' or direct dict
            findings_data = task_json.get("findings") if isinstance(task_json, dict) and "findings" in task_json else [task_json]
            if isinstance(findings_data, dict):
                findings_data = [findings_data]

            for item in findings_data:
                if not isinstance(item, dict) or not item.get("statement"):
                    continue
                fid = f"finding_{len(candidate_findings) + 1:03d}"
                decision = human_decisions.get(fid, {})
                status = decision.get("status", "pending")
                raw_cids = item.get("evidence_chunk_ids", [])
                resolved_cids = [resolve_chunk_id(cid, fin_evidence) for cid in raw_cids if cid]
                if not resolved_cids and t_ev:
                    resolved_cids = [t_ev[0]["chunk_id"]]

                candidate_findings.append({
                    "id": fid,
                    "task_id": tid,
                    "category": item.get("category", t_cat),
                    "statement": decision.get("edited_text") or item.get("statement", ""),
                    "confidence": item.get("confidence", "high"),
                    "evidence_chunk_ids": resolved_cids,
                    "status": status,
                    "edited_text": decision.get("edited_text"),
                    "rejection_reason": decision.get("reason"),
                    "evidence_request_note": decision.get("note"),
                    "news_citation": None,
                    "numerically_verified": False,
                    "cited_figures": item.get("figures", []),
                    "temporal_labels": item.get("periods", []),
                    "validation_status": "valid"
                })

        except Exception as e:
            parse_errors.append(f"Task {tid} synthesis error: {e}")
            print(f"[Synthesis Error] Task {tid} generation failed: {e}")
            # Do NOT create fake findings like 'Structured synthesis output could not be generated'

    # Requirement A.7: Diagnostic Artifacts
    per_task_finding_counts = {t["id"]: sum(1 for f in candidate_findings if f.get("task_id") == t["id"]) for t in tasks}
    synthesis_diagnostics = {
        "finish_reason": "stop",
        "parsed_findings": [dict(f) for f in candidate_findings],
        "parse_errors": parse_errors,
        "per_task_finding_counts": per_task_finding_counts
    }

    # Requirement 7: Relevance Filter — Drop any finding not linked to a Planner task
    relevant_findings = relevance_filter(candidate_findings, tasks)

    processed_findings: List[Finding] = []
    task_map = {t["id"]: t for t in tasks}

    for f in relevant_findings:
        task_id = f.get("task_id")
        task_obj = task_map.get(task_id, {})
        task_company = task_obj.get("company") or normalize_company_name(f.get("statement"))
        evidence_chunks = f.get("evidence_chunk_ids", [])
        statement = f.get("statement", "")
        cat = f.get("category", "financial_performance")

        if cat == "market_data":
            f["validation_status"] = "valid"
            f["citation_status"] = "supported"
            f["approval_status"] = f.get("status", "pending")
            has_figures = len(f.get("cited_figures", [])) > 0
            f["numerically_verified"] = has_figures
            f["figure_status"] = "verified" if has_figures else "not_applicable"
            f["confidence"] = "high"
            processed_findings.append(f)
            continue

        if cat == "news":
            f["approval_status"] = f.get("status", "pending")
            f["figure_status"] = "not_applicable"
            f["numerically_verified"] = None

            # Fallback limitation case
            if "no sufficiently relevant news retrieved" in statement.lower():
                f["validation_status"] = "valid"
                f["citation_status"] = "unsupported"
                f["confidence"] = "low"
                processed_findings.append(f)
                continue

            # Validate news article relevance
            news_cit = f.get("news_citation") or {}
            target_ticker = get_ticker_for_company(task_company)
            is_rel, rel_score, rel_reason = evaluate_news_article_relevance(news_cit, task_company, target_ticker=target_ticker)
            if is_rel and news_cit.get("title"):
                f["validation_status"] = "valid"
                f["citation_status"] = "supported"
                f["confidence"] = "medium"
            else:
                f["validation_status"] = "valid"
                f["citation_status"] = "unsupported"
                f["confidence"] = "low"
                f["rejection_reason"] = rel_reason
            processed_findings.append(f)
            continue

        # Step 1: Ensure task-specific evidence chunks are linked if missing
        if task_id and not any(c["chunk_id"] in evidence_chunks for c in fin_evidence):
            task_cids = [c["chunk_id"] for c in fin_evidence if c.get("task_id") == task_id or task_id in c.get("task_ids", [])]
            if task_cids:
                evidence_chunks = list(dict.fromkeys(evidence_chunks + task_cids))
                f["evidence_chunk_ids"] = evidence_chunks

        matching_chunks = [ch for ch in fin_evidence if ch.get("chunk_id") in evidence_chunks]
        if not matching_chunks and task_id:
            matching_chunks = [ch for ch in fin_evidence if ch.get("task_id") == task_id or task_id in ch.get("task_ids", [])]

        # Step 2: Causal Claims validation (split if unbacked)
        cleaned_stmt, was_split = validate_causal_claims(statement, matching_chunks)
        if was_split:
            f["statement"] = cleaned_stmt
            statement = cleaned_stmt

        # Step 3: Numerical and Temporal Validation
        is_num_valid, matched_nums, periods, val_status, fig_details = validate_numerical_and_temporal(
            statement, matching_chunks, company=task_company, return_figure_details=True
        )

        # Step 4: Numerical Recovery against all evidence for that company if initial chunks missed figures
        if (not is_num_valid or val_status == "dropped") and cat == "financial_performance":
            norm_c = normalize_company_name(task_company)
            other_chunks = [
                ch for ch in fin_evidence 
                if ch.get("chunk_id") not in evidence_chunks 
                and normalize_company_name(ch.get("metadata", {}).get("company")) == norm_c
            ]
            if other_chunks:
                is_rec_valid, rec_nums, rec_periods, rec_status, rec_details = validate_numerical_and_temporal(
                    statement, other_chunks, company=norm_c, return_figure_details=True
                )
                if is_rec_valid and rec_status != "dropped":
                    is_num_valid = True
                    matched_nums = rec_nums
                    periods = list(dict.fromkeys(periods + rec_periods))
                    val_status = rec_status
                    fig_details = rec_details
                    supporting_cids = [
                        ch["chunk_id"] for ch in other_chunks 
                        if any(match_figure_against_chunk_text(fig, ch.get("text", "")) for fig in matched_nums)
                    ]
                    if supporting_cids:
                        f["evidence_chunk_ids"] = list(dict.fromkeys(evidence_chunks + supporting_cids))
                        evidence_chunks = f["evidence_chunk_ids"]
                        matching_chunks = [ch for ch in fin_evidence if ch.get("chunk_id") in evidence_chunks]

        # Step 5: Semantic Claim Support Check
        is_supported, sup_reason = check_claim_support(f, fin_evidence, news_evidence)

        # Step 6: Record Figure Verification Outcomes and Rejection Reasons
        has_figures = len(matched_nums) > 0
        if cat == "risk" and not has_figures:
            f["numerically_verified"] = None
            f["figure_status"] = "not_applicable"
        else:
            f["numerically_verified"] = is_num_valid and has_figures
            f["figure_status"] = "verified" if (is_num_valid and has_figures) else "unverified"

        f["cited_figures"] = matched_nums
        f["temporal_labels"] = periods
        f["validation_status"] = val_status
        f["citation_status"] = "supported" if is_supported else "unsupported"
        f["approval_status"] = f.get("status", "pending")
        f["figure_details"] = fig_details

        # Step 7: Keep unsupported findings out of final approved report (Requirement B.8)
        if cat == "financial_performance" and (val_status == "dropped" or not is_num_valid or not is_supported):
            f["status"] = "rejected"
            f["rejection_reason"] = "Unsupported figures or missing evidence in SEC filings"

        # Prevent raw Markdown tables or large SEC blocks
        if "|" in statement or "---" in statement or len(statement) > 400:
            clean_lines = [line.strip() for line in statement.splitlines() if not line.strip().startswith("|") and "---" not in line]
            statement = " ".join(clean_lines).strip()
            if not statement or len(statement) < 15 or "|" in statement:
                continue
            f["statement"] = statement

        # Requirement 9: Confidence rules
        f["confidence"] = enforce_confidence_rules(f, is_supported=is_supported, is_num_valid=is_num_valid)
        processed_findings.append(f)

    # Requirement 8: Deduplicate findings
    final_findings = deduplicate_findings(processed_findings)

    # Requirement 5: Update Retrieval Trace with cited chunks
    for task in tasks:
        tid = task.get("id")
        if tid in retrieval_trace:
            cited = [
                cid for f in final_findings
                if f.get("task_id") == tid
                for cid in f.get("evidence_chunk_ids", [])
            ]
            retrieval_trace[tid]["cited_chunks"] = list(dict.fromkeys(cited))

    # Requirement 1: Synchronize Coverage Ledger
    ledger_map = {e["task_id"]: e for e in coverage_ledger}
    for task in tasks:
        tid = task.get("id")
        sem_kws = [k.lower() for k in task.get("semantic_keywords", [])]
        task_comp = str(task.get("company", "")).lower()

        # Find best finding addressing this task
        matching_findings = [f for f in final_findings if f.get("task_id") == tid]
        if not matching_findings:
            task_cat = task.get("category", "")
            other_task_ids = {t["id"] for t in tasks if t["id"] != tid}
            matching_findings = [
                f for f in final_findings
                if (not f.get("task_id") or f.get("task_id") not in other_task_ids)
                and task_comp in f.get("statement", "").lower()
                and f.get("category") == task_cat
                and any(k in f.get("statement", "").lower() for k in sem_kws if k not in ["services", "company", "quarter", "apple", "growth"])
            ]

        approved_matching = [f for f in matching_findings if f.get("status") in ["approved", "pending"] and f.get("validation_status") != "dropped"]

        if tid in ledger_map:
            entry = ledger_map[tid]
            task_cited = list(dict.fromkeys([
                cid for f in matching_findings 
                for cid in f.get("evidence_chunk_ids", [])
                if cid
            ]))
            all_retrieved = list(entry.get("evidence_retrieved", []))
            entry["cited_chunks"] = task_cited
            entry["retrieved_unused_chunks"] = [c for c in all_retrieved if c not in task_cited]
            if task_cited:
                entry["evidence_retrieved"] = task_cited

            entry["finding_ids"] = [f["id"] for f in matching_findings]

            if approved_matching:
                best_f = approved_matching[0]
                entry["final_finding"] = " ".join([f.get("statement", "") for f in approved_matching])
                entry["finding_id"] = best_f.get("id")
                stmt_lower = entry["final_finding"].lower()
                is_margin_task = "margin" in task.get("sub_question", "").lower() or "margin" in task.get("clause", "").lower()
                is_revenue_task = any(r in task.get("sub_question", "").lower() or r in task.get("clause", "").lower() for r in ["revenue", "sales"]) and not is_margin_task
                is_price_task = any(p in task.get("sub_question", "").lower() or p in task.get("clause", "").lower() for p in ["price", "valuation", "p/e", "52-week"])
                
                meets_semantic = True
                if is_margin_task and not any(m in stmt_lower for m in ["%", "percent", "basis points", "margin"]):
                    meets_semantic = False
                elif is_revenue_task and not any(r in stmt_lower for r in ["$", "billion", "million", "revenue"]):
                    meets_semantic = False
                elif is_price_task and not any(p in stmt_lower for p in ["$", "price", "traded", "%"]):
                    meets_semantic = False

                if meets_semantic and best_f.get("validation_status") != "dropped" and (best_f.get("numerically_verified") is not False):
                    entry["qc_status"] = "PASSED"
                else:
                    entry["qc_status"] = "FAILED"
            else:
                entry["final_finding"] = None
                entry["finding_id"] = None
                task_cat = task.get("category", "")
                if entry.get("evidence_retrieved"):
                    entry["qc_status"] = "LIMITATION"
                    entry["evidence_limitation"] = "Evidence retrieved does not support quantified metrics for this task."
                elif task_cat == "market_data":
                    entry["qc_status"] = "LIMITATION"
                    entry["evidence_limitation"] = f"Market data telemetry unavailable for {task.get('company', 'target company')}."
                elif task_cat == "news":
                    entry["qc_status"] = "LIMITATION"
                    entry["evidence_limitation"] = f"Recent news feed unavailable for {task.get('company', 'target company')}."
                else:
                    entry["qc_status"] = "FAILED"
                    entry["evidence_limitation"] = "No relevant SEC evidence found."

    return {
        "synthesis_draft": draft,
        "findings": final_findings,
        "coverage_ledger": coverage_ledger,
        "retrieval_trace": retrieval_trace,
        "synthesis_diagnostics": synthesis_diagnostics,
        "run_status": "critiquing"
    }

def _build_fallback_synthesis(
    query: str,
    companies: List[str],
    tasks: List[Dict[str, Any]],
    fin_evidence: list,
    market_data: dict,
    news_evidence: list,
    risk_findings: list,
    human_decisions: dict
):
    findings: List[Finding] = []
    is_multi = len(companies) > 1

    # Map chunks per company
    company_chunks: Dict[str, List[Dict[str, Any]]] = {}
    for comp in companies:
        c_chunks = [
            c for c in fin_evidence
            if comp.lower() in str(c.get("metadata", {}).get("company", "")).lower()
        ]
        if not c_chunks:
            c_chunks = fin_evidence[:4]
        company_chunks[comp] = c_chunks

    finding_idx = 1
    for task in tasks:
        comp = task.get("company", companies[0])
        clause = task.get("clause") or task.get("sub_question", "")
        tid = task.get("id", f"task_{finding_idx:03d}")
        cat = task.get("category", "financial_performance")
        sem_kws = task.get("semantic_keywords", [])
        c_chunks = company_chunks.get(comp, [])
        c_chunk_ids = [c["chunk_id"] for c in c_chunks]

        # Check if pre-validated risk findings exist for this task
        matching_risk = [rf for rf in risk_findings if rf.get("task_id") == tid or (rf.get("category") == "risk" and cat == "risk")]
        if matching_risk:
            rf = matching_risk[0]
            f_obj: Finding = {
                "id": f"finding_{finding_idx:03d}",
                "task_id": tid,
                "category": "risk",
                "statement": rf.get("statement", ""),
                "confidence": rf.get("confidence", "high"),
                "evidence_chunk_ids": rf.get("evidence_chunk_ids", []),
                "status": "pending",
                "edited_text": None,
                "rejection_reason": None,
                "evidence_request_note": None,
                "news_citation": None,
                "numerically_verified": None,
                "figure_status": "not_applicable",
                "citation_status": "supported" if rf.get("evidence_chunk_ids") else "unsupported",
                "approval_status": "pending",
                "cited_figures": [],
                "temporal_labels": [],
                "validation_status": "valid"
            }
            findings.append(f_obj)
            finding_idx += 1
            continue

        # If synthesis failed for financial metrics, do NOT fabricate fake placeholder findings
        # Simply skip creating a fake finding; the task will be marked as an explicit limitation in coverage_ledger.
        continue

    # Apply human decisions
    for f in findings:
        fid = f["id"]
        if fid in human_decisions:
            dec = human_decisions[fid]
            f["status"] = dec.get("status", f["status"])
            if dec.get("status") in ["edit", "edited"] and dec.get("edited_text"):
                f["statement"] = dec["edited_text"]
                f["edited_text"] = dec["edited_text"]
            elif dec.get("status") in ["reject", "rejected"]:
                f["rejection_reason"] = dec.get("reason")
            elif dec.get("status") == "request_evidence":
                f["evidence_request_note"] = dec.get("note")

    # Build draft narrative
    if is_multi:
        comp_sections = ""
        matrix_rows = ""
        for comp in companies:
            comp_findings = [f for f in findings if comp.lower() in f.get("statement", "").lower()]
            stmt_list = "\n".join([f"- {cf['statement']} [{cf['id']}]" for cf in comp_findings[:4]])
            comp_sections += f"""
### {comp} — Detailed Clause Audits
{stmt_list if stmt_list else "- Primary SEC filings reviewed."}
"""
            m_fin = next((f["statement"][:45] + "..." for f in comp_findings if f["category"] == "financial_performance"), "Audited SEC disclosures")
            m_risk = next((f["statement"][:45] + "..." for f in comp_findings if f["category"] == "risk"), "Item 1A risk reviewed")
            matrix_rows += f"| **{comp}** | {m_fin} | {m_risk} | Audited SEC Filings |\n"

        draft = f"""# FinSight Institutional Research: {query}

## Summary
This institutional research report provides a multi-company synthesis across **{', '.join(companies)}**, addressing each clause of the research query with citations from primary SEC filings.

## Multi-Company Research Profiles
{comp_sections}

## Comparative Matrix
| Company | Financial Performance | Risk Exposures | Primary Filings |
| :--- | :--- | :--- | :--- |
{matrix_rows}
"""
    else:
        comp = companies[0] if companies else "Target Company"
        claims_list = "\n".join([f"- {f['statement']} [{f['id']}]" for f in findings])
        draft = f"""# FinSight Institutional Research: {query}

## Summary
This institutional research report provides an authoritative synthesis for **{comp}**, addressing all research clauses through verified SEC filings (10-K Item 1A/3, 10-Q, 8-K).

## Audited Disclosures by Clause
{claims_list}
"""

    return draft, findings
