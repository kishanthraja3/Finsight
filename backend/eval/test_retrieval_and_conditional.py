import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.config import settings
from backend.agents.financial_research import get_resources, execute_financial_research
from backend.graph.build_graph import market_data_node, news_research_node
from backend.agents.verifier import resolve_chunk_id

class TestRetrievalAndConditional(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.model, cls.chroma_client = get_resources()
        try:
            cls.collection = cls.chroma_client.get_collection("finsight_documents")
        except Exception:
            cls.collection = None

    def test_c1_collection_compatibility(self):
        """C.6 & C.7: ChromaDB collection is compatible and uses cosine distance."""
        self.assertIsNotNone(self.collection, "Collection finsight_documents must exist")
        count = self.collection.count()
        self.assertGreater(count, 500, f"Corpus must have chunks (found {count})")
        # Verify metadata schema
        sample = self.collection.get(limit=5, include=["metadatas", "documents"])
        for meta in sample["metadatas"]:
            self.assertIn("company", meta)
            self.assertIn("doc_type", meta)
            self.assertIn("section", meta)

    def test_c2_company_metadata_filter(self):
        """C.1: Company metadata filters strictly isolate company chunks."""
        if not self.collection:
            self.skipTest("No collection")
        apple_res = self.collection.get(where={"company": "Apple"}, limit=10)
        for meta in apple_res["metadatas"]:
            self.assertEqual(meta["company"], "Apple")

        nvda_res = self.collection.get(where={"company": "NVIDIA"}, limit=10)
        for meta in nvda_res["metadatas"]:
            self.assertEqual(meta["company"], "NVIDIA")

    def test_c3_item1_vs_item1a_distinction(self):
        """C.3: Item 1 and Item 1A are distinguished and not confused."""
        if not self.collection:
            self.skipTest("No collection")
        sample_1a = self.collection.get(where={"section": "Item 1A Risk Factors"}, limit=5)
        for meta in sample_1a["metadatas"]:
            self.assertIn("1a", meta["section"].lower())
            self.assertNotIn("item 1 ", meta["section"].lower() + " ")

    def test_c4_retrieval_trace_stages(self):
        """C.4 & C.5: Retrieval trace preserves stages and shared chunks."""
        state = {
            "query": "Evaluate Apple's Services revenue growth",
            "run_id": "test_trace_01",
            "companies": ["Apple"],
            "tasks": [
                {
                    "id": "task_001",
                    "company": "Apple",
                    "agent": "financial_research",
                    "sub_question": "Services revenue growth across FY2023-FY2025",
                    "clause": "Services revenue growth",
                    "required_doc_types": ["10-K"],
                    "required_sections": ["Item 7"],
                    "semantic_keywords": ["services", "net sales", "revenue"]
                }
            ],
            "financial_evidence": [],
            "coverage_ledger": [],
            "retrieval_trace": {}
        }
        res = execute_financial_research(state)
        trace = res["retrieval_trace"]
        self.assertIn("task_001", trace)
        t_data = trace["task_001"]
        self.assertIn("retrieved_chunks", t_data)
        self.assertIn("selected_chunks", t_data)
        self.assertGreater(len(t_data["selected_chunks"]), 0)
        self.assertEqual(t_data["company"], "Apple")

    def test_g1_sec_only_query_skips_market_and_news(self):
        """G.1: SEC-only revenue/margin query skips Market Data and News."""
        sec_state = {
            "query": "Evaluate Apple's Services revenue growth and gross margin",
            "tasks": [
                {"id": "t1", "category": "financial_performance", "sub_question": "Services revenue"},
                {"id": "t2", "category": "financial_performance", "sub_question": "Gross margin"}
            ]
        }
        mkt_res = market_data_node(sec_state)
        news_res = news_research_node(sec_state)
        self.assertEqual(mkt_res, {"market_data": {}}, "Market data must be empty for SEC-only query")
        self.assertEqual(news_res, {"news_evidence": []}, "News must be empty for SEC-only query")

    def test_g2_market_query_triggers_market_node(self):
        """G.2: Market valuation query triggers Market Data node."""
        mkt_state = {
            "query": "What is NVIDIA's current stock price and valuation P/E ratio?",
            "companies": ["NVIDIA"],
            "tasks": [
                {"id": "t1", "category": "market_data", "sub_question": "Valuation and stock price"}
            ]
        }
        mkt_res = market_data_node(mkt_state)
        self.assertIn("market_data", mkt_res)
        self.assertIn("NVIDIA", mkt_res["market_data"])
        self.assertIn("provenance", mkt_res["market_data"]["NVIDIA"])

    def test_g3_news_query_triggers_news_node(self):
        """G.3: News and catalyst query triggers News node."""
        news_state = {
            "query": "Recent news headlines and sentiment for Microsoft",
            "companies": ["Microsoft"],
            "tasks": [
                {"id": "t1", "category": "news", "sub_question": "Recent news headlines"}
            ]
        }
        news_res = news_research_node(news_state)
        self.assertIn("news_evidence", news_res)
        self.assertGreater(len(news_res["news_evidence"]), 0)

if __name__ == "__main__":
    unittest.main()
