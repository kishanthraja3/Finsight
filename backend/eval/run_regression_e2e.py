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
from backend.agents.financial_research import execute_financial_research
from backend.graph.build_graph import market_data_node, news_research_node, compile_final_report
from backend.agents.risk import execute_risk_analysis
from backend.agents.synthesis import execute_synthesis
from backend.agents.critic import execute_critic
from backend.agents.replanner import execute_replanner
from backend.agents.llm_client import telemetry_tracker

def execute_e2e_query(run_id: str, query: str):
    print("=" * 80)
    print(f"RUNNING E2E REGRESSION TEST: {run_id}")
    print(f"Query: {query}")
    print("=" * 80, flush=True)

    state = {
        "query": query,
        "run_id": run_id,
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
        "max_retries": 2,
        "human_decisions": {},
        "affected_categories": [],
        "affected_tasks": [],
        "final_report": "",
        "run_status": "planning"
    }

    start_time = time.time()

    # 1. Planner
    print("\n[Stage 1] Planner: Decomposing query...", flush=True)
    plan_out = plan_research(state)
    state.update(plan_out)
    print(f"Tasks planned ({len(state['tasks'])}):", flush=True)
    for t in state["tasks"]:
        print(f"  - [{t['id']}] {t.get('company')} ({t.get('category')}): {t.get('sub_question')}")

    # 2. Financial Research (SEC RAG)
    print("\n[Stage 2] Financial Research: SEC ChromaDB retrieval...", flush=True)
    fin_out = execute_financial_research(state)
    state.update(fin_out)
    print(f"Retrieved {len(state['financial_evidence'])} SEC chunks across tasks.", flush=True)

    # 3. Market Data (Conditional)
    print("\n[Stage 3] Conditional Market Data check...", flush=True)
    mkt_out = market_data_node(state)
    state.update(mkt_out)
    print(f"Market data fetched: {bool(state['market_data'])}", flush=True)

    # 4. News Research (Conditional)
    print("\n[Stage 4] Conditional News Research check...", flush=True)
    news_out = news_research_node(state)
    state.update(news_out)
    print(f"News evidence fetched count: {len(state['news_evidence'])}", flush=True)

    # 5. Risk Analysis
    print("\n[Stage 5] Risk Analysis...", flush=True)
    risk_out = execute_risk_analysis(state)
    state.update(risk_out)
    print(f"Validated risk findings generated: {len(state['risk_findings'])}", flush=True)

    # 6. Synthesis with Verifier
    print("\n[Stage 6] Synthesis with Verifier...", flush=True)
    synth_out = execute_synthesis(state)
    state.update(synth_out)
    print(f"Synthesized findings count: {len(state['findings'])}", flush=True)
    for f in state["findings"]:
        print(f"  [{f['id']}] {f.get('statement')[:80]}... | NumVerified: {f.get('numerically_verified')} | Citations: {f.get('evidence_chunk_ids')}")

    # 7. Critic QC Review
    print("\n[Stage 7] Critic Quality Control...", flush=True)
    crit_out = execute_critic(state)
    state.update(crit_out)
    print(f"Critic QC passed: {state['critic_result']['passed']} | Issues: {state['critic_result']['issues']}", flush=True)

    # If QC failed and retries available, run targeted replan
    while not state["critic_result"]["passed"] and state["retry_count"] < state["max_retries"]:
        print(f"\n[Stage 7.1] Critic failed coverage. Targeted Replanner (Attempt {state['retry_count']}/{state['max_retries']})...", flush=True)
        replan_out = execute_replanner(state)
        state.update(replan_out)

        fin_out = execute_financial_research(state)
        state.update(fin_out)

        synth_out = execute_synthesis(state)
        state.update(synth_out)

        crit_out = execute_critic(state)
        state.update(crit_out)
        print(f"Retry Critic QC passed: {state['critic_result']['passed']}", flush=True)

    # 8. Human Review Simulation & Compile Final Report
    print("\n[Stage 8] Final Report Compilation...", flush=True)
    for f in state["findings"]:
        f["status"] = "approved"

    report = compile_final_report(state, state["findings"])
    state["final_report"] = report

    elapsed = time.time() - start_time
    metrics = telemetry_tracker.get_run_metrics(run_id)

    print("\n" + "=" * 80)
    print(f"RUN METRICS FOR {run_id}:")
    print(f"  Elapsed Time: {elapsed:.2f}s")
    print(f"  Logical LLM Calls: {metrics.get('logical_calls')}")
    print(f"  HTTP Requests: {metrics.get('http_requests')}")
    print(f"  Prompt Tokens: {metrics.get('prompt_tokens')}")
    print(f"  Completion Tokens: {metrics.get('completion_tokens')}")
    print(f"  Total Tokens: {metrics.get('total_tokens')}")
    print(f"  Retries: {metrics.get('retries')}")
    print(f"  Rate Limit 429 Events: {metrics.get('rate_limit_events')}")
    print(f"  Calls by Component: {metrics.get('calls_by_component')}")
    print(f"  Models Used: {metrics.get('models_used')}")
    print("=" * 80, flush=True)

    return state, metrics

if __name__ == "__main__":
    results = {}

    # T1 - Apple
    s1, m1 = execute_e2e_query(
        "T1_Apple",
        "Evaluate Apple's Services revenue growth, gross margin impact, and Item 1A regulatory risks in European markets."
    )
    results["T1"] = {"state": s1, "metrics": m1}

    print("\nWaiting 10s before T2 to refresh per-minute OTPM quota...", flush=True)
    time.sleep(10)

    # T2 - NVIDIA
    s2, m2 = execute_e2e_query(
        "T2_NVIDIA",
        "Evaluate NVIDIA's Data Center revenue trajectory, gross margin trend, and export-control risks to China."
    )
    results["T2"] = {"state": s2, "metrics": m2}

    print("\nWaiting 10s before T3 to refresh per-minute OTPM quota...", flush=True)
    time.sleep(10)

    # T3 - Microsoft
    s3, m3 = execute_e2e_query(
        "T3_Microsoft",
        "Evaluate Microsoft's Azure growth, operating margin trend, and European regulatory risks."
    )
    results["T3"] = {"state": s3, "metrics": m3}

    print("\n" + "#" * 80)
    print("ALL THREE REGRESSION TESTS COMPLETED SUCCESSFULLY!")
    print("#" * 80)

    # Save summary json for documentation
    summary_path = PROJECT_ROOT / "docs" / "regression_results.json"
    clean_summary = {}
    for tid, data in results.items():
        st = data["state"]
        met = data["metrics"]
        clean_summary[tid] = {
            "query": st.get("query"),
            "metrics": met,
            "tasks_count": len(st.get("tasks", [])),
            "findings_count": len(st.get("findings", [])),
            "qc_passed": st.get("critic_result", {}).get("passed"),
            "report_excerpt": st.get("final_report", "")[:1000]
        }
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(clean_summary, f, indent=2)
    print(f"Summary saved to {summary_path}")
