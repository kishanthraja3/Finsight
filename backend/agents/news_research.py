import os
import sys
import json
import datetime
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import requests
from backend.config import settings, rate_limiter
from backend.agents.market_data import get_ticker_for_company, get_cache_path
from backend.graph.state import FinSightState

COMPANY_ENTITY_MAP: Dict[str, Dict[str, Any]] = {
    "NVIDIA": {
        "names": ["nvidia", "nvda", "geforce", "blackwell", "hopper", "h100", "h200", "b100", "b200", "cuda", "jensen huang", "dgx", "grace", "rtx"],
        "ticker": "NVDA",
        "related_context": ["chip", "chips", "gpu", "gpus", "semiconductor", "accelerator", "ai compute", "foundry", "data center", "datacenter", "supply", "supplier", "partnership", "procurement", "tsmc"]
    },
    "Microsoft": {
        "names": ["microsoft", "msft", "azure", "windows", "copilot", "satya nadella", "xbox", "surface", "office 365", "teams", "dynamics 365"],
        "ticker": "MSFT",
        "related_context": ["cloud", "enterprise", "openai", "datacenter", "software", "infrastructure", "ai platform", "hyperscaler"]
    },
    "Apple": {
        "names": ["apple", "aapl", "iphone", "ipad", "mac", "macbook", "ios", "app store", "tim cook", "vision pro", "m3", "m4", "airpods"],
        "ticker": "AAPL",
        "related_context": ["services", "smartphone", "digital markets act", "dma", "hardware", "supplier", "procurement", "wearables"]
    },
    "Amazon": {
        "names": ["amazon", "amzn", "aws", "andy jassy", "prime", "bedrock", "annapurna"],
        "ticker": "AMZN",
        "related_context": ["cloud", "ecommerce", "datacenter", "retail", "server"]
    },
    "Alphabet": {
        "names": ["alphabet", "google", "googl", "goog", "sundar pichai", "gemini", "tpu", "deepmind"],
        "ticker": "GOOGL",
        "related_context": ["search", "cloud", "ai", "advertising", "datacenter"]
    }
}

def get_company_config(company: str, target_ticker: str = None) -> Dict[str, Any]:
    norm_comp = company.strip()
    for k, v in COMPANY_ENTITY_MAP.items():
        if (
            k.lower() == norm_comp.lower() 
            or norm_comp.lower() in [n.lower() for n in v.get("names", [])]
            or v.get("ticker", "").upper() == (target_ticker or "").upper()
        ):
            return v
    ticker = target_ticker or get_ticker_for_company(company)
    names = [norm_comp.lower(), ticker.lower()]
    import re
    words = [w.lower() for w in re.findall(r'[A-Za-z]+', norm_comp) if len(w) > 2]
    names = list(dict.fromkeys(names + words))
    return {
        "names": names,
        "ticker": ticker,
        "related_context": ["earnings", "revenue", "profit", "shares", "growth", "partnership", "supply", "market"]
    }

def evaluate_news_article_relevance(
    article: Dict[str, Any], 
    company: str, 
    target_ticker: str = None
) -> Tuple[bool, float, str]:
    """
    Evaluates whether a news article is materially relevant to the requested company.
    - Matches company names, aliases, tickers, and entity relationships.
    - Rejects unrelated portfolio adjustments/Form 13-F stories for third-party companies.
    - Only accepts related-company articles if they substantively discuss the target company or its products.
    - Returns (is_relevant, relevance_score, reason).
    """
    import re
    cfg = get_company_config(company, target_ticker)
    ticker = cfg["ticker"]
    aliases = cfg["names"]
    related_context = cfg["related_context"]

    title = (article.get("title") or "").strip()
    summary = (article.get("summary") or "").strip()
    title_lower = title.lower()
    summary_lower = summary.lower()

    has_target_in_title = any(re.search(rf'\b{re.escape(alias)}\b', title_lower) for alias in aliases) or f"${ticker.lower()}" in title_lower

    other_ticker_matches = [t for t in re.findall(r'\$([A-Z]{2,5})\b', title) if t != ticker.upper()]
    prominent_other_companies = [
        "amazon", "google", "alphabet", "meta", "tesla", "westrock", "intel", "amd", 
        "qualcomm", "netflix", "salesforce", "cameco", "deere", "servicenow", "synopsys", 
        "zscaler", "uber", "akamai", "analog devices", "three seasons wealth", "broadcom",
        "micron", "oracle", "ibm", "cisco", "dell", "hp"
    ]
    other_companies_in_title = [
        oc for oc in prominent_other_companies 
        if oc not in [a.lower() for a in aliases] and re.search(rf'\b{re.escape(oc)}\b', title_lower)
    ]
    is_about_other_company = bool(other_ticker_matches or other_companies_in_title)

    ticker_sentiment_list = article.get("ticker_sentiment", [])
    target_ticker_data = next((ts for ts in ticker_sentiment_list if ts.get("ticker", "").upper() == ticker.upper()), None)
    av_relevance = float(target_ticker_data.get("relevance_score", 0.0)) if target_ticker_data else 0.0

    is_portfolio_or_filing_story = any(k in title_lower for k in [
        "boosts stake", "shares sold", "acquires new shares", "stock holdings decreased", 
        "buys new shares", "position reduced", "holdings trimmed", "stake lifted", 
        "stake increased", "stock position cut", "sells stock in", "stock sold by", 
        "buys stock in", "holdings added", "increases holdings", "lowers holdings",
        "boosts stock holdings", "boosts holdings", "stock holdings", "holdings in",
        "buys shares", "trims stake", "reduces stake", "increases stake", "decreases stake",
        "holdings lifted", "holdings boosted", "raises stake",
        "form 4", "form 13f", "schedule 13"
    ])

    # Rule 1: Reject third-party portfolio/filing alerts when target company is not the headline subject
    if is_about_other_company and not has_target_in_title and is_portfolio_or_filing_story:
        return False, 0.0, f"Unrelated portfolio/filing story about {other_companies_in_title or other_ticker_matches}."

    # Rule 2: Related-company news must substantively discuss target company or products
    if is_about_other_company and not has_target_in_title:
        has_target_in_body = any(re.search(rf'\b{re.escape(alias)}\b', summary_lower) for alias in aliases) or f"${ticker.lower()}" in summary_lower
        has_substantive_context = has_target_in_body and any(re.search(rf'\b{re.escape(ctx)}\b', summary_lower) for ctx in related_context)
        if not has_substantive_context:
            return False, 0.0, f"Story primarily about {other_companies_in_title or other_ticker_matches} without substantive connection to {company}."
        score = 60.0 + (av_relevance * 20.0)
        return True, score, f"Substantive related-company coverage for {company}."

    # Rule 3: Direct headline coverage
    if has_target_in_title:
        score = 100.0 + (av_relevance * 30.0)
        return True, score, f"Primary headline coverage for {company}."

    # Rule 4: Body mention with material context
    has_target_in_body = any(re.search(rf'\b{re.escape(alias)}\b', summary_lower) for alias in aliases) or f"${ticker.lower()}" in summary_lower
    if has_target_in_body:
        has_context = any(re.search(rf'\b{re.escape(ctx)}\b', summary_lower) for ctx in related_context)
        if av_relevance >= 0.35 or has_context:
            score = 50.0 + (av_relevance * 25.0)
            return True, score, f"Substantive body coverage for {company}."
        return False, 0.0, f"Incidental mention of {company} in general market commentary."

    return False, 0.0, f"No material reference to {company} or its products."

def fetch_news_sentiment(ticker: str) -> List[Dict[str, Any]]:
    """
    Fetches NEWS_SENTIMENT endpoint from Alpha Vantage with caching and shared rate limiting.
    """
    today_str = datetime.date.today().isoformat()
    cache_file = get_cache_path(ticker, "NEWS_SENTIMENT", today_str)

    if cache_file.exists():
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                cached = json.load(f)
                feed_items = cached if isinstance(cached, list) else cached.get("feed", [])
                for item in feed_items:
                    item["_provenance"] = "cached"
                return feed_items[:50]
        except Exception:
            pass

    if not settings.ALPHA_VANTAGE_API_KEY:
        if not settings.ALLOW_MOCK_DATA:
            return [{
                "title": f"Live news feed unavailable for {ticker} (Alpha Vantage API key not configured)",
                "url": "",
                "time_published": "",
                "summary": "Alpha Vantage API key not configured. News retrieval unavailable.",
                "overall_sentiment_score": 0.0,
                "overall_sentiment_label": "Neutral",
                "source": "System",
                "_provenance": "unavailable"
            }]
        mock = _mock_news_fallback(ticker)
        for item in mock:
            item["_provenance"] = "mock_fixture"
        return mock

    try:
        rate_limiter.acquire()
        url = "https://www.alphavantage.co/query"
        params = {
            "function": "NEWS_SENTIMENT",
            "tickers": ticker,
            "limit": 50,
            "apikey": settings.ALPHA_VANTAGE_API_KEY
        }
        resp = requests.get(url, params=params, timeout=12)
        if resp.status_code == 200:
            data = resp.json()
            if "Note" in data or "Information" in data:
                print(f"Alpha Vantage News limit notice: {data.get('Note') or data.get('Information')}")
                if not settings.ALLOW_MOCK_DATA:
                    return [{
                        "title": f"Live news feed unavailable for {ticker} (Alpha Vantage rate limit reached)",
                        "url": "",
                        "time_published": "",
                        "summary": "Alpha Vantage rate limit reached. News retrieval unavailable.",
                        "overall_sentiment_score": 0.0,
                        "overall_sentiment_label": "Neutral",
                        "source": "System",
                        "_provenance": "unavailable"
                    }]
                mock = _mock_news_fallback(ticker)
                for item in mock:
                    item["_provenance"] = "mock_fixture"
                return mock

            feed = data.get("feed", [])
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(feed, f, indent=2)
            for item in feed:
                item["_provenance"] = "live"
            return feed[:50]
    except Exception as e:
        print(f"Error fetching news for {ticker}: {e}")

    if not settings.ALLOW_MOCK_DATA:
        return [{
            "title": f"Live news feed unavailable for {ticker} (network error)",
            "url": "",
            "time_published": "",
            "summary": "Network error communicating with Alpha Vantage news endpoint.",
            "overall_sentiment_score": 0.0,
            "overall_sentiment_label": "Neutral",
            "source": "System",
            "_provenance": "unavailable"
        }]
    mock = _mock_news_fallback(ticker)
    for item in mock:
        item["_provenance"] = "mock_fixture"
    return mock

def _mock_news_fallback(ticker: str) -> List[Dict[str, Any]]:
    """Curated recent financial news snapshots with sentiment scores if API quota is reached."""
    items = {
        "NVDA": [
            {
                "title": "NVIDIA Blackwell Architecture Ramps into High-Volume Data Center Shipments",
                "url": "https://nvidianews.nvidia.com",
                "time_published": "20260815T120000",
                "summary": "Enterprise cloud providers expand Hopper and Blackwell cluster deployments as AI computing demand accelerates.",
                "overall_sentiment_score": 0.42,
                "overall_sentiment_label": "Bullish",
                "source": "Financial Wire"
            },
            {
                "title": "Semiconductor Export Controls and Geopolitical Trade Compliance Update",
                "url": "https://reuters.com",
                "time_published": "20260810T090000",
                "summary": "U.S. Commerce Department reviews high-performance accelerator licensing rules for international markets.",
                "overall_sentiment_score": -0.18,
                "overall_sentiment_label": "Somewhat-Bearish",
                "source": "Tech Trade Report"
            }
        ],
        "AAPL": [
            {
                "title": "Apple Services Revenue Reaches Historic Record Driven by Cloud and Subscriptions",
                "url": "https://apple.com/newsroom",
                "time_published": "20260812T140000",
                "summary": "Services growth offset consumer hardware replacement cycles, boosting consolidated gross margin.",
                "overall_sentiment_score": 0.35,
                "overall_sentiment_label": "Bullish",
                "source": "Market Watch"
            },
            {
                "title": "European Digital Markets Act Compliance Scrutiny on App Store Fee Models",
                "url": "https://bloomberg.com",
                "time_published": "20260805T110000",
                "summary": "Regulators evaluate alternative marketplace fees and core technology commission structures.",
                "overall_sentiment_score": -0.25,
                "overall_sentiment_label": "Bearish",
                "source": "Regulatory Review"
            }
        ],
        "MSFT": [
            {
                "title": "Microsoft Cloud and Azure AI Revenue Exceeds Analyst Consensus",
                "url": "https://news.microsoft.com",
                "time_published": "20260814T100000",
                "summary": "Commercial cloud bookings accelerated with widespread Copilot enterprise license adoption.",
                "overall_sentiment_score": 0.38,
                "overall_sentiment_label": "Bullish",
                "source": "Cloud Insights"
            },
            {
                "title": "Microsoft Expands Capital Expenditures for Global Datacenter and Energy Capacity",
                "url": "https://wsj.com",
                "time_published": "20260808T150000",
                "summary": "Heightened infrastructure capex prompts investor analysis on long-term free cash flow margins.",
                "overall_sentiment_score": 0.05,
                "overall_sentiment_label": "Neutral",
                "source": "Wall Street Journal"
            }
        ]
    }
    return items.get(ticker, [])

def execute_news_research(state: FinSightState, sse_callback=None) -> Dict[str, Any]:
    """
    News Agent: retrieves articles, evaluates semantic company relevance,
    and extracts company-specific Alpha Vantage sentiment scores.
    """
    companies = state.get("companies", ["NVIDIA"])
    all_news: List[Dict[str, Any]] = list(state.get("news_evidence", []))

    for company in companies:
        ticker = get_ticker_for_company(company)
        if sse_callback:
            sse_callback({
                "agent": "news_research",
                "status": "fetching_news",
                "company": company,
                "ticker": ticker
            })

        feed = fetch_news_sentiment(ticker)
        company_articles: List[Dict[str, Any]] = []

        for article in feed:
            is_rel, rel_score, rel_reason = evaluate_news_article_relevance(article, company, target_ticker=ticker)
            if not is_rel:
                continue

            # Extract target-company-specific sentiment
            ticker_sentiment_list = article.get("ticker_sentiment", [])
            target_ts = next((ts for ts in ticker_sentiment_list if ts.get("ticker", "").upper() == ticker.upper()), None)
            if target_ts:
                try:
                    sentiment_score = float(target_ts.get("ticker_sentiment_score", 0.0))
                    sentiment_label = target_ts.get("ticker_sentiment_label", "Neutral")
                except (ValueError, TypeError):
                    sentiment_score = float(article.get("overall_sentiment_score", 0.0))
                    sentiment_label = str(article.get("overall_sentiment_label", "Neutral"))
            else:
                sentiment_score = float(article.get("overall_sentiment_score", 0.0))
                sentiment_label = str(article.get("overall_sentiment_label", "Neutral"))

            item = {
                "company": company,
                "ticker": ticker,
                "title": article.get("title", ""),
                "summary": article.get("summary", ""),
                "url": article.get("url", ""),
                "published": article.get("time_published", ""),
                "sentiment_score": sentiment_score,
                "sentiment_label": sentiment_label,
                "overall_sentiment_score": article.get("overall_sentiment_score", 0.0),
                "overall_sentiment_label": article.get("overall_sentiment_label", "Neutral"),
                "source": article.get("source", "Alpha Vantage News") if article.get("_provenance") != "mock_fixture" else f"{article.get('source', 'News Wire')} (Mock Fixture)",
                "provenance": article.get("_provenance", "unknown"),
                "is_relevant": True,
                "relevance_score": rel_score,
                "relevance_reason": rel_reason
            }
            company_articles.append(item)

        # Rank relevant articles by relevance_score descending so top primary coverage appears first
        company_articles.sort(key=lambda x: x.get("relevance_score", 0.0), reverse=True)
        for item in company_articles:
            if not any(n["title"] == item["title"] for n in all_news):
                all_news.append(item)

    return {
        "news_evidence": all_news
    }
