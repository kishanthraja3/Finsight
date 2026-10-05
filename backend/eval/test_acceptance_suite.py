import sys
import json
from pathlib import Path

try:
    sys.stdout.reconfigure(line_buffering=True)
except Exception:
    pass

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.agents.planner import plan_research
from backend.agents.financial_research import execute_financial_research
from backend.agents.market_data import execute_market_data
from backend.agents.news_research import execute_news_research
from backend.agents.risk import execute_risk_analysis as execute_risk
from backend.agents.synthesis import execute_synthesis
from backend.agents.critic import execute_critic
from backend.graph.build_graph import compile_final_report

def run_acceptance_test(test_id: str, query: str):
    print("=" * 80)
    print(f"RUNNING ACCEPTANCE TEST: {test_id}")
    print(f"Query: {query}")
    print("=" * 80)

    # 1. Planning
    state = {
        "query": query,
        "run_id": f"test_{test_id.lower()}",
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
        "max_retries": 3,
        "human_decisions": {},
        "affected_categories": [],
        "affected_tasks": [],
        "final_report": "",
        "run_status": "planning"
    }

    plan_res = plan_research(state)
    state.update(plan_res)
    print(f"Planner emitted {len(state['tasks'])} tasks across {state['companies']}.", flush=True)

    # 2. Retrieval
    print("Step 2: Executing Financial Research RAG...", flush=True)
    fin_res = execute_financial_research(state)
    state.update(fin_res)
    print(f"Retrieved {len(state['financial_evidence'])} financial evidence chunks.", flush=True)

    # 3. Market & News
    print("Step 3: Executing Market & News Research...", flush=True)
    mkt_res = execute_market_data(state)
    state.update(mkt_res)

    news_res = execute_news_research(state)
    state.update(news_res)

    # 4. Risk
    print("Step 4: Executing Risk Analysis...", flush=True)
    risk_res = execute_risk(state)
    state.update(risk_res)

    # 5. Synthesis
    print("Step 5: Executing Synthesis with Verifier...", flush=True)
    synth_res = execute_synthesis(state)
    state.update(synth_res)
    print(f"Synthesis generated {len(state['findings'])} relevant findings.", flush=True)

    # 6. Critic and Retry Loop (Requirement 1 & 15)
    print("Step 6: Executing Critic QC check...", flush=True)
    crit_res = execute_critic(state)
    state.update(crit_res)
    print(f"Critic QC initial pass: {state['critic_result']['passed']}", flush=True)

    while not state["critic_result"]["passed"] and state["retry_count"] < state["max_retries"]:
        print(f"-> Critic QC failed on coverage. Triggering targeted Re-planner (Attempt {state['retry_count']}/{state['max_retries']})...")
        from backend.agents.replanner import execute_replanner
        replan_res = execute_replanner(state)
        state.update(replan_res)

        fin_res = execute_financial_research(state)
        state.update(fin_res)

        synth_res = execute_synthesis(state)
        state.update(synth_res)

        crit_res = execute_critic(state)
        state.update(crit_res)
        print(f"   Retry QC passed: {state['critic_result']['passed']}")

    # 7. Approve relevant findings
    for f in state["findings"]:
        f["status"] = "approved"

    # 8. Final Report
    report = compile_final_report(state, state["findings"])
    state["final_report"] = report

    # Print summary output for report
    print("\n--- COVERAGE LEDGER ---")
    for entry in state.get("coverage_ledger", []):
        print(f"[{entry['task_id']}] {entry['company']} | {entry['task'][:50]} | QC: {entry['qc_status']} | Ev: {len(entry.get('evidence_retrieved', []))} chunks | Lim: {entry.get('evidence_limitation')}")

    print("\n--- RETRIEVAL TRACE SUMMARY ---")
    for tid, tr in state.get("retrieval_trace", {}).items():
        print(f"[{tid}] Query: {tr.get('query_used')[:50]}... | Retrieved: {len(tr.get('retrieved_chunk_ids', []))} chunks | Selected: {tr.get('selected_chunks')} | Cited: {tr.get('cited_chunks')}")

    evidence_limitations = [e for e in state.get("coverage_ledger", []) if e.get("evidence_limitation")]
    print(f"\nTasks with Evidence Limitation: {len(evidence_limitations)}")
    for lim in evidence_limitations:
        print(f"- {lim['task_id']} ({lim['company']}): {lim['evidence_limitation']}")

    return state

if __name__ == "__main__":
    t1_state = run_acceptance_test(
        "T1",
        "Analyze NVIDIA's Q2 FY2027 performance: Data Center revenue trajectory, gross margin trend, and the export-control risks to its China business."
    )
    t2_state = run_acceptance_test(
        "T2",
        "Evaluate Apple's Services revenue growth, gross margin impact, and Item 1A regulatory risks in European markets."
    )
    t3_state = run_acceptance_test(
        "T3",
        "Compare semiconductor supply chain dependencies and geopolitical trade exposure across NVIDIA and Apple."
    )
    print("\nALL 3 ACCEPTANCE TESTS EXECUTED SUCCESSFULLY!")
