import sys
import uuid
import threading
import asyncio
from pathlib import Path
from typing import Dict, Any, Optional, List

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fastapi import APIRouter, HTTPException, BackgroundTasks, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from langgraph.types import Command

import datetime
from backend.config import settings
from backend.graph.state import FinSightState, Finding
from backend.graph.build_graph import build_finsight_graph, register_sse_callback, compile_final_report
from backend.agents.llm_client import telemetry_tracker
from backend.api.sse import sse_manager
from backend.api.pdf_generator import generate_report_pdf

router = APIRouter(prefix="/api")

# In-memory storage for runs and compiled graph
graph_app = build_finsight_graph()
RUNS_DB: Dict[str, Dict[str, Any]] = {}
RUNS_LOCK = threading.Lock()

class CreateRunRequest(BaseModel):
    query: str

class DecisionRequest(BaseModel):
    status: str  # "approve" | "edit" | "reject" | "request_evidence"
    edited_text: Optional[str] = None
    reason: Optional[str] = None
    note: Optional[str] = None

def run_graph_worker(run_id: str, state: FinSightState, resume_input: Optional[Any] = None):
    """
    Executes or resumes LangGraph state machine in a background thread.
    """
    config = {"configurable": {"thread_id": run_id}}

    def sse_cb(event: Dict[str, Any]):
        event["run_id"] = run_id
        event["active_model"] = telemetry_tracker.get_active_model(run_id)
        metrics = telemetry_tracker.get_run_metrics(run_id)
        event["fallback_active"] = metrics.get("fallback_active", False)
        sse_manager.publish_event(run_id, event)

    register_sse_callback(run_id, sse_cb)

    try:
        if resume_input is not None:
            # Resuming graph from interrupt
            sse_cb({"type": "status", "agent": "replanner" if any(d.get("status") == "reject" for d in state.get("human_decisions", {}).values()) else "human_review", "status": "resuming_graph"})
            output = graph_app.invoke(Command(resume=resume_input), config=config)
        else:
            # Initial invocation
            sse_cb({"type": "status", "agent": "planner", "status": "starting_research", "query": state["query"]})
            output = graph_app.invoke(state, config=config)

        with RUNS_LOCK:
            current_state = RUNS_DB.get(run_id, {}).get("state", state)
            if output:
                current_state.update(output)
            RUNS_DB[run_id]["state"] = current_state

        # Check graph state to see if interrupted or completed
        graph_snapshot = graph_app.get_state(config)
        if graph_snapshot.next:  # Graph is paused at an interrupt (e.g. human_review)
            with RUNS_LOCK:
                RUNS_DB[run_id]["state"]["run_status"] = "awaiting_human"
            sse_cb({
                "type": "status",
                "agent": "human_review",
                "status": "awaiting_human",
                "run_status": "awaiting_human",
                "findings": RUNS_DB[run_id]["state"].get("findings", [])
            })
        else:
            # Completed
            with RUNS_LOCK:
                RUNS_DB[run_id]["state"]["run_status"] = "complete"
                if not RUNS_DB[run_id]["state"].get("final_report"):
                    RUNS_DB[run_id]["state"]["final_report"] = compile_final_report(
                        RUNS_DB[run_id]["state"],
                        RUNS_DB[run_id]["state"].get("findings", [])
                    )
            sse_cb({
                "type": "status",
                "agent": "human_review",
                "status": "complete",
                "run_status": "complete",
                "final_report": RUNS_DB[run_id]["state"]["final_report"]
            })

    except Exception as e:
        print(f"Error in run_graph_worker for {run_id}: {e}")
        import traceback
        traceback.print_exc()
        with RUNS_LOCK:
            if run_id in RUNS_DB:
                RUNS_DB[run_id]["state"]["run_status"] = "error"
        sse_cb({
            "type": "error",
            "agent": "system",
            "status": "error",
            "message": str(e)
        })

@router.post("/runs")
def create_run(req: CreateRunRequest):
    """Start a new research run."""
    query = req.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query cannot be empty.")

    run_id = f"run_{uuid.uuid4().hex[:8]}"

    initial_state: FinSightState = {
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
        "max_retries": settings.MAX_RETRIES,
        "human_decisions": {},
        "affected_categories": [],
        "affected_tasks": [],
        "final_report": "",
        "run_status": "planning"
    }

    with RUNS_LOCK:
        RUNS_DB[run_id] = {
            "run_id": run_id,
            "state": initial_state
        }

    # Launch background thread
    t = threading.Thread(target=run_graph_worker, args=(run_id, initial_state, None), daemon=True)
    t.start()

    return {"run_id": run_id, "status": "started"}

@router.get("/runs/{run_id}/stream")
async def stream_run_events(run_id: str):
    """SSE stream of live agent status events."""
    if run_id not in RUNS_DB:
        raise HTTPException(status_code=404, detail="Run ID not found.")

    return StreamingResponse(
        sse_manager.event_generator(run_id),
        media_type="text/event-stream"
    )

@router.get("/runs/{run_id}/report")
def get_run_report(run_id: str):
    """Returns current report state: synthesis_draft, findings (with status), critic_result."""
    with RUNS_LOCK:
        run_record = RUNS_DB.get(run_id)
        if not run_record:
            raise HTTPException(status_code=404, detail="Run ID not found.")
        st = run_record["state"]
        active_model = telemetry_tracker.get_active_model(run_id)
        metrics = telemetry_tracker.get_run_metrics(run_id)
        return {
            "run_id": run_id,
            "query": st.get("query"),
            "companies": st.get("companies", []),
            "tasks": st.get("tasks", []),
            "coverage_ledger": st.get("coverage_ledger", []),
            "synthesis_draft": st.get("synthesis_draft", ""),
            "findings": st.get("findings", []),
            "critic_result": st.get("critic_result", {"passed": False, "issues": []}),
            "retry_count": st.get("retry_count", 0),
            "max_retries": st.get("max_retries", 3),
            "run_status": st.get("run_status", "planning"),
            "affected_categories": st.get("affected_categories", []),
            "active_model": active_model,
            "fallback_active": metrics.get("fallback_active", False)
        }

@router.post("/runs/{run_id}/findings/{finding_id}/decision")
def post_finding_decision(run_id: str, finding_id: str, decision: DecisionRequest):
    """
    Feeds into human_decisions and resumes the graph:
    - If status == 'approve' / 'edit': records decision
    - If status == 'reject': records reason; only replans if replacement research is explicitly requested
    - If status == 'request_evidence': records note and triggers targeted replanner
    """
    with RUNS_LOCK:
        run_record = RUNS_DB.get(run_id)
        if not run_record:
            raise HTTPException(status_code=404, detail="Run ID not found.")
        
        st = run_record["state"]
        findings = st.get("findings", [])
        
        # Locate target finding
        target_f = None
        for f in findings:
            if f["id"] == finding_id:
                target_f = f
                break
        
        if not target_f:
            raise HTTPException(status_code=404, detail=f"Finding '{finding_id}' not found.")

        # Normalize status to standard canonical forms
        if decision.status in ["approve", "approved"]:
            canonical_status = "approved"
        elif decision.status in ["edit", "edited"]:
            canonical_status = "edited"
        elif decision.status in ["request_evidence", "evidence"]:
            canonical_status = "request_evidence"
        else:
            canonical_status = "rejected"

        target_f["status"] = canonical_status
        if canonical_status == "edited":
            target_f["statement"] = decision.edited_text or target_f["statement"]
            target_f["edited_text"] = decision.edited_text
        elif canonical_status == "rejected":
            target_f["rejection_reason"] = decision.reason
            if decision.note:
                target_f["evidence_request_note"] = decision.note
        elif canonical_status == "request_evidence":
            note = decision.note or decision.reason or "Reviewer requested more evidence."
            target_f["evidence_request_note"] = note
            # Surgical routing: record task_id and category
            tid = target_f.get("task_id")
            if tid:
                st.setdefault("affected_tasks", []).append(tid)
            if target_f.get("category"):
                st.setdefault("affected_categories", []).append(target_f["category"])

        st["human_decisions"][finding_id] = {
            "status": canonical_status,
            "edited_text": decision.edited_text,
            "reason": decision.reason,
            "note": decision.note or decision.reason
        }

    # Notify SSE listeners
    sse_manager.publish_event(run_id, {
        "type": "decision_recorded",
        "finding_id": finding_id,
        "status": canonical_status,
        "reason": decision.reason,
        "note": decision.note or decision.reason,
        "all_findings": findings,
        "active_model": telemetry_tracker.get_active_model(run_id)
    })

    # Check if all findings now have decisions
    all_decided = all(f.get("status") in ["approved", "edited", "rejected", "request_evidence"] for f in findings)
    has_replan_action = any(
        f.get("status") == "request_evidence" or 
        (f.get("status") in ["rejected", "reject"] and f.get("evidence_request_note"))
        for f in findings
    )

    # Resume graph execution if explicit re-retrieval requested or all decided
    if canonical_status == "request_evidence" or (canonical_status == "rejected" and decision.note) or all_decided:
        t = threading.Thread(
            target=run_graph_worker,
            args=(run_id, st, {"decisions": st["human_decisions"]}),
            daemon=True
        )
        t.start()

    return {
        "status": "decision_applied",
        "finding_id": finding_id,
        "decision": canonical_status,
        "all_decided": all_decided,
        "has_rejections": has_replan_action
    }

@router.post("/runs/{run_id}/findings/approve-all")
def approve_all_findings(run_id: str):
    """Batch approves all pending findings and immediately resumes the workflow."""
    with RUNS_LOCK:
        run_record = RUNS_DB.get(run_id)
        if not run_record:
            raise HTTPException(status_code=404, detail="Run ID not found.")
        st = run_record["state"]
        findings = st.get("findings", [])
        for f in findings:
            if f.get("status") == "pending":
                f["status"] = "approved"
                st["human_decisions"][f["id"]] = {"status": "approved"}

    sse_manager.publish_event(run_id, {
        "type": "decision_recorded",
        "finding_id": "all",
        "status": "approved",
        "all_findings": findings
    })

    t = threading.Thread(
        target=run_graph_worker,
        args=(run_id, st, {"decisions": st["human_decisions"]}),
        daemon=True
    )
    t.start()

    return {"status": "all_approved", "count": len(findings)}

@router.get("/runs/{run_id}/report/final")
def get_final_report(run_id: str):
    """Returns the locked final report once run_status == 'complete'."""
    with RUNS_LOCK:
        run_record = RUNS_DB.get(run_id)
        if not run_record:
            raise HTTPException(status_code=404, detail="Run ID not found.")
        st = run_record["state"]
        
        if st.get("run_status") != "complete" and not st.get("final_report"):
            # Check if all findings are approved/edited
            findings = st.get("findings", [])
            if findings and all(f.get("status") in ["approved", "edited"] for f in findings):
                st["final_report"] = compile_final_report(st, findings)
                st["run_status"] = "complete"

        return {
            "run_id": run_id,
            "run_status": st.get("run_status"),
            "final_report": st.get("final_report", ""),
            "findings": st.get("findings", [])
        }

@router.get("/runs/{run_id}/report/download")
def download_final_report(run_id: str):
    """Returns the final report as a downloadable Markdown file."""
    with RUNS_LOCK:
        run_record = RUNS_DB.get(run_id)
        if not run_record:
            raise HTTPException(status_code=404, detail="Run ID not found.")
        st = run_record["state"]
        report_content = st.get("final_report") or st.get("synthesis_draft", "# FinSight Report")

    filename = f"FinSight_Research_{run_id}.md"
    return Response(
        content=report_content,
        media_type="text/markdown",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )

@router.get("/runs/{run_id}/report/pdf")
def download_pdf_report(run_id: str):
    """Returns the professional research report as a downloadable PDF file."""
    with RUNS_LOCK:
        run_record = RUNS_DB.get(run_id)
        if not run_record:
            raise HTTPException(status_code=404, detail="Run ID not found.")
        st = run_record["state"]

    pdf_bytes = generate_report_pdf(run_id, st)
    filename = f"FinSight_Research_{run_id}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )

@router.get("/reports")
def list_reports():
    """Lists all research reports published or stored in the system."""
    with RUNS_LOCK:
        reports = []
        for run_id, run_record in RUNS_DB.items():
            st = run_record.get("state", {})
            findings = st.get("findings", [])
            approved = [f for f in findings if f.get("status") in ["approved", "edited"]]
            reports.append({
                "run_id": run_id,
                "query": st.get("query", "Institutional Research"),
                "companies": st.get("companies", []),
                "run_status": st.get("run_status", "complete"),
                "findings_count": len(findings),
                "approved_count": len(approved) if approved else len(findings),
                "created_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })
        return {"reports": reports}
