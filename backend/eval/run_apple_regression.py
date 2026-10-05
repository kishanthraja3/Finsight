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

def run_apple_e2e():
    run_id = "Apple_Regression_Live"
    query = "Evaluate Apple's Services revenue growth, gross margin impact, and Item 1A regulatory risks in European markets."

    print("=" * 80)
    print(f"RUNNING TARGETED REGRESSION TEST: {run_id}")
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
        "max_retries": 1,
        "human_decisions": {},
        "affected_categories": [],
        "affected_tasks": [],
        "final_report": "",
        "run_status": "planning"
    }

    t0 = time.time()

    # Stage 1: Planner
    print("\n[Stage 1] Planner: Decomposing query...", flush=True)
    plan_out = plan_research(state)
    state.update(plan_out)
    print(f"Tasks planned ({len(state['tasks'])}):", flush=True)
    for t in state["tasks"]:
        print(f"  - [{t['id']}] {t.get('company')} ({t.get('category')}): {t.get('sub_question')}")

    # Stage 2: Financial Research
    print("\n[Stage 2] Financial Research: SEC ChromaDB retrieval...", flush=True)
    fin_out = execute_financial_research(state)
    state.update(fin_out)
    print(f"Retrieved {len(state['financial_evidence'])} SEC chunks across tasks.", flush=True)

    # Stage 3 & 4: Conditional Market / News checks
    print("\n[Stage 3 & 4] Conditional Market & News Checks...", flush=True)
    mkt_out = market_data_node(state)
    state.update(mkt_out)
    news_out = news_research_node(state)
    state.update(news_out)
    print(f"Market data fetched: {bool(state['market_data'])} | News fetched: {len(state['news_evidence'])}", flush=True)

    # Stage 5: Risk Analysis
    print("\n[Stage 5] Risk Analysis...", flush=True)
    risk_out = execute_risk_analysis(state)
    state.update(risk_out)
    print(f"Validated risk findings generated: {len(state['risk_findings'])}", flush=True)

    # Stage 6: Synthesis with Verifier
    print("\n[Stage 6] Synthesis with Verifier...", flush=True)
    synth_out = execute_synthesis(state)
    state.update(synth_out)
    print(f"Synthesized findings count: {len(state['findings'])}", flush=True)
    for f in state["findings"]:
        print(f"  [{f['id']}] {f.get('statement')[:75]}... | NumVerified: {f.get('numerically_verified')} | Citations: {f.get('evidence_chunk_ids')}")

    # Stage 7: Critic QC
    print("\n[Stage 7] Critic Quality Control...", flush=True)
    crit_out = execute_critic(state)
    state.update(crit_out)
    print(f"Critic QC passed: {state['critic_result']['passed']} | Issues: {state['critic_result']['issues']}", flush=True)

    # Stage 8: Approve and Compile Final Report
    print("\n[Stage 8] Final Report Compilation...", flush=True)
    for f in state["findings"]:
        f["status"] = "approved"

    report = compile_final_report(state, state["findings"])
    state["final_report"] = report

    elapsed = time.time() - t0
    metrics = telemetry_tracker.get_run_metrics(run_id)

    print("\n" + "=" * 80)
    print("TELEMETRY METRICS:")
    print(f"  Elapsed Time: {elapsed:.2f}s")
    print(f"  Logical Calls: {metrics.get('logical_calls')}")
    print(f"  HTTP Requests: {metrics.get('http_requests')}")
    print(f"  Prompt Tokens: {metrics.get('prompt_tokens')}")
    print(f"  Completion Tokens: {metrics.get('completion_tokens')}")
    print(f"  Total Tokens: {metrics.get('total_tokens')}")
    print(f"  Active Model: {metrics.get('active_model')}")
    print(f"  Fallback Active: {metrics.get('fallback_active')}")
    print(f"  Models Used: {metrics.get('models_used')}")
    print("=" * 80)

    print("\nCOVERAGE LEDGER:")
    for entry in state.get("coverage_ledger", []):
        print(f"  [{entry['task_id']}] {entry['company']} | QC: {entry['qc_status']} | Final: {entry.get('final_finding')[:65] if entry.get('final_finding') else 'None'} | Lim: {entry.get('evidence_limitation')}")

    print("\nFINAL REPORT EXCERPT:")
    print("-" * 80)
    print(report[:800] + ("..." if len(report) > 800 else ""))
    print("-" * 80)

    return state

if __name__ == "__main__":
    run_apple_e2e()
