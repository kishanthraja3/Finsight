import sys
import unittest
from pathlib import Path
from typing import Dict, Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.agents.planner import classify_research_intent, plan_research
from backend.graph.build_graph import financial_research_node, market_data_node, news_research_node, synthesis_node
from backend.graph.state import FinSightState

class TestSystemWideRoutingIntent(unittest.TestCase):
    """
    System-wide regression test suite for intelligent retrieval routing and intent classification.
    Covers Queries A through E defined in the specification.
    """

    def test_query_a_microsoft_revenue_growth(self):
        """
        Query A: 'What was Microsoft's revenue growth in its latest annual filing?'
        Expected: SEC required; market data and news not required.
        """
        query = "What was Microsoft's revenue growth in its latest annual filing?"
        intent = classify_research_intent(query)
        
        self.assertTrue(intent["sec_retrieval_required"], "SEC retrieval must be required for annual filing revenue growth")
        self.assertFalse(intent["market_data_required"], "Market data must NOT be required for SEC annual revenue query")
        self.assertFalse(intent["news_required"], "News must NOT be required for SEC annual revenue query")

        # Test planner decomposition
        state: FinSightState = {
            "query": query,
            "run_id": "test_routing_a",
            "companies": ["Microsoft"],
            "tasks": [],
            "coverage_ledger": [],
            "retrieval_trace": {},
            "financial_evidence": [],
            "market_data": {},
            "news_evidence": [],
            "risk_findings": [],
            "findings": [],
            "synthesis_draft": "",
            "critic_result": {},
            "retry_count": 0,
            "max_retries": 1,
            "human_decisions": {},
            "affected_categories": [],
            "affected_tasks": [],
            "final_report": "",
            "run_status": "planning"
        }
        plan_out = plan_research(state)
        state.update(plan_out)

        # Verify task categories
        tasks = state.get("tasks", [])
        self.assertTrue(any(t.get("category") == "financial_performance" for t in tasks))
        self.assertFalse(any(t.get("category") == "market_data" for t in tasks))
        self.assertFalse(any(t.get("category") == "news" for t in tasks))

        # Test node routing behavior
        mkt_res = market_data_node(state)
        self.assertEqual(mkt_res.get("market_data"), {}, "market_data_node must return empty for Query A")

        news_res = news_research_node(state)
        self.assertEqual(news_res.get("news_evidence"), [], "news_research_node must return empty for Query A")

    def test_query_b_nvidia_price_performance(self):
        """
        Query B: 'Analyse current Nvidia price performance.'
        Expected: market data required; news and SEC not required.
        """
        query = "Analyse current Nvidia price performance."
        intent = classify_research_intent(query)

        self.assertTrue(intent["market_data_required"], "Market data MUST be required for price performance query")
        self.assertFalse(intent["sec_retrieval_required"], "SEC retrieval must NOT be required for pure stock price performance")
        self.assertFalse(intent["news_required"], "News must NOT be required for pure price performance")

        # Test planner decomposition
        state: FinSightState = {
            "query": query,
            "run_id": "test_routing_b",
            "companies": ["NVIDIA"],
            "tasks": [],
            "coverage_ledger": [],
            "retrieval_trace": {},
            "financial_evidence": [],
            "market_data": {},
            "news_evidence": [],
            "risk_findings": [],
            "findings": [],
            "synthesis_draft": "",
            "critic_result": {},
            "retry_count": 0,
            "max_retries": 1,
            "human_decisions": {},
            "affected_categories": [],
            "affected_tasks": [],
            "final_report": "",
            "run_status": "planning"
        }
        plan_out = plan_research(state)
        state.update(plan_out)

        tasks = state.get("tasks", [])
        self.assertTrue(any(t.get("category") == "market_data" for t in tasks), "Must produce a market_data task")
        self.assertFalse(any(t.get("category") == "financial_performance" for t in tasks), "Must not have SEC tasks")

        # Verify node execution
        fin_res = financial_research_node(state)
        self.assertEqual(fin_res.get("financial_evidence"), [], "financial_research_node must bypass for Query B")

        news_res = news_research_node(state)
        self.assertEqual(news_res.get("news_evidence"), [], "news_research_node must bypass for Query B")

        mkt_res = market_data_node(state)
        self.assertIn("NVIDIA", mkt_res.get("market_data", {}), "market_data_node must execute for Query B")
        state.update(mkt_res)

        # Verify synthesis consumes market data and produces verified finding
        syn_res = synthesis_node(state)
        findings = syn_res.get("findings", [])
        mkt_findings = [f for f in findings if f.get("category") == "market_data"]
        self.assertGreaterEqual(len(mkt_findings), 1, "Synthesis must produce a market_data finding")
        self.assertEqual(mkt_findings[0]["figure_status"], "verified")
        self.assertEqual(mkt_findings[0]["citation_status"], "supported")

        # Verify Coverage Ledger QC status
        ledger = syn_res.get("coverage_ledger", [])
        mkt_entry = next((e for e in ledger if "task_001" in e["task_id"]), None)
        self.assertIsNotNone(mkt_entry)
        self.assertIn(mkt_entry["qc_status"], ["PASSED", "LIMITATION"])

    def test_query_c_microsoft_price_performance_and_risks(self):
        """
        Query C: 'Analyse current Microsoft price performance and risks involved.'
        Expected: market data, news, and SEC retrieval ALL required.
        """
        query = "Analyse current Microsoft price performance and risks involved."
        intent = classify_research_intent(query)

        self.assertTrue(intent["market_data_required"], "Market data must be required")
        self.assertTrue(intent["news_required"], "News must be required for joint performance + risk context")
        self.assertTrue(intent["sec_retrieval_required"], "SEC retrieval must be required for risks involved")

        # Test planner decomposition
        state: FinSightState = {
            "query": query,
            "run_id": "test_routing_c",
            "companies": ["Microsoft"],
            "tasks": [],
            "coverage_ledger": [],
            "retrieval_trace": {},
            "financial_evidence": [],
            "market_data": {},
            "news_evidence": [],
            "risk_findings": [],
            "findings": [],
            "synthesis_draft": "",
            "critic_result": {},
            "retry_count": 0,
            "max_retries": 1,
            "human_decisions": {},
            "affected_categories": [],
            "affected_tasks": [],
            "final_report": "",
            "run_status": "planning"
        }
        plan_out = plan_research(state)
        state.update(plan_out)

        tasks = state.get("tasks", [])
        categories = {t.get("category") for t in tasks}
        self.assertIn("market_data", categories, "Must include market_data task")
        self.assertIn("risk", categories, "Must include risk task")
        self.assertIn("news", categories, "Must include news task")

        # Verify all nodes activate
        mkt_res = market_data_node(state)
        self.assertIn("Microsoft", mkt_res.get("market_data", {}))
        state.update(mkt_res)

        news_res = news_research_node(state)
        self.assertGreater(len(news_res.get("news_evidence", [])), 0)
        state.update(news_res)

    def test_query_d_apple_european_regulatory_risks(self):
        """
        Query D: 'What are Apple's European regulatory risks disclosed in Item 1A?'
        Expected: SEC required; market data not required; news optional.
        """
        query = "What are Apple's European regulatory risks disclosed in Item 1A?"
        intent = classify_research_intent(query)

        self.assertTrue(intent["sec_retrieval_required"], "SEC retrieval must be required for Item 1A regulatory risks")
        self.assertFalse(intent["market_data_required"], "Market data must NOT be required for Item 1A regulatory risks")

        # Test planner decomposition
        state: FinSightState = {
            "query": query,
            "run_id": "test_routing_d",
            "companies": ["Apple"],
            "tasks": [],
            "coverage_ledger": [],
            "retrieval_trace": {},
            "financial_evidence": [],
            "market_data": {},
            "news_evidence": [],
            "risk_findings": [],
            "findings": [],
            "synthesis_draft": "",
            "critic_result": {},
            "retry_count": 0,
            "max_retries": 1,
            "human_decisions": {},
            "affected_categories": [],
            "affected_tasks": [],
            "final_report": "",
            "run_status": "planning"
        }
        plan_out = plan_research(state)
        state.update(plan_out)

        tasks = state.get("tasks", [])
        self.assertTrue(any(t.get("category") == "risk" for t in tasks), "Must produce risk task")
        self.assertFalse(any(t.get("category") == "market_data" for t in tasks), "Must NOT produce market_data task")

        # Market data node must bypass
        mkt_res = market_data_node(state)
        self.assertEqual(mkt_res.get("market_data"), {}, "market_data_node must bypass for Query D")

    def test_query_e_summarize_latest_nvidia_news(self):
        """
        Query E: 'Summarize the latest NVIDIA news.'
        Expected: news required; market data and SEC not required.
        """
        query = "Summarize the latest NVIDIA news."
        intent = classify_research_intent(query)

        self.assertTrue(intent["news_required"], "News must be required for news summary query")
        self.assertFalse(intent["market_data_required"], "Market data must NOT be required for pure news query")
        self.assertFalse(intent["sec_retrieval_required"], "SEC retrieval must NOT be required for pure news query")

        # Test planner decomposition
        state: FinSightState = {
            "query": query,
            "run_id": "test_routing_e",
            "companies": ["NVIDIA"],
            "tasks": [],
            "coverage_ledger": [],
            "retrieval_trace": {},
            "financial_evidence": [],
            "market_data": {},
            "news_evidence": [],
            "risk_findings": [],
            "findings": [],
            "synthesis_draft": "",
            "critic_result": {},
            "retry_count": 0,
            "max_retries": 1,
            "human_decisions": {},
            "affected_categories": [],
            "affected_tasks": [],
            "final_report": "",
            "run_status": "planning"
        }
        plan_out = plan_research(state)
        state.update(plan_out)

        tasks = state.get("tasks", [])
        self.assertTrue(any(t.get("category") == "news" for t in tasks), "Must produce news task")
        self.assertFalse(any(t.get("category") in ["financial_performance", "market_data"] for t in tasks))

        # Check node execution
        fin_res = financial_research_node(state)
        self.assertEqual(fin_res.get("financial_evidence"), [], "financial_research_node must bypass for Query E")

        mkt_res = market_data_node(state)
        self.assertEqual(mkt_res.get("market_data"), {}, "market_data_node must bypass for Query E")

        news_res = news_research_node(state)
        self.assertGreater(len(news_res.get("news_evidence", [])), 0, "news_research_node must retrieve articles")
        state.update(news_res)

        # Synthesis
        syn_res = synthesis_node(state)
        findings = syn_res.get("findings", [])
        news_findings = [f for f in findings if f.get("category") == "news"]
        self.assertGreaterEqual(len(news_findings), 1, "Must generate a news finding")
        self.assertIsNotNone(news_findings[0].get("news_citation"), "News finding must contain news citation")

if __name__ == "__main__":
    unittest.main()
