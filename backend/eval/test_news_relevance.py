import unittest
from backend.agents.news_research import evaluate_news_article_relevance, execute_news_research
from backend.agents.verifier import check_claim_support
from backend.agents.synthesis import execute_synthesis
from backend.agents.critic import execute_critic

class TestNewsRelevanceValidation(unittest.TestCase):

    def test_rejection_of_unrelated_portfolio_news(self):
        # 1. Three Seasons Wealth LLC boosting stake in Amazon (NVDA query)
        amazon_portfolio_article = {
            "title": "Three Seasons Wealth LLC Boosts Stock Holdings in Amazon.com, Inc. $AMZN",
            "url": "https://www.marketbeat.com/instant-alerts/nasdaq-amzn-sec-filing-2026-10-04/",
            "time_published": "20261004T070642",
            "summary": "Three Seasons Wealth LLC grew its holdings in shares of Amazon.com, Inc. by 3.2% in the 2nd quarter... Other hedge funds and institutional investors have also modified their holdings of the company. NVDA was also held in fund portfolio.",
            "overall_sentiment_score": 0.22,
            "overall_sentiment_label": "Somewhat-Bullish",
            "ticker_sentiment": [
                {
                    "ticker": "AMZN",
                    "relevance_score": "0.85",
                    "ticker_sentiment_score": "0.35",
                    "ticker_sentiment_label": "Bullish"
                },
                {
                    "ticker": "NVDA",
                    "relevance_score": "0.08",
                    "ticker_sentiment_score": "0.01",
                    "ticker_sentiment_label": "Neutral"
                }
            ]
        }
        is_rel, score, reason = evaluate_news_article_relevance(amazon_portfolio_article, "NVIDIA", "NVDA")
        self.assertFalse(is_rel)
        self.assertEqual(score, 0.0)
        self.assertIn("Unrelated portfolio/filing story", reason)

        # 2. Westrock Coffee filing for Microsoft query
        westrock_article = {
            "title": "Westrock Coffee Company $WEST Receives $9.00 Consensus Price Target from Analysts",
            "url": "https://www.marketbeat.com/instant-alerts/nasdaq-west-consensus-analyst-rating-2026-10-04/",
            "time_published": "20261004T080000",
            "summary": "Westrock Coffee Company has earned a consensus rating of Moderate Buy from analysts... Institutional holders also hold Microsoft Corp shares in minor allocations.",
            "overall_sentiment_score": 0.15,
            "overall_sentiment_label": "Somewhat-Bullish",
            "ticker_sentiment": [
                {
                    "ticker": "WEST",
                    "relevance_score": "0.90",
                    "ticker_sentiment_score": "0.25",
                    "ticker_sentiment_label": "Somewhat-Bullish"
                },
                {
                    "ticker": "MSFT",
                    "relevance_score": "0.05",
                    "ticker_sentiment_score": "0.0",
                    "ticker_sentiment_label": "Neutral"
                }
            ]
        }
        is_rel, score, reason = evaluate_news_article_relevance(westrock_article, "Microsoft", "MSFT")
        self.assertFalse(is_rel)
        self.assertEqual(score, 0.0)

    def test_acceptance_of_direct_company_news(self):
        nvda_headline_article = {
            "title": "Toews Corp ADV Buys New Shares in NVIDIA Corporation $NVDA",
            "url": "https://www.marketbeat.com/instant-alerts/nasdaq-nvda-sec-filing-2026-10-04/",
            "time_published": "20261004T070442",
            "summary": "Toews Corp ADV acquired a new position in shares of NVIDIA Corporation during the second quarter.",
            "overall_sentiment_score": 0.2,
            "ticker_sentiment": [
                {
                    "ticker": "NVDA",
                    "relevance_score": "1.0",
                    "ticker_sentiment_score": "0.198305",
                    "ticker_sentiment_label": "Somewhat-Bullish"
                }
            ]
        }
        is_rel, score, reason = evaluate_news_article_relevance(nvda_headline_article, "NVIDIA", "NVDA")
        self.assertTrue(is_rel)
        self.assertGreaterEqual(score, 100.0)

    def test_related_company_substantive_vs_unrelated(self):
        # Substantive: Amazon expanding AWS with Nvidia chips
        amazon_nvda_substantive = {
            "title": "Amazon Web Services Expands Cloud AI Infrastructure with NVIDIA Blackwell GPU Clusters",
            "url": "https://aws.amazon.com/press",
            "time_published": "20260930T100000",
            "summary": "Amazon AWS announces massive deployment of NVIDIA Blackwell and H100 GPUs across enterprise cloud data centers.",
            "overall_sentiment_score": 0.4,
            "ticker_sentiment": [
                {
                    "ticker": "AMZN",
                    "relevance_score": "0.7",
                    "ticker_sentiment_score": "0.3",
                    "ticker_sentiment_label": "Bullish"
                },
                {
                    "ticker": "NVDA",
                    "relevance_score": "0.6",
                    "ticker_sentiment_score": "0.4",
                    "ticker_sentiment_label": "Bullish"
                }
            ]
        }
        is_rel, score, _ = evaluate_news_article_relevance(amazon_nvda_substantive, "NVIDIA", "NVDA")
        self.assertTrue(is_rel)
        self.assertGreaterEqual(score, 60.0)

        # Unrelated: Amazon investment/retail story with incidental mention
        amazon_retail = {
            "title": "Amazon Retail and Prime Video Launch Fall Consumer Electronics Promotions",
            "url": "https://amazon.com/news",
            "time_published": "20260930T100000",
            "summary": "Amazon announced consumer discounts across tablets, headphones, and home appliances. Tech peers like Apple and Nvidia were flat in pre-market trading.",
            "overall_sentiment_score": 0.1,
            "ticker_sentiment": [
                {
                    "ticker": "AMZN",
                    "relevance_score": "0.9",
                    "ticker_sentiment_score": "0.2",
                    "ticker_sentiment_label": "Somewhat-Bullish"
                }
            ]
        }
        is_rel, score, _ = evaluate_news_article_relevance(amazon_retail, "NVIDIA", "NVDA")
        self.assertFalse(is_rel)

    def test_verifier_rejects_irrelevant_news_citation(self):
        finding_with_bad_news = {
            "id": "finding_001",
            "task_id": "task_news",
            "category": "news",
            "company": "NVIDIA",
            "statement": "Recent market news for NVIDIA: 'Three Seasons Wealth LLC Boosts Stock Holdings in Amazon.com, Inc. $AMZN'.",
            "news_citation": {
                "title": "Three Seasons Wealth LLC Boosts Stock Holdings in Amazon.com, Inc. $AMZN",
                "publisher": "MarketBeat",
                "url": "https://marketbeat.com/amzn"
            },
            "evidence_chunk_ids": ["news_NVDA_recent"]
        }
        is_supported, reason = check_claim_support(finding_with_bad_news, [], [])
        self.assertFalse(is_supported)
        self.assertEqual(finding_with_bad_news["citation_status"], "unsupported")
        self.assertEqual(finding_with_bad_news["confidence"], "low")

    def test_synthesis_fallback_when_no_relevant_news(self):
        # When only irrelevant news is present
        state = {
            "tasks": [
                {
                    "id": "task_001",
                    "company": "NVIDIA",
                    "category": "news",
                    "sub_question": "Summarize the latest NVIDIA news"
                }
            ],
            "companies": ["NVIDIA"],
            "coverage_ledger": [
                {
                    "task_id": "task_001",
                    "company": "NVIDIA",
                    "category": "news",
                    "task_text": "Summarize the latest NVIDIA news",
                    "qc_status": "PENDING"
                }
            ],
            "financial_evidence": [],
            "market_evidence": [],
            "news_evidence": [
                {
                    "company": "NVIDIA",
                    "ticker": "NVDA",
                    "title": "Three Seasons Wealth LLC Boosts Stock Holdings in Amazon.com, Inc. $AMZN",
                    "summary": "Holdings in Amazon changed.",
                    "url": "https://marketbeat.com",
                    "is_relevant": False, # rejected during retrieval
                    "relevance_score": 0.0
                }
            ],
            "risk_findings": [],
            "human_decisions": {}
        }
        out = execute_synthesis(state)
        findings = out.get("findings", [])
        self.assertEqual(len(findings), 1)
        finding = findings[0]
        self.assertIn("No sufficiently relevant news retrieved for NVIDIA", finding["statement"])
        self.assertEqual(finding["citation_status"], "unsupported")
        self.assertEqual(finding["confidence"], "low")
        self.assertIsNone(finding["news_citation"])

    def test_critic_rejects_irrelevant_news_finding(self):
        state = {
            "tasks": [
                {
                    "id": "task_001",
                    "company": "NVIDIA",
                    "category": "news",
                    "sub_question": "Summarize latest news"
                }
            ],
            "companies": ["NVIDIA"],
            "coverage_ledger": [
                {
                    "task_id": "task_001",
                    "company": "NVIDIA",
                    "category": "news",
                    "task_text": "Summarize latest news",
                    "qc_status": "PENDING"
                }
            ],
            "findings": [
                {
                    "id": "finding_001",
                    "task_id": "task_001",
                    "category": "news",
                    "statement": "Recent news: Amazon stake increased.",
                    "confidence": "high",
                    "citation_status": "supported",
                    "news_citation": {
                        "title": "Three Seasons Wealth LLC Boosts Stock Holdings in Amazon.com, Inc. $AMZN",
                        "publisher": "MarketBeat",
                        "url": "https://marketbeat.com"
                    }
                }
            ],
            "retry_counts": {"task_001": 0}
        }
        critic_out = execute_critic(state)
        critic_res = critic_out.get("critic_result", {})
        self.assertFalse(critic_res.get("passed"))
        self.assertTrue(any("cites irrelevant news" in issue for issue in critic_res.get("issues", [])))

if __name__ == "__main__":
    unittest.main()
