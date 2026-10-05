import sys
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from typing import Dict, Any, List
from backend.config import settings
from backend.agents.llm_client import call_gemini, extract_json_from_llm
from backend.graph.state import FinSightState

REPLANNER_SYSTEM_PROMPT = """You are the Senior Research Operations Architect.
When a finding is rejected by a human reviewer, has evidence requested, or fails automated quality critique, your job is to isolate the EXACT categories and tasks affected so downstream execution is targeted, NOT a wasteful full pipeline restart.

Valid Categories:
- "financial_performance" (affects financial_research)
- "market_data" (affects market_data)
- "news" (affects news_research)
- "risk" (affects risk and financial_research)

Analyze the rejection reasons, evidence request notes, and critic issues below and return the minimal set of affected categories and task IDs that must be re-run.

Output JSON ONLY:
{
  "affected_categories": ["risk", "financial_performance"],
  "affected_tasks": ["task_001"],
  "rationale": "Explanation of why these specific tasks need re-analysis"
}
"""

def execute_replanner(state: FinSightState, sse_callback=None) -> Dict[str, Any]:
    """
    Re-planner: identifies specifically affected tasks and categories from human decisions (rejections or evidence requests) or critic issues.
    Enables surgical targeted re-execution rather than full graph restart.
    """
    if sse_callback:
        sse_callback({
            "agent": "replanner",
            "status": "diagnosing_rejections"
        })

    findings = state.get("findings", [])
    tasks = state.get("tasks", [])
    critic_result = state.get("critic_result", {})
    human_decisions = state.get("human_decisions", {})
    existing_affected_tasks = list(state.get("affected_tasks", []))
    existing_affected_categories = list(state.get("affected_categories", []))

    rejected_findings = []
    evidence_requested_findings = []

    for f in findings:
        fid = f.get("id")
        decision = human_decisions.get(fid, {})
        status = decision.get("status") or f.get("status")
        
        if status in ["rejected", "reject"]:
            reason = decision.get("reason") or f.get("rejection_reason") or "Rejected by human reviewer."
            rejected_findings.append({
                "id": fid,
                "task_id": f.get("task_id"),
                "category": f.get("category"),
                "statement": f.get("statement"),
                "reason": reason
            })
        elif status == "request_evidence":
            note = decision.get("note") or f.get("evidence_request_note") or "Reviewer requested additional evidence."
            evidence_requested_findings.append({
                "id": fid,
                "task_id": f.get("task_id"),
                "category": f.get("category"),
                "statement": f.get("statement"),
                "note": note
            })

    critic_issues = critic_result.get("issues", [])

    prompt = f"""Critic Issues:
{chr(10).join(['- ' + str(i) for i in critic_issues]) if critic_issues else 'None'}

Human Rejected Findings:
{chr(10).join([f"- [{rf['id']}] ({rf['category']}): '{rf['statement']}' -> Reason: {rf['reason']}" for rf in rejected_findings]) if rejected_findings else 'None'}

Evidence Requests from Reviewer:
{chr(10).join([f"- [{ef['id']}] ({ef['category']}): '{ef['statement']}' -> Note: {ef['note']}" for ef in evidence_requested_findings]) if evidence_requested_findings else 'None'}

Available Tasks:
{chr(10).join([f"- {t.get('id')}: {t.get('sub_question')}" for t in tasks])}

Determine the minimal affected categories and task IDs to re-execute.
"""

    affected_cats: List[str] = list(existing_affected_categories)
    affected_ts: List[str] = list(existing_affected_tasks)

    # 1. Deterministic task and category resolution from human rejections and evidence requests
    for rf in rejected_findings + evidence_requested_findings:
        cat = rf.get("category")
        tid = rf.get("task_id")
        if cat and cat not in affected_cats:
            affected_cats.append(cat)
        if cat == "risk" and "financial_performance" not in affected_cats:
            # Regulatory risk requires SEC filing retrieval
            affected_cats.append("financial_performance")
        if tid and tid not in affected_ts:
            affected_ts.append(tid)

    # 2. Map affected tasks directly from critic state if available
    for stid in state.get("affected_tasks", []):
        if stid not in affected_ts:
            affected_ts.append(stid)
        matching_task = next((t for t in tasks if t.get("id") == stid), None)
        if matching_task:
            cat = matching_task.get("category", "financial_performance")
            if cat not in affected_cats:
                affected_cats.append(cat)
            if cat == "risk" and "financial_performance" not in affected_cats:
                affected_cats.append("financial_performance")

    # 3. Only invoke LLM when next action cannot be determined deterministically
    if not affected_ts and critic_issues:
        is_complex = (
            len(state.get("companies", [])) > 1
            or len(critic_issues) > 2
            or len(tasks) > 3
        )
        selected_model = settings.MODEL_REPLANNER_COMPLEX if is_complex else settings.MODEL_REPLANNER_FAST

        try:
            run_id = state.get("run_id")
            raw_response = call_gemini(
                prompt,
                system_instruction=REPLANNER_SYSTEM_PROMPT,
                model=selected_model,
                run_id=run_id,
                component="replanner"
            )
            parsed = extract_json_from_llm(raw_response, run_id=run_id)
            llm_cats = parsed.get("affected_categories", [])
            llm_tasks = parsed.get("affected_tasks", [])
            affected_cats.extend(llm_cats)
            affected_ts.extend(llm_tasks)
        except Exception as e:
            print(f"Error parsing replanner response: {e}")

    # If still empty, fallback to financial_performance
    if not affected_cats:
        affected_cats = ["financial_performance"]

    affected_cats = list(dict.fromkeys(affected_cats))
    affected_ts = list(dict.fromkeys(affected_ts))

    if sse_callback:
        sse_callback({
            "agent": "replanner",
            "status": "replanning_complete",
            "affected_categories": affected_cats,
            "affected_tasks": affected_ts
        })

    return {
        "affected_categories": affected_cats,
        "affected_tasks": affected_ts,
        "run_status": "retrieving"
    }
