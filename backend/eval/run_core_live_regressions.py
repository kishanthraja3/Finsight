import sys
import json
import time
from pathlib import Path

try:
    sys.stdout.reconfigure(line_buffering=True)
except Exception:
    pass

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.config import settings
from backend.agents.planner import plan_research
from backend.graph.build_graph import (
    financial_research_node,
    market_data_node,
    news_research_node,
    risk_node,
    synthesis_node,
    compile_final_report
)
from backend.agents.llm_client import telemetry_tracker

def run_live_regression(test_name: str, query: str):
    print("=" * 80)
    print(f"LIVE REGRESSION TEST: {test_name}")
    print(f"Query: {query}")
    print("=" * 80, flush=True)

    state = {
        "query": query,
        "run_id": test_name.lower(),
        "companies": [],
        "tasks": [],
        "coverage_ledger": [],
        "retrieval_trace": {},
        "financial_evidence": [],
        "market_data": {},
        "news_evidence": [],
        "risk_findings": [],
        "findings": [],
        "synthesis_draft": "",
        "critic_result": {"passed": False, "issues": []},
        "retry_count": 0,
        "max_retries": 1,
        "human_decisions": {},
        "affected_categories": [],
        "affected_tasks": [],
        "final_report": "",
        "run_status": "planning"
    }

    start_time = time.time()

    # 1. Planner & Intent Classification
    print("\n[Step 1] Planning & Intent Classification...", flush=True)
    plan_out = plan_research(state)
    state.update(plan_out)

    intent = state.get("intent_classification", {})
    print(f"Intent Classification:")
    print(f"  - market_data_required: {intent.get('market_data_required')}")
    print(f"  - news_required: {intent.get('news_required')}")
    print(f"  - sec_retrieval_required: {intent.get('sec_retrieval_required')}")
    print(f"Tasks planned ({len(state['tasks'])}):")
    for t in state["tasks"]:
        print(f"  * [{t['id']}] {t.get('company')} ({t.get('category')}, agent={t.get('agent')}): {t.get('sub_question')}")

    # 2. Financial Research (SEC RAG) - Conditional
    print("\n[Step 2] Executing Financial Research Node (SEC Filings)...", flush=True)
    fin_out = financial_research_node(state)
    state.update(fin_out)
    sec_count = len(state.get("financial_evidence", []))
    print(f"  -> SEC Retrieval executed: {'YES' if sec_count > 0 else 'BYPASSED / 0 chunks'} (chunks retrieved: {sec_count})")

    # 3. Market Data - Conditional
    print("\n[Step 3] Executing Market Data Node (Alpha Vantage)...", flush=True)
    mkt_out = market_data_node(state)
    state.update(mkt_out)
    mkt_data = state.get("market_data", {})
    print(f"  -> Market Data executed: {'YES' if bool(mkt_data) else 'BYPASSED'}")
    for comp, m in mkt_data.items():
        print(f"     {comp}: Price=${m.get('price')} (change: {m.get('change_percent')}), P/E={m.get('pe_ratio')}, Source={m.get('source')}")

    # 4. News Research - Conditional
    print("\n[Step 4] Executing News Research Node...", flush=True)
    news_out = news_research_node(state)
    state.update(news_out)
    news_items = state.get("news_evidence", [])
    print(f"  -> News Retrieval executed: {'YES' if len(news_items) > 0 else 'BYPASSED'} (articles retrieved: {len(news_items)})")
    for art in news_items[:2]:
        print(f"     * {art.get('company')}: '{art.get('title')[:60]}...' (Score={art.get('sentiment_score')}, Source={art.get('source')})")

    # 5. Risk Analysis - Conditional
    print("\n[Step 5] Executing Risk Analysis Node...", flush=True)
    risk_out = risk_node(state)
    state.update(risk_out)
    print(f"  -> Risk Analysis executed: {len(state.get('risk_findings', []))} risk findings")

    # 6. Synthesis Node
    print("\n[Step 6] Executing Synthesis Node...", flush=True)
    syn_out = synthesis_node(state)
    state.update(syn_out)
    findings = state.get("findings", [])
    print(f"  -> Synthesized Findings ({len(findings)}):")
    for f in findings:
        print(f"     [{f['id']}] ({f.get('category')}): {f.get('statement')[:100]}...")
        print(f"          Status: {f.get('validation_status')} | Figures: {f.get('figure_status')} | Citation: {f.get('citation_status')} | ChunkIDs: {f.get('evidence_chunk_ids')}")

    # 7. Coverage Ledger & QC Status
    print("\n[Step 7] Task-Level Quality Control & Coverage Ledger:", flush=True)
    for entry in state.get("coverage_ledger", []):
        print(f"  * Task: {entry.get('task_id')} ({entry.get('company')}): QC={entry.get('qc_status')}")
        if entry.get("evidence_limitation"):
            print(f"    Limitation: {entry.get('evidence_limitation')}")
        if entry.get("cited_chunks"):
            print(f"    Cited Chunks: {entry.get('cited_chunks')}")

    # 8. Final Report Assembly
    final_report = compile_final_report(state, state.get("findings", []))
    state["final_report"] = final_report

    elapsed = round(time.time() - start_time, 2)
    metrics = telemetry_tracker.get_run_metrics(test_name.lower())

    print("\n[Summary Metrics]")
    print(f"  Total Duration: {elapsed}s")
    print(f"  LLM Calls: {metrics.get('total_llm_calls')}")
    print(f"  Tokens: Prompt={metrics.get('total_prompt_tokens')}, Completion={metrics.get('total_completion_tokens')}")
    print(f"  Models Used: {metrics.get('models_used')}")
    print("=" * 80 + "\n", flush=True)

    return state, metrics

if __name__ == "__main__":
    results = {}

    # Regression 1: Apple Financial Performance (SEC required)
    s1, m1 = run_live_regression(
        "LIVE_REG_1_Apple_Financial",
        "Evaluate Apple's Services revenue growth trajectory and gross margin trends over the latest three fiscal years (FY2023–FY2025)."
    )
    results["Apple_Financial"] = {"state": s1, "metrics": m1}

    time.sleep(2)

    # Regression 2: NVIDIA Stock Price Performance (Market Data required)
    s2, m2 = run_live_regression(
        "LIVE_REG_2_NVIDIA_Stock_Price",
        "Analyse current Nvidia price performance."
    )
    results["NVIDIA_Stock_Price"] = {"state": s2, "metrics": m2}

    time.sleep(2)

    # Regression 3: Microsoft Stock Price Performance + Risks (Market Data + News + SEC required)
    s3, m3 = run_live_regression(
        "LIVE_REG_3_Microsoft_Price_and_Risks",
        "Analyse current Microsoft price performance and risks involved."
    )
    results["Microsoft_Price_and_Risks"] = {"state": s3, "metrics": m3}

    print("\n" + "#" * 80)
    print("ALL 3 LIVE REGRESSIONS FINISHED SUCCESSFULLY!")
    print("#" * 80)
