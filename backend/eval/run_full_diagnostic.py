import sys
import os
import json
import time
from pathlib import Path

# Ensure UTF-8 output on Windows
sys.stdout.reconfigure(encoding='utf-8')

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.config import settings
from backend.agents.planner import plan_research
from backend.agents.financial_research import execute_financial_research, get_resources
from backend.agents.risk import execute_risk_analysis
from backend.agents.synthesis import execute_synthesis
from backend.agents.critic import execute_critic

query = "Evaluate Apple's Services revenue growth, gross margin impact, and Item 1A regulatory risks in European markets."

print("=" * 80, flush=True)
print("DIAGNOSTIC PIPELINE RUN", flush=True)
print(f"Query: {query}", flush=True)
print("=" * 80, flush=True)

# Pre-load embedding model so it doesn't block mid-run
print("Pre-loading SentenceTransformer and ChromaDB...", flush=True)
t_load = time.time()
get_resources()
print(f"Resources loaded in {time.time() - t_load:.2f}s", flush=True)

# Initial State
state = {
    "run_id": f"diag_apple_{int(time.time())}",
    "query": query,
    "companies": ["Apple"],
    "tasks": [],
    "financial_evidence": [],
    "market_data": {},
    "news_evidence": [],
    "risk_findings": [],
    "findings": [],
    "coverage_ledger": [],
    "retrieval_trace": {},
    "critic_result": {},
    "synthesis_draft": "",
    "final_report": "",
    "retry_count": 0,
    "max_retries": 1,
}

# -------------------------------------------------------------
# STEP 1: PLANNER
# -------------------------------------------------------------
print("\n" + "#" * 80, flush=True)
print("STEP 1: PLANNER EXECUTION", flush=True)
print("#" * 80, flush=True)

t0 = time.time()
planner_res = plan_research(state)
state.update(planner_res)
print(f"Planner finished in {time.time() - t0:.2f}s", flush=True)

print(f"\nCompanies Detected: {state.get('companies')}", flush=True)
print(f"Total Tasks Planned: {len(state.get('tasks', []))}", flush=True)
for t in state.get("tasks", []):
    print(f"\n  - Task ID: [{t.get('id')}]", flush=True)
    print(f"    Agent: {t.get('agent')} | Category: {t.get('category')}", flush=True)
    print(f"    Clause: '{t.get('clause')}'", flush=True)
    print(f"    Sub-question: '{t.get('sub_question')}'", flush=True)
    print(f"    Required Doc Types: {t.get('required_doc_types')}", flush=True)
    print(f"    Required Sections: {t.get('required_sections')}", flush=True)
    print(f"    Required Evidence Type: {t.get('required_evidence_type')}", flush=True)
    print(f"    Semantic Keywords: {t.get('semantic_keywords')}", flush=True)

# -------------------------------------------------------------
# STEP 2: RETRIEVAL BOUNDARY DIAGNOSTIC LOGGING
# -------------------------------------------------------------
print("\n" + "#" * 80, flush=True)
print("STEP 2: RETRIEVAL BOUNDARY DIAGNOSTIC LOGGING", flush=True)
print("#" * 80, flush=True)

t0 = time.time()
fin_res = execute_financial_research(state)
state.update(fin_res)
print(f"Financial Research finished in {time.time() - t0:.2f}s", flush=True)

retrieval_trace = state.get("retrieval_trace", {})
print(f"\nRetrieval Boundary Log (Total Tasks Retrieved: {len(retrieval_trace)}):", flush=True)
for tid, trace in retrieval_trace.items():
    task_desc = trace.get("sub_question")
    clause = trace.get("clause")
    query_used = trace.get("query_used")
    candidates = trace.get("retrieved_chunk_ids", [])
    selected = trace.get("selected_chunks", [])
    
    print("\n" + "-" * 70, flush=True)
    print(f"RETRIEVAL CALL FOR TASK [{tid}]:", flush=True)
    print(f"  * Original Query: {query}", flush=True)
    print(f"  * Task ID: {tid}", flush=True)
    print(f"  * Task Description: {task_desc}", flush=True)
    print(f"  * Clause: {clause}", flush=True)
    print(f"  * Generated Retrieval Query: {query_used}", flush=True)
    print(f"  * Metadata Filter: {{'company': 'Apple'}}", flush=True)
    print(f"  * Number of candidate chunks returned: {len(candidates)}", flush=True)
    print(f"  * Number of chunks selected for task: {len(selected)}", flush=True)
    print(f"  * Selected Chunk IDs: {selected}", flush=True)

print("\n" + "=" * 70, flush=True)
print("ALL EVIDENCE CHUNKS ACCUMULATED FOR SYNTHESIS:", flush=True)
print("=" * 70, flush=True)
for idx, chunk in enumerate(state.get("financial_evidence", []), 1):
    meta = chunk.get("metadata", {})
    cid = chunk.get("chunk_id")
    print(f"\nChunk #{idx} Details:", flush=True)
    print(f"  * Chunk ID: {cid}", flush=True)
    print(f"  * Task ID: {chunk.get('task_id')}", flush=True)
    print(f"  * Company: {meta.get('company')}", flush=True)
    print(f"  * Doc Type: {meta.get('doc_type')}", flush=True)
    print(f"  * Fiscal Period: {meta.get('fiscal_period')}", flush=True)
    print(f"  * Section: {meta.get('section')}", flush=True)
    print(f"  * Source Filename: {meta.get('source_file')}", flush=True)
    print(f"  * Similarity / Distance Score: {chunk.get('score')}", flush=True)
    text_sample = chunk.get("text", "")[:800].replace("\n", " ").strip()
    print(f"  * Retrieved Text (first 800 chars):\n    {text_sample}", flush=True)

# -------------------------------------------------------------
# STEP 3: RISK ANALYSIS
# -------------------------------------------------------------
print("\n" + "#" * 80, flush=True)
print("STEP 3: RISK ANALYSIS EXECUTION", flush=True)
print("#" * 80, flush=True)

t0 = time.time()
risk_res = execute_risk_analysis(state)
state.update(risk_res)
print(f"Risk Analysis finished in {time.time() - t0:.2f}s", flush=True)
print(f"Risk Findings Count: {len(state.get('risk_findings', []))}", flush=True)
for rf in state.get("risk_findings", []):
    print(f"  - [{rf.get('id')}] Statement: {rf.get('statement')}", flush=True)
    print(f"    Confidence: {rf.get('confidence')} | Cited Chunk IDs: {rf.get('evidence_chunk_ids')}", flush=True)

# -------------------------------------------------------------
# STEP 4: EVIDENCE ACTUALLY PASSED INTO SYNTHESIS
# -------------------------------------------------------------
print("\n" + "#" * 80, flush=True)
print("STEP 4: EVIDENCE PASSED INTO SYNTHESIS", flush=True)
print("#" * 80, flush=True)

fin_evidence_passed = state.get("financial_evidence", [])
print(f"Total SEC chunks passed into Synthesis prompt: {len(fin_evidence_passed)}", flush=True)
print(f"Passed Chunk IDs:", [c['chunk_id'] for c in fin_evidence_passed], flush=True)

# -------------------------------------------------------------
# STEP 5: SYNTHESIS & VERIFIER
# -------------------------------------------------------------
print("\n" + "#" * 80, flush=True)
print("STEP 5: SYNTHESIS & VERIFIER EXECUTION", flush=True)
print("#" * 80, flush=True)

t0 = time.time()
synth_res = execute_synthesis(state)
state.update(synth_res)
print(f"Synthesis finished in {time.time() - t0:.2f}s", flush=True)

print(f"\nFinal Findings Generated ({len(state.get('findings', []))} total):", flush=True)
for f in state.get("findings", []):
    print(f"\nFinding [{f.get('id')}]:", flush=True)
    print(f"  Task ID: {f.get('task_id')}", flush=True)
    print(f"  Category: {f.get('category')}", flush=True)
    print(f"  Statement: {f.get('statement')}", flush=True)
    print(f"  Confidence: {f.get('confidence')}", flush=True)
    print(f"  Numerically Verified: {f.get('numerically_verified')}", flush=True)
    print(f"  Cited Figures: {f.get('cited_figures')}", flush=True)
    print(f"  Temporal Labels: {f.get('temporal_labels')}", flush=True)
    print(f"  Cited Chunk IDs: {f.get('evidence_chunk_ids')}", flush=True)

# Compare cited chunk IDs with retrieved evidence
all_retrieved_ids = {c["chunk_id"] for c in state.get("financial_evidence", [])}
all_cited_ids = {cid for f in state.get("findings", []) for cid in f.get("evidence_chunk_ids", [])}
print("\n" + "=" * 70, flush=True)
print("CHUNK ID COMPARISON (CITED vs RETRIEVED):", flush=True)
print("=" * 70, flush=True)
print(f"Total Unique Retrieved Chunk IDs: {len(all_retrieved_ids)}", flush=True)
print(f"Total Unique Cited Chunk IDs: {len(all_cited_ids)}", flush=True)
print(f"Cited Chunks That Were Retrieved: {all_cited_ids.intersection(all_retrieved_ids)}", flush=True)
print(f"Cited Chunks NOT in Retrieved Evidence (Hallucinated IDs): {all_cited_ids - all_retrieved_ids}", flush=True)
print(f"Retrieved Chunks That Were NOT Cited (Unused): {all_retrieved_ids - all_cited_ids}", flush=True)

# -------------------------------------------------------------
# STEP 6: CRITIC & QC
# -------------------------------------------------------------
print("\n" + "#" * 80, flush=True)
print("STEP 6: CRITIC & QC EXECUTION", flush=True)
print("#" * 80, flush=True)

t0 = time.time()
critic_res = execute_critic(state)
state.update(critic_res)
print(f"Critic finished in {time.time() - t0:.2f}s", flush=True)

print(f"\nCritic Passed: {state.get('critic_result', {}).get('passed')}", flush=True)
print(f"Critic Issues: {state.get('critic_result', {}).get('issues')}", flush=True)

print("\nCoverage Ledger Status:", flush=True)
for entry in state.get("coverage_ledger", []):
    print(f"\n  Task [{entry.get('task_id')}]: {entry.get('task')}", flush=True)
    print(f"    QC Status: {entry.get('qc_status')}", flush=True)
    print(f"    Evidence Retrieved: {entry.get('evidence_retrieved')}", flush=True)
    print(f"    Final Finding: {entry.get('final_finding')}", flush=True)
    print(f"    Evidence Limitation: {entry.get('evidence_limitation')}", flush=True)

print("\nSynthesis Draft Preview (First 1000 characters):", flush=True)
print(state.get("synthesis_draft", "")[:1000], flush=True)

# Write output to JSON for exhaustive analysis
out_file = PROJECT_ROOT / "diagnostic_apple_run_results.json"
with open(out_file, "w", encoding="utf-8") as f:
    json.dump({
        "query": query,
        "tasks": state.get("tasks"),
        "financial_evidence": [
            {
                "chunk_id": c.get("chunk_id"),
                "task_id": c.get("task_id"),
                "metadata": c.get("metadata"),
                "score": c.get("score"),
                "text": c.get("text")[:800]
            }
            for c in state.get("financial_evidence", [])
        ],
        "risk_findings": state.get("risk_findings"),
        "findings": state.get("findings"),
        "coverage_ledger": state.get("coverage_ledger"),
        "retrieval_trace": state.get("retrieval_trace"),
        "critic_result": state.get("critic_result"),
        "synthesis_draft": state.get("synthesis_draft")
    }, f, indent=2, ensure_ascii=False)

print(f"\nDiagnostic run successfully saved to {out_file}", flush=True)
