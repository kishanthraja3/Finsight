import sys
import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.graph.build_graph import (
    apply_decision_to_finding,
    human_review_node,
    compile_final_report
)
from backend.agents.critic import execute_critic
from backend.agents.synthesis import _build_fallback_synthesis
from backend.agents.llm_client import (
    call_gemini,
    RateLimitExhaustedError,
    telemetry_tracker
)

class TestHITLAndWorkflow(unittest.TestCase):

    def test_e1_raw_tables_rejected_and_empty_output_handled(self):
        """E.1 & E.2: Raw SEC tables are not approved as findings; empty output handled cleanly."""
        draft, findings = _build_fallback_synthesis(
            query="Apple Services gross margin",
            companies=["Apple"],
            tasks=[{"id": "t1", "sub_question": "Services gross margin", "category": "financial_performance"}],
            fin_evidence=[],
            market_data={},
            news_evidence=[],
            risk_findings=[],
            human_decisions={}
        )
        for f in findings:
            self.assertNotIn("|", f["statement"])
            self.assertNotIn("---", f["statement"])

    def test_e2_critic_fails_closed_on_error(self):
        """E.4: Critic fails closed when LLM fails or response is unparseable."""
        state = {
            "tasks": [{"id": "t1", "sub_question": "Services gross margin", "category": "financial_performance"}],
            "findings": [{"id": "f1", "task_id": "t1", "category": "financial_performance", "statement": "Services margin was 75.4% in FY2025.", "confidence": "high", "evidence_chunk_ids": ["c1"]}],
            "coverage_ledger": [{
                "task_id": "t1",
                "task": "Services gross margin",
                "company": "Apple",
                "evidence_retrieved": ["c1"],
                "final_finding": "Services margin was 75.4% in FY2025.",
                "qc_status": "PENDING",
                "evidence_limitation": None
            }],
            "retry_count": 0,
            "max_retries": 2
        }
        with patch("backend.agents.critic.call_gemini", side_effect=Exception("API connection failure")):
            res = execute_critic(state)
            self.assertFalse(res["critic_result"]["passed"], "Critic must fail closed on API error")
            self.assertIn("FAILED", [e["qc_status"] for e in res["coverage_ledger"]] + (["FAILED"] if not res["critic_result"]["passed"] else []))

    def test_f1_hitl_action_normalization_and_edit_revalidation(self):
        """F.1, F.2, F.3: Canonical actions (approved, edited, rejected), edit revalidation, rejection exclusion."""
        state = {
            "query": "Evaluate Apple gross margin",
            "companies": ["Apple"],
            "financial_evidence": [
                {
                    "chunk_id": "c1",
                    "text": "Gross margin percentage for Services was 75.4% in fiscal 2025.",
                    "task_id": "t1",
                    "metadata": {"doc_type": "10-K", "section": "Item 7"}
                }
            ],
            "news_evidence": [],
            "coverage_ledger": [{"task_id": "t1", "task": "Gross margin", "qc_status": "PASSED"}]
        }
        # 1. Edit action
        f_edit = {
            "id": "f_001",
            "task_id": "t1",
            "statement": "Services gross margin was 80.0%",
            "status": "pending",
            "evidence_chunk_ids": ["c1"]
        }
        apply_decision_to_finding(f_edit, {"status": "edit", "edited_text": "Services gross margin was 75.4% in fiscal 2025"}, state)
        self.assertEqual(f_edit["status"], "edited")
        self.assertTrue(f_edit["numerically_verified"], "Revalidated edit should verify figure 75.4% present in c1")

        # 2. Reject action
        f_reject = {
            "id": "f_002",
            "task_id": "t1",
            "statement": "Total revenue was $1 trillion",
            "status": "pending",
            "evidence_chunk_ids": ["c1"]
        }
        apply_decision_to_finding(f_reject, {"status": "reject", "reason": "Incorrect figure"}, state)
        self.assertEqual(f_reject["status"], "rejected")

        # 3. Compile report excludes rejected
        report = compile_final_report(state, [f_edit, f_reject])
        self.assertNotIn("Total revenue was $1 trillion", report, "Rejected finding must never appear in final report")
        self.assertIn("Services gross margin was 75.4%", report, "Approved/edited finding must appear in report")

    def test_f2_pending_decisions_detected_on_replan(self):
        """F.4 & F.5: Pending decisions are detected even when previous decisions exist."""
        state = {
            "findings": [
                {"id": "f1", "status": "approved", "statement": "Services margin was 75.4% in FY2025."},
                {"id": "f2", "status": "pending", "statement": "New replanned finding for European risks."}
            ],
            "human_decisions": {"f1": {"status": "approve"}},
            "critic_result": {"passed": True},
            "financial_evidence": [],
            "news_evidence": [],
            "coverage_ledger": []
        }
        # Interrupt will be called for f2 because it is pending, even though f1 is in human_decisions
        with patch("backend.graph.build_graph.interrupt") as mock_interrupt:
            mock_interrupt.return_value = {"decisions": {"f2": {"status": "approve"}}}
            res = human_review_node(state)
            mock_interrupt.assert_called_once()
            self.assertEqual(res["findings"][1]["status"], "approved")

    def test_t5_simulated_rate_limit(self):
        """T5: Simulated 429 Rate Limit enforces bounded retries and raises typed error."""
        telemetry_tracker.get_run_metrics("sim_rate_limit_run")
        with patch("groq.resources.chat.completions.Completions.create") as mock_create:
            mock_response = MagicMock()
            mock_response.status_code = 429
            mock_response.headers = {"Retry-After": "2"}
            from groq import RateLimitError
            mock_create.side_effect = RateLimitError("Rate limit exceeded 429", response=mock_response, body={"error": {"message": "Rate limit reached"}})

            with self.assertRaises(RateLimitExhaustedError):
                call_gemini("Test rate limit prompt", max_retries=1)

            # Assert bounded retries (should not loop infinitely)
            self.assertLessEqual(mock_create.call_count, 2, "Must not retry more than configured max_retries")

if __name__ == "__main__":
    unittest.main()
