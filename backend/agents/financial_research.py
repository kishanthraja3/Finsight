import sys
import re
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from typing import Dict, Any, List, Optional
import chromadb
from sentence_transformers import SentenceTransformer

from backend.config import settings
from backend.agents.llm_client import call_gemini, extract_json_from_llm
from backend.graph.state import FinSightState

def extract_entity_terms(text: str) -> List[str]:
    """Extracts entity terms, product names, regulatory programs, and periods from text."""
    patterns = [
        r'\b(?:H20|H200|Blackwell|Hopper|Rubin|GB200|B200|B100)\b',
        r'\b(?:DMA|Digital Markets Act|EAR|Export Administration Regulations|BIS|Commerce Department|FTC|DOJ)\b',
        r'\b(?:Q[1-4]\s*FY202[5-9]|FY202[5-9])\b',
        r'\b(?:Item 1A|Item 3|Item 7|Item 8|Item 2)\b',
        r'\b(?:Data Center|Services|Gaming|Intelligent Cloud|Compute)\b',
        r'\b(?:foundry|TSMC|advanced packaging|CoWoS|supplier concentration)\b',
        r'\b(?:gross margin|operating margin|revenue trajectory|guidance)\b'
    ]
    terms = []
    for p in patterns:
        matches = re.findall(p, text, re.IGNORECASE)
        for m in matches:
            cleaned = m.strip()
            if cleaned and cleaned not in terms:
                terms.append(cleaned)
    return terms

EVALUATE_EVIDENCE_PROMPT = """You are a Principal Financial Auditor and RAG Evaluation Judge.
Evaluate the retrieved financial evidence against the sub-question based on 4 criteria:
1. Coverage: Does the evidence provide clear numerical or qualitative answers to the specific question?
2. Source Quality: Is it sourced from the appropriate section (e.g. Item 8 or Financial Statements for numbers, MD&A for discussion, 8-K for latest earnings)?
3. Recency: For recent quarter questions, is the evidence sufficiently current (e.g. 10-Q/8-K preferred over older 10-K)?
4. Contradiction: Do any of the retrieved chunks conflict or provide incompatible numbers?

Sub-question: {sub_question}
Target Company: {company}

Retrieved Chunks:
{chunks_text}

Output JSON ONLY:
{{
  "passed": true/false,
  "confidence": "high" | "medium" | "low",
  "reason": "Detailed evaluation explaining coverage and quality",
  "suggested_query_refinement": "Refined query if passed is false"
}}
"""

GENERATE_QUERY_PROMPT = """You are a Financial Search Optimization Specialist.
Given a financial research sub-question and any previous search feedback, generate a precise, keyword-rich semantic search query to find the exact numbers and disclosures in SEC filings.

Sub-question: {sub_question}
Company: {company}
Previous Feedback: {feedback}

Output JSON ONLY:
{{
  "search_query": "Targeted search query text",
  "preferred_doc_type": "10-K" | "10-Q" | "8-K" | "any"
}}
"""

_embedding_model = None
_chroma_client = None

def get_resources():
    global _embedding_model, _chroma_client
    if _embedding_model is None:
        _embedding_model = SentenceTransformer(settings.EMBEDDING_MODEL)
    if _chroma_client is None:
        _chroma_client = chromadb.PersistentClient(path=str(Path(settings.CHROMA_PERSIST_DIR).resolve()))
    return _embedding_model, _chroma_client

def execute_financial_research(state: FinSightState, sse_callback=None) -> Dict[str, Any]:
    """
    Agentic RAG loop implementing:
    - Multi-doc type retrieval across 10-K (Item 1A/3), 10-Q, 8-K with section-targeted filtering
    - Query expansion with entity and regulation terms
    - Mandatory Retrieval Trace logging (chunk IDs, scores, selected, cited)
    - Coverage Ledger synchronization
    """
    model, chroma_client = get_resources()
    try:
        collection = chroma_client.get_collection("finsight_documents")
    except Exception as e:
        print(f"Warning: Could not get finsight_documents collection: {e}")
        collection = None

    tasks = [t for t in state.get("tasks", []) if t.get("agent") in ["financial_research", "risk"]]
    if not tasks:
        tasks = state.get("tasks", [])

    # Requirement 15: Rerun only the relevant Planner tasks, not the whole pipeline
    affected_tasks = state.get("affected_tasks", [])
    if affected_tasks:
        targeted_tasks = [t for t in tasks if t.get("id") in affected_tasks]
        if targeted_tasks:
            tasks = targeted_tasks

    max_retries = state.get("max_retries", settings.MAX_RETRIES)
    current_retry = state.get("retry_count", 0)
    accumulated_evidence: List[Dict[str, Any]] = list(state.get("financial_evidence", []))
    coverage_ledger = list(state.get("coverage_ledger", []))
    ledger_map = {e["task_id"]: e for e in coverage_ledger}
    retrieval_trace: Dict[str, Any] = dict(state.get("retrieval_trace", {}))

    for task in tasks:
        task_id = task.get("id", "task_001")
        # Skip tasks targeted to market data or news
        req_sources = task.get("required_data_sources", [])
        if req_sources and "sec_filings" not in req_sources and task.get("agent") != "financial_research":
            continue
        if task.get("category") in ["market_data", "news"] or task.get("agent") in ["market_data", "news_research"]:
            continue

        company = task.get("company", state.get("companies", ["NVIDIA"])[0])
        sub_question = task.get("sub_question", "")
        clause = task.get("clause", sub_question)
        req_docs = task.get("required_doc_types", ["10-K"])
        req_sections = task.get("required_sections", [])
        evidence_type = task.get("required_evidence_type", "financial_metric")

        # Requirement 4: Query expansion with task-specific entity terms ONLY (no global query bleed)
        base_entities = extract_entity_terms(sub_question + " " + clause)
        expanded_query = sub_question
        if base_entities:
            expanded_query = f"{sub_question} {' '.join(base_entities)}"

        if sse_callback:
            sse_callback({
                "agent": "financial_research",
                "status": "querying" if current_retry == 0 else "retrying",
                "attempt": current_retry + 1,
                "max_retries": max_retries,
                "company": company,
                "task_id": task_id,
                "task": sub_question
            })

        current_query = expanded_query
        
        # Requirement 19: GAP-FILL RETRIEVAL
        # For incomplete tasks (retries), have LLM list specifics a domain reader expects
        top_k = getattr(settings, "RETRIEVAL_TOP_K", 8)
        if current_retry > 0 or task_id in affected_tasks:
            gap_prompt = f"""You are a Principal Financial Auditor.
For the research sub-task below, list the exact specific data points a domain reader would expect from SEC filings (periods, quantified impacts, named actions/regulations/products).
Task: {sub_question}
Company: {company}

Output JSON ONLY:
{{
  "expected_periods": ["Q2 FY2027", "Q1 FY2027", "FY2026"],
  "quantified_metrics": ["gross margin %", "revenue in billions", "charges in millions"],
  "named_entities_actions": ["specific regulation or product or supplier"],
  "expanded_search_query": "Targeted query incorporating these specifics"
}}
"""
            run_id = state.get("run_id")
            try:
                raw_gap = call_gemini(gap_prompt, model=settings.MODEL_GAP_FILL, run_id=run_id, component="gap_fill")
                parsed_gap = extract_json_from_llm(raw_gap, run_id=run_id)
                gen_query = parsed_gap.get("expanded_search_query")
                if gen_query:
                    current_query = gen_query
                else:
                    exp_periods = " ".join(parsed_gap.get("expected_periods", []))
                    exp_metrics = " ".join(parsed_gap.get("quantified_metrics", []))
                    current_query = f"{company} {sub_question} {exp_periods} {exp_metrics} {' '.join(req_sections)}"
            except Exception:
                current_query = f"{company} {sub_question} {' '.join(req_sections)} {' '.join(base_entities)}"

        retrieved_chunks: List[Dict[str, Any]] = []
        all_retrieved_for_trace: List[Dict[str, Any]] = []

        is_revenue_task = any(w in clause.lower() or w in sub_question.lower() for w in ["revenue", "net sales", "segment", "growth"]) and "margin" not in clause.lower()
        is_margin_task = "margin" in clause.lower() or "margin" in sub_question.lower()
        is_regulatory_task = any(w in clause.lower() or w in sub_question.lower() for w in ["regulatory", "regulation", "legal", "europe", "european", "dma", "antitrust"])

        if collection and collection.count() > 0:
            query_emb = model.encode([current_query]).tolist()
            where_clause = {"company": company} if company else None

            # Retrieve top_k * 2 candidates for reranking
            results = collection.query(
                query_embeddings=query_emb,
                n_results=min(top_k * 2, 20),
                where=where_clause,
                include=["documents", "metadatas", "distances"]
            )

            if results and "ids" in results and results["ids"]:
                ids = results["ids"][0]
                docs = results["documents"][0]
                metas = results["metadatas"][0]
                dists = results.get("distances", [[0.5] * len(ids)])[0]

                for cid, text, meta, dist in zip(ids, docs, metas, dists):
                    score = round(max(0.0, 1.0 - dist), 4)
                    chunk_item = {
                        "chunk_id": cid,
                        "text": text,
                        "metadata": meta,
                        "score": score
                    }
                    retrieved_chunks.append(chunk_item)
                    if not any(r["chunk_id"] == cid for r in all_retrieved_for_trace):
                        all_retrieved_for_trace.append(chunk_item)

            # Requirement 3, 4 & 19: Targeted query across relevant doc types (10-K, 10-Q, 8-K)
            needs_multi_doc = any(
                k in sub_question.lower() or k in clause.lower()
                for k in ["risk", "regulatory", "regulation", "legal", "export control", "trade", "margin", "services", "data center", "current status", "licensing", "dependency", "dma", "europe"]
            )

            if req_sections or needs_multi_doc:
                target_kw = " ".join(req_sections + base_entities)
                sec_query = f"{company} {target_kw} {clause}"
                sec_emb = model.encode([sec_query]).tolist()

                try:
                    sec_results = collection.query(
                        query_embeddings=sec_emb,
                        n_results=min(top_k * 2, 20),
                        where=where_clause,
                        include=["documents", "metadatas", "distances"]
                    )
                    if sec_results and "ids" in sec_results and sec_results["ids"]:
                        s_ids = sec_results["ids"][0]
                        s_docs = sec_results["documents"][0]
                        s_metas = sec_results["metadatas"][0]
                        s_dists = sec_results.get("distances", [[0.5] * len(s_ids)])[0]

                        for cid, text, meta, dist in zip(s_ids, s_docs, s_metas, s_dists):
                            score = round(max(0.0, 1.0 - dist), 4)
                            chunk_item = {
                                "chunk_id": cid,
                                "text": text,
                                "metadata": meta,
                                "score": score
                            }
                            if not any(r["chunk_id"] == cid for r in all_retrieved_for_trace):
                                all_retrieved_for_trace.append(chunk_item)
                            if not any(c["chunk_id"] == cid for c in retrieved_chunks):
                                retrieved_chunks.append(chunk_item)
                except Exception as e:
                    print(f"Targeted multi-doc retrieval notice: {e}")

            if is_regulatory_task:
                item3_query = f"{company} Item 3 Legal Proceedings Digital Markets Act European Commission antitrust investigation fines"
                item3_emb = model.encode([item3_query]).tolist()
                try:
                    i3_results = collection.query(
                        query_embeddings=item3_emb,
                        n_results=min(top_k * 2, 10),
                        where=where_clause,
                        include=["documents", "metadatas", "distances"]
                    )
                    if i3_results and "ids" in i3_results and i3_results["ids"]:
                        for cid, text, meta, dist in zip(i3_results["ids"][0], i3_results["documents"][0], i3_results["metadatas"][0], i3_results.get("distances", [[0.5]*len(i3_results["ids"][0])])[0]):
                            score = round(max(0.0, 1.0 - dist), 4)
                            chunk_item = {"chunk_id": cid, "text": text, "metadata": meta, "score": score}
                            if not any(r["chunk_id"] == cid for r in all_retrieved_for_trace):
                                all_retrieved_for_trace.append(chunk_item)
                            if not any(c["chunk_id"] == cid for c in retrieved_chunks):
                                retrieved_chunks.append(chunk_item)
                except Exception as e:
                    print(f"Item 3 targeted retrieval notice: {e}")

        # Requirement 19: RERANKING
        # Rerank candidate chunks based on similarity, section match, doc type, and entity coverage


        def compute_rerank_score(c: Dict[str, Any]) -> float:
            base_score = c.get("score", 0.0)
            meta = c.get("metadata", {})
            sec = str(meta.get("section", "")).lower().replace("\xa0", " ")
            doc = str(meta.get("doc_type", "")).upper()
            txt = c.get("text", "").lower()

            rerank_val = base_score * 0.50
            if any(rs.lower() in sec for rs in req_sections):
                rerank_val += 0.25
            if doc in [d.upper() for d in req_docs]:
                rerank_val += 0.15
            entity_matches = sum(1 for e in base_entities if e.lower() in txt)
            rerank_val += min(0.15, entity_matches * 0.04)

            # Domain-specific prioritization
            if is_revenue_task:
                # Prioritize chunks with segment net sales tables and trajectory
                segment_terms = [e.lower() for e in base_entities if e.lower() in ["services", "data center", "gaming", "intelligent cloud", "cloud", "azure"]]
                matches_segment = any(st in txt for st in segment_terms) or (company.lower() in ["nvidia"] and "data center" in txt) or (company.lower() in ["apple"] and "services" in txt) or (company.lower() in ["microsoft"] and ("azure" in txt or "cloud" in txt))
                if matches_segment and ("net sales" in txt or "revenue" in txt) and ("$" in txt or "billion" in txt or "million" in txt):
                    rerank_val += 0.35
                if "gross margin percentage" in txt and "net sales" not in txt and "revenue" not in txt:
                    rerank_val -= 0.20
            elif is_margin_task:
                if "gross margin" in txt or "operating margin" in txt:
                    if "%" in txt or "percentage" in txt or "basis points" in txt:
                        rerank_val += 0.30
            elif is_regulatory_task:
                if any(k in txt for k in ["digital markets act", "dma", "european commission", "article 5", "investigation", "alternative fee", "app store", "export administration", "ear", "bis", "export control", "license", "licensing", "entity list"]):
                    rerank_val += 0.35
                if "item 3" in sec or "legal proceedings" in sec:
                    rerank_val += 0.35
                if "item 1a" in sec or "risk factors" in sec:
                    rerank_val += 0.25
                if "europe" in txt or "european" in txt or "china" in txt:
                    rerank_val += 0.20

            return rerank_val

        retrieved_chunks.sort(key=compute_rerank_score, reverse=True)

        # Requirement 19: Tasks must not share identical evidence sets unless sources genuinely overlap
        # Check previously selected chunks in accumulated_evidence
        previously_selected = [e["chunk_id"] for e in accumulated_evidence if e.get("task_id") != task_id]
        
        prioritized_chunks: List[Dict[str, Any]] = []
        overlapping_chunks: List[Dict[str, Any]] = []

        for ch in retrieved_chunks:
            if ch["chunk_id"] not in previously_selected:
                prioritized_chunks.append(ch)
            else:
                overlapping_chunks.append(ch)

        # Build candidate pool giving priority to task-distinct evidence
        best_chunks = (prioritized_chunks + overlapping_chunks)[:max(4, top_k // 2)]
        eval_result = {
            "passed": len(retrieved_chunks) > 0,
            "confidence": "high" if len(retrieved_chunks) >= 3 else "medium",
            "reason": f"Retrieved {len(retrieved_chunks)} relevant candidate chunks from SEC database."
        }

        # Select top evidence chunks for this task (guaranteeing diverse section coverage when requested)
        if is_regulatory_task:
            item3_chunk = next((c for c in prioritized_chunks if "item 3" in str(c.get("metadata", {}).get("section", "")).lower() or "legal proceedings" in str(c.get("metadata", {}).get("section", "")).lower()), None)
            item1a_chunk = next((c for c in prioritized_chunks if "item 1a" in str(c.get("metadata", {}).get("section", "")).lower()), None)
            selected_set = []
            if item1a_chunk:
                selected_set.append(item1a_chunk)
            if item3_chunk and item3_chunk not in selected_set:
                selected_set.append(item3_chunk)
            for c in prioritized_chunks:
                if c not in selected_set and len(selected_set) < 4:
                    selected_set.append(c)
            selected_for_task = selected_set if selected_set else best_chunks[:4]
        else:
            selected_for_task = best_chunks[:4]
        selected_chunk_ids = [c["chunk_id"] for c in selected_for_task]

        # Accumulate evidence while retaining all task IDs associated with each chunk
        for chunk in selected_for_task:
            existing_entry = next((e for e in accumulated_evidence if e["chunk_id"] == chunk["chunk_id"]), None)
            if existing_entry:
                if "task_ids" not in existing_entry:
                    existing_entry["task_ids"] = [existing_entry.get("task_id")]
                if task_id not in existing_entry["task_ids"]:
                    existing_entry["task_ids"].append(task_id)
            else:
                chunk_entry = {
                    "chunk_id": chunk["chunk_id"],
                    "text": chunk["text"],
                    "metadata": chunk["metadata"],
                    "score": chunk.get("score", 0.5),
                    "task_id": task_id,
                    "task_ids": [task_id],
                    "sub_question": sub_question,
                    "confidence": eval_result.get("confidence", "medium"),
                    "eval_reason": eval_result.get("reason", ""),
                }
                accumulated_evidence.append(chunk_entry)

        # Requirement 5: Log Retrieval Trace for this task (preserving retrieved, selected, supplied, cited separately)
        retrieval_trace[task_id] = {
            "task_id": task_id,
            "clause": clause,
            "sub_question": sub_question,
            "company": company,
            "query_used": current_query,
            "expanded_terms": base_entities,
            "retrieved_chunk_ids": [
                {
                    "chunk_id": r["chunk_id"],
                    "score": r.get("score", 0.0),
                    "doc_type": r["metadata"].get("doc_type"),
                    "section": r["metadata"].get("section")
                }
                for r in all_retrieved_for_trace
            ],
            "retrieved_chunks": [r["chunk_id"] for r in all_retrieved_for_trace],
            "selected_chunks": selected_chunk_ids,
            "supplied_to_synthesis": selected_chunk_ids,
            "used_chunks": selected_chunk_ids,
            "cited_chunks": [] # will be populated in synthesis
        }

        # Requirement 1: Synchronize Coverage Ledger with evidence retrieved
        if task_id in ledger_map:
            ledger_map[task_id]["evidence_retrieved"] = selected_chunk_ids
        else:
            coverage_ledger.append({
                "task_id": task_id,
                "task": sub_question,
                "company": company,
                "required_doc_types": req_docs,
                "required_sections": req_sections,
                "required_evidence_type": evidence_type,
                "semantic_keywords": task.get("semantic_keywords", []),
                "evidence_retrieved": selected_chunk_ids,
                "final_finding": None,
                "finding_id": None,
                "qc_status": "PENDING",
                "evidence_limitation": None
            })

    if sse_callback:
        sse_callback({
            "agent": "financial_research",
            "status": "retrieval_complete",
            "retrieval_trace": retrieval_trace,
            "coverage_ledger": coverage_ledger
        })

    return {
        "financial_evidence": accumulated_evidence,
        "retrieval_trace": retrieval_trace,
        "coverage_ledger": coverage_ledger
    }
