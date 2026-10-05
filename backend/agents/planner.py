import re
from typing import Dict, Any, List
from backend.config import settings
from backend.agents.llm_client import call_gemini, extract_json_from_llm
from backend.graph.state import FinSightState, CoverageLedgerEntry

KNOWN_COMPANIES = {
    "apple": "Apple",
    "aapl": "Apple",
    "microsoft": "Microsoft",
    "msft": "Microsoft",
    "nvidia": "NVIDIA",
    "nvda": "NVIDIA",
    "google": "Google",
    "alphabet": "Google",
    "googl": "Google",
    "goog": "Google",
    "amazon": "Amazon",
    "amzn": "Amazon",
    "meta": "Meta",
    "facebook": "Meta",
    "tesla": "Tesla",
    "tsla": "Tesla",
    "netflix": "Netflix",
    "nflx": "Netflix"
}

def detect_companies_from_query(query: str) -> List[str]:
    """
    Detects all companies mentioned in the query text.
    Does not default silently to an unrelated company.
    """
    q_lower = query.lower()
    detected = []
    for key, name in KNOWN_COMPANIES.items():
        if re.search(rf'\b{re.escape(key)}\b', q_lower):
            if name not in detected:
                detected.append(name)
    return detected

def query_mentions_risk_or_regulation(query: str) -> bool:
    """Checks if query keywords require Item 1A / Item 3 coverage."""
    keywords = ["risk", "regulatory", "regulation", "legal", "compliance", "litigation", "antitrust", "export control", "trade", "china", "europe", "eu"]
    q_lower = query.lower()
    return any(k in q_lower for k in keywords)

def classify_research_intent(query: str) -> Dict[str, Any]:
    """
    Deterministically classifies required retrieval capabilities:
    - market_data_required
    - news_required
    - sec_retrieval_required
    """
    q_lower = query.lower()
    
    # 1. Market Data Intent Keywords
    market_keywords = [
        "price", "price performance", "stock price", "stock performance", "valuation",
        "pe ratio", "p/e", "market cap", "market capitalization", "returns", "return",
        "volatility", "trading volume", "52-week", "52 week", "share price", "trading",
        "all-time high", "all time high", "ytd return"
    ]
    market_required = any(re.search(rf'\b{re.escape(k)}\b', q_lower) for k in market_keywords) or any(k in q_lower for k in ["price performance", "stock price", "stock performance", "pe ratio", "p/e ratio", "52-week", "valuation"])
    if "price" in q_lower and not ("price fixing" in q_lower or "transfer price" in q_lower):
        market_required = True

    # 2. News Intent Keywords
    news_keywords = [
        "news", "headline", "headlines", "sentiment", "catalyst", "catalysts",
        "recent event", "recent events", "breaking", "press release", "current events", "latest news"
    ]
    news_explicit = any(re.search(rf'\b{re.escape(k)}\b', q_lower) for k in news_keywords) or "news" in q_lower

    # 3. SEC Retrieval Keywords
    sec_keywords = [
        "revenue", "margin", "sales", "net sales", "segment", "10-k", "10-q", "8-k",
        "item 1a", "item 3", "item 7", "item 8", "filing", "filings", "sec",
        "annual", "quarterly", "growth", "risk", "risks", "regulatory", "regulation",
        "legal", "dma", "antitrust", "export control", "supply chain", "operating income",
        "operating margin", "gross margin", "net income", "balance sheet", "cash flow",
        "disclosed", "disclosures", "fiscal year", "fy202"
    ]
    sec_required = any(re.search(rf'\b{re.escape(k)}\b', q_lower) for k in sec_keywords) or any(k in q_lower for k in ["revenue", "margin", "filing", "annual", "quarterly", "item 1a", "item 3", "item 7", "item 8", "10-k", "10-q"])

    # 4. Joint Routing Rules:
    # "A query combining stock performance and risks should retrieve market data, relevant news, and SEC evidence."
    has_risk = any(k in q_lower for k in ["risk", "risks", "regulatory", "regulation", "legal", "antitrust", "export control", "dma"])
    if market_required and has_risk:
        news_required = True
        sec_required = True
    else:
        news_required = news_explicit

    # If completely unclassified, default to SEC retrieval as baseline
    if not market_required and not news_required and not sec_required:
        sec_required = True

    return {
        "market_data_required": bool(market_required),
        "news_required": bool(news_required),
        "sec_retrieval_required": bool(sec_required),
        "has_risk_focus": bool(has_risk)
    }

def split_query_into_clauses(query: str) -> List[str]:
    """
    Decomposes a complex financial query into distinct functional clauses.
    Splits across colons, semicolons, commas, and conjunctions ('and', 'plus', 'across', 'with').
    """
    cleaned = query.strip()
    parts = re.split(r'[,:;]|\band\b|\balso\b|\bplus\b|\bwith\b|\bacross\b', cleaned, flags=re.IGNORECASE)
    clauses = []
    for p in parts:
        c = p.strip()
        c = re.sub(r'^[\s,.-]+|[\s,.-]+$', '', c)
        if len(c) > 6 and not re.match(r'^(compare|analyze|evaluate|review|assess|performance)$', c.lower()):
            clauses.append(c)
    
    if not clauses:
        clauses = [query]
    return clauses

def build_task_from_clause(company: str, clause: str, query: str, idx: int) -> Dict[str, Any]:
    """
    Deterministically constructs a company-aware, topic-specific task from a clause.
    Guarantees no cross-company contamination (e.g. Apple terms on NVIDIA).
    """
    c_lower = clause.lower()
    q_lower = query.lower()
    
    # 1. Market Data (Valuation, Price, Price Performance, P/E, Returns, Volatility)
    # Evaluated with high priority to avoid mistaking stock price for financial statements
    if any(k in c_lower for k in ["price", "price performance", "performance", "valuation", "pe ratio", "p/e", "market cap", "stock", "return", "returns", "volatility", "52-week"]) and not any(k in c_lower for k in ["revenue", "sales", "gross margin"]):
        return {
            "id": f"task_{idx:03d}",
            "clause": clause,
            "sub_question": f"Retrieve current market valuation, stock price performance, 52-week range, and P/E ratio for {company}.",
            "company": company,
            "agent": "market_data",
            "category": "market_data",
            "required_data_sources": ["market_telemetry"],
            "required_doc_types": ["market_feed"],
            "required_sections": ["quote", "overview"],
            "required_evidence_type": "market_telemetry",
            "required_metrics": ["latest_price", "change_percent", "52_week_high", "52_week_low", "pe_ratio"],
            "expected_output": f"Current stock price, percent change, 52-week trading range, and P/E ratio for {company}.",
            "completeness_conditions": "Latest market price, percentage return, and valuation metrics verified.",
            "semantic_keywords": ["price", "pe ratio", "market cap", "%", "$"]
        }

    # 2. News / Market Sentiment / Recent Catalysts
    if any(k in c_lower for k in ["news", "sentiment", "headlines", "recent events", "catalyst", "press release", "breaking"]):
        return {
            "id": f"task_{idx:03d}",
            "clause": clause,
            "sub_question": f"Review recent financial news coverage, major catalysts, and market sentiment for {company}.",
            "company": company,
            "agent": "news_research",
            "category": "news",
            "required_data_sources": ["news_feed"],
            "required_doc_types": ["news_feed"],
            "required_sections": ["headlines"],
            "required_evidence_type": "news_sentiment",
            "required_metrics": ["title", "published", "sentiment_score", "sentiment_label"],
            "expected_output": f"Recent headlines, publication dates, and sentiment scores for {company}.",
            "completeness_conditions": "Headline titles and sentiment scores retrieved from news feed.",
            "semantic_keywords": ["news", "sentiment", "catalyst"]
        }

    # 3. Revenue / Segment Trajectory
    if any(k in c_lower for k in ["revenue", "sales", "net sales", "segment", "growth", "growth trajectory", "trajectory"]):
        if company == "Apple" and "services" in (c_lower + " " + q_lower):
            sub_q = f"Analyze Apple's Services revenue growth trajectory over the latest three fiscal years (FY2023–FY2025)."
            kws = ["services", "revenue", "growth", "FY2023", "FY2024", "FY2025"]
        elif company == "NVIDIA" and "data center" in (c_lower + " " + q_lower):
            sub_q = f"Analyze NVIDIA's Data Center revenue trajectory across recent fiscal quarters and years."
            kws = ["data center", "compute", "revenue", "growth", "networking"]
        elif company == "Microsoft" and ("azure" in c_lower or "cloud" in c_lower):
            sub_q = f"Evaluate Microsoft's Azure and Intelligent Cloud revenue growth trajectory."
            kws = ["azure", "cloud", "intelligent cloud", "revenue", "growth"]
        else:
            sub_q = f"Analyze {company}'s revenue growth trajectory and segment performance."
            kws = ["revenue", "net sales", "growth"]

        return {
            "id": f"task_{idx:03d}",
            "clause": clause,
            "sub_question": sub_q,
            "company": company,
            "agent": "financial_research",
            "category": "financial_performance",
            "required_data_sources": ["sec_filings"],
            "required_doc_types": ["10-K", "10-Q"],
            "required_sections": ["Item 7", "Item 8"],
            "required_evidence_type": "financial_metric",
            "required_metrics": ["revenue", "growth_rate", "reporting_periods"],
            "expected_output": f"Audited segment and total revenue figures across fiscal periods with verified growth percentages.",
            "completeness_conditions": "Revenue numbers and corresponding fiscal periods verified in SEC filings.",
            "semantic_keywords": kws
        }

    # 4. Margin (Gross margin vs Operating margin)
    if "margin" in c_lower:
        is_operating = "operating margin" in c_lower or "operating margin" in q_lower
        if is_operating:
            sub_q = f"Assess {company}'s operating margin trend across recent fiscal periods."
            kws = ["operating margin", "operating income", "%"]
        elif company == "Apple":
            sub_q = f"Assess Apple's Services gross margin and total company gross margin trends over the latest three fiscal years (FY2023–FY2025)."
            kws = ["gross margin", "services gross margin", "%", "FY2023", "FY2024", "FY2025"]
        else:
            sub_q = f"Assess {company}'s gross margin trend across recent reporting periods."
            kws = ["gross margin", "GAAP gross margin", "%"]

        return {
            "id": f"task_{idx:03d}",
            "clause": clause,
            "sub_question": sub_q,
            "company": company,
            "agent": "financial_research",
            "category": "financial_performance",
            "required_data_sources": ["sec_filings"],
            "required_doc_types": ["10-K", "10-Q"],
            "required_sections": ["Item 7", "Item 8"],
            "required_evidence_type": "financial_metric",
            "required_metrics": ["gross_margin", "operating_margin", "%"],
            "expected_output": f"Gross or operating margin percentages across comparative fiscal periods.",
            "completeness_conditions": "Margin percentages and comparison periods verified in SEC filings.",
            "semantic_keywords": kws
        }

    # 5. Export Controls / China Geopolitical Risks
    if any(k in c_lower for k in ["export", "china", "trade", "geopolitical", "licensing", "sanction"]):
        return {
            "id": f"task_{idx:03d}",
            "clause": clause,
            "sub_question": f"Evaluate export-control restrictions, licensing requirements, and regulatory risks affecting {company}'s operations in China.",
            "company": company,
            "agent": "financial_research",
            "category": "risk",
            "required_data_sources": ["sec_filings"],
            "required_doc_types": ["10-K", "10-Q"],
            "required_sections": ["Item 1A", "Item 7"],
            "required_evidence_type": "regulatory_disclosure",
            "required_metrics": ["risk_factors", "licensing_impact", "geopolitical_scope"],
            "expected_output": f"Item 1A risk disclosures regarding trade sanctions, EAR, and BIS export restrictions.",
            "completeness_conditions": "Regulatory disclosures identified with Item 1A or Item 7 citations.",
            "semantic_keywords": ["export controls", "China", "license", "BIS", "Item 1A"]
        }

    # 6. European Regulatory Risks / Legal Proceedings
    if any(k in c_lower for k in ["europe", "european", "eu", "dma", "antitrust"]):
        return {
            "id": f"task_{idx:03d}",
            "clause": clause,
            "sub_question": f"Identify and evaluate regulatory risk factors disclosed in Item 1A and legal proceedings in Item 3 affecting {company} in European markets.",
            "company": company,
            "agent": "financial_research",
            "category": "risk",
            "required_data_sources": ["sec_filings"],
            "required_doc_types": ["10-K", "10-Q"],
            "required_sections": ["Item 1A", "Item 3"],
            "required_evidence_type": "risk_factor",
            "required_metrics": ["dma_compliance", "legal_proceedings", "fines"],
            "expected_output": f"Item 1A and Item 3 European antitrust and regulatory disclosures.",
            "completeness_conditions": "Direct disclosures regarding EU regulatory scrutiny and legal proceedings.",
            "semantic_keywords": ["regulatory", "European", "Europe", "Item 1A", "Item 3", "antitrust"]
        }

    # 7. Supply Chain / Foundry Dependencies
    if any(k in c_lower for k in ["supply chain", "dependencies", "foundry", "semiconductor", "concentration"]):
        return {
            "id": f"task_{idx:03d}",
            "clause": clause,
            "sub_question": f"Assess semiconductor supply chain dependencies, foundry concentration, and vendor risks for {company}.",
            "company": company,
            "agent": "financial_research",
            "category": "risk",
            "required_data_sources": ["sec_filings"],
            "required_doc_types": ["10-K", "10-Q"],
            "required_sections": ["Item 1A", "Item 7"],
            "required_evidence_type": "risk_factor",
            "required_metrics": ["supplier_concentration", "foundry_risks"],
            "expected_output": f"Item 1A supply chain and manufacturing concentration disclosures.",
            "completeness_conditions": "Supply chain dependencies and risks identified in filings.",
            "semantic_keywords": ["supply chain", "foundry", "concentration", "Item 1A"]
        }

    # 8. General Risk (if risk is in clause)
    if any(k in c_lower for k in ["risk", "risks", "threat", "uncertainty"]):
        return {
            "id": f"task_{idx:03d}",
            "clause": clause,
            "sub_question": f"Analyze principal business, market, and regulatory risk factors disclosed for {company}.",
            "company": company,
            "agent": "financial_research",
            "category": "risk",
            "required_data_sources": ["sec_filings"],
            "required_doc_types": ["10-K", "10-Q"],
            "required_sections": ["Item 1A"],
            "required_evidence_type": "risk_factor",
            "required_metrics": ["principal_risks"],
            "expected_output": f"Item 1A risk factor disclosures for {company}.",
            "completeness_conditions": "Item 1A risk disclosures identified.",
            "semantic_keywords": ["risk", "Item 1A", "uncertainty"]
        }

    # Default Financial Research
    return {
        "id": f"task_{idx:03d}",
        "clause": clause,
        "sub_question": f"Analyze disclosures for {company} regarding {clause}.",
        "company": company,
        "agent": "financial_research",
        "category": "financial_performance",
        "required_data_sources": ["sec_filings"],
        "required_doc_types": ["10-K", "10-Q"],
        "required_sections": ["Item 7", "Item 8"],
        "required_evidence_type": "financial_metric",
        "required_metrics": ["financial_disclosures"],
        "expected_output": f"Financial disclosures answering {clause}.",
        "completeness_conditions": "Disclosures verified from SEC filings.",
        "semantic_keywords": ["financial", "disclosures"]
    }

def infer_clause_requirements(clause: str, query: str) -> Dict[str, Any]:
    task = build_task_from_clause("Target Company", clause, query, 1)
    return {
        "required_data_sources": task.get("required_data_sources", ["sec_filings"]),
        "required_doc_types": task.get("required_doc_types", ["10-K"]),
        "required_sections": task.get("required_sections", ["Item 7"]),
        "required_evidence_type": task.get("required_evidence_type", "financial_metric"),
        "semantic_keywords": task.get("semantic_keywords", [])
    }

PLANNER_SYSTEM_PROMPT = """You are an elite Senior Financial Research Analyst and Research Director.
Your job is to decompose user financial queries into precise, targeted sub-tasks for specialized research agents:
- 'financial_research': Historical SEC filings (10-K, 10-Q, 8-K), revenue, margins, segment breakdown, balance sheet, MD&A, cash flows, and Item 1A/3 risk/regulatory disclosures.
- 'market_data': Stock price, recent returns, volatility, valuation metrics, PE ratio, 52-week ranges (ONLY if query asks for market valuation/pricing/performance).
- 'news_research': Recent press releases, news headlines, market sentiment, product announcements (ONLY if query asks for news/sentiment/recent developments).
- 'risk': Risk factors (Item 1A), regulatory risks, supply chain risks, competition, legal challenges.

MANDATORY RULES:
1. Clause-by-Clause Decomposition: Emit ONE TASK PER CLAUSE of the user query. Do NOT add extraneous tasks or unrequested requirements.
2. Capability Alignment: If the user asks for stock price performance, assign agent='market_data' and category='market_data'. If they ask for news, assign agent='news_research' and category='news'. If they ask for financial filings or revenue, assign agent='financial_research' and category='financial_performance' or 'risk'.
3. Multi-Company: When the query names multiple companies (e.g. NVIDIA and Apple), you MUST identify ALL companies and produce separate per-company sub-tasks.
4. For each task, specify:
   - "clause": The query phrase this task addresses
   - "sub_question": Explicit research question directly answering the clause
   - "company": Target company
   - "category": "financial_performance" | "risk" | "market_data" | "news"
   - "agent": "financial_research" | "market_data" | "news_research"
   - "required_data_sources": ["sec_filings"] | ["market_telemetry"] | ["news_feed"]
   - "required_doc_types": ["10-K", "10-Q"] or ["market_feed"] or ["news_feed"]
   - "required_sections": ["Item 7", "Item 8"] or ["Item 1A", "Item 3"] or ["quote", "overview"] or ["headlines"]
   - "required_evidence_type": "financial_metric" | "risk_factor" | "regulatory_disclosure" | "market_telemetry" | "news_sentiment"
   - "semantic_keywords": Specific terms required in findings

Output valid JSON ONLY matching the schema:
{
  "companies": ["NVIDIA"],
  "tasks": [
    {
      "id": "task_001",
      "clause": "Data Center revenue growth",
      "sub_question": "Analyze NVIDIA's Data Center revenue growth trajectory across recent fiscal years.",
      "company": "NVIDIA",
      "agent": "financial_research",
      "category": "financial_performance",
      "required_data_sources": ["sec_filings"],
      "required_doc_types": ["10-K", "10-Q"],
      "required_sections": ["Item 7", "Item 8"],
      "required_evidence_type": "financial_metric",
      "semantic_keywords": ["revenue", "data center", "$", "billion"]
    }
  ]
}
"""

def plan_research(state: FinSightState, sse_callback=None) -> Dict[str, Any]:
    """
    Planner Agent: Decomposes the user query into clause-targeted tasks,
    classifies research intent independently, constructs the mandatory Coverage Ledger,
    and enforces deterministic routing safeguards.
    """
    query = state.get("query") or state.get("user_query") or ""
    affected_categories = state.get("affected_categories", [])
    affected_tasks = state.get("affected_tasks", [])
    existing_companies = state.get("companies", [])
    existing_tasks = state.get("tasks", [])
    existing_ledger = state.get("coverage_ledger", [])

    detected_companies = detect_companies_from_query(query)
    companies = existing_companies or detected_companies

    # If no known company was matched by dictionary, try extracting candidate company from query patterns
    # e.g. "price performance of Google", "valuation of Snowflake", "AcmeCorp's stock"
    if not companies:
        cand_match = re.search(r'\b(?:of|for|on|about)\s+([A-Za-z0-9\.\-&]+)\b', query, re.IGNORECASE)
        poss_match = re.search(r'\b([A-Za-z0-9\.\-&]+)\'s\b', query, re.IGNORECASE)
        cand = None
        if cand_match:
            c = cand_match.group(1).strip()
            if c.lower() not in ["the", "a", "an", "this", "that", "recent", "its", "our", "q1", "q2", "q3", "q4", "fy2023", "fy2024", "fy2025"]:
                cand = c
        elif poss_match:
            c = poss_match.group(1).strip()
            if c.lower() not in ["the", "today", "yesterday"]:
                cand = c
        if cand:
            companies = [cand.title() if cand.islower() else cand]

    # 1. Independent Deterministic Intent Classification
    intent = classify_research_intent(query)
    market_data_required = intent["market_data_required"]
    news_required = intent["news_required"]
    sec_retrieval_required = intent["sec_retrieval_required"]
    has_risk_focus = intent["has_risk_focus"]

    tasks: List[Dict[str, Any]] = []

    # If this is surgical replanning for specific affected tasks or categories
    if affected_tasks or affected_categories:
        prompt = f"""Targeted Re-Planning Request:
Original Query: {query}
Target Companies: {companies if companies else 'Identify from query'}
Affected Task IDs: {affected_tasks}
Affected Categories: {affected_categories}
Risk/Regulation Focus: {has_risk_focus}

Generate replacement sub-tasks ONLY for the affected tasks/categories. Preserve clause targeting and keep requirements specific to the query.
"""
    else:
        prompt = f"""New Research Request:
User Query: {query}
Target Companies Identified: {companies if companies else 'Identify target company from user query'}
Required Capabilities:
- Market Data Required: {market_data_required}
- News Required: {news_required}
- SEC Retrieval Required: {sec_retrieval_required}
- Risk/Regulation Focus: {has_risk_focus}

Emit one task per clause of the query for each target company.
If Market Data is required, emit a market_data task (agent='market_data').
If News is required, emit a news task (agent='news_research').
If SEC Retrieval is required, emit financial_research or risk tasks (agent='financial_research').
Do not add unrequested capabilities or extraneous tasks.
"""

    run_id = state.get("run_id")
    response_text = call_gemini(
        prompt, 
        system_instruction=PLANNER_SYSTEM_PROMPT,
        model=settings.MODEL_PLANNER,
        run_id=run_id,
        component="planner"
    )

    try:
        parsed = extract_json_from_llm(response_text, run_id=run_id)
        llm_companies = parsed.get("companies", [])
        if llm_companies:
            companies = llm_companies
        raw_tasks = parsed.get("tasks", [])
        if raw_tasks:
            tasks = raw_tasks
    except Exception as e:
        print(f"Planner LLM notice: {e}. Running deterministic clause decomposition.")

    if not companies:
        companies = ["NVIDIA"]

    # Fallback deterministic decomposition if LLM returned empty or malformed tasks
    if not tasks:
        clauses = split_query_into_clauses(query)
        task_counter = 1
        for comp in companies:
            for clause in clauses:
                other_comps = [c for c in companies if c != comp]
                if any(oc.lower() in clause.lower() for oc in other_comps):
                    continue

                task_obj = build_task_from_clause(comp, clause, query, task_counter)
                tasks.append(task_obj)
                task_counter += 1

    # Deterministic Routing Safeguards (Section 2 & 3)
    # 1. Market Data Activation Safeguard
    if market_data_required:
        has_market_task = any(t.get("category") == "market_data" or t.get("agent") == "market_data" for t in tasks)
        if not has_market_task:
            for comp in companies:
                m_task = build_task_from_clause(comp, f"current {comp} stock price performance and market valuation", query, len(tasks) + 1)
                tasks.append(m_task)

    # 2. News Activation Safeguard
    if news_required:
        has_news_task = any(t.get("category") == "news" or t.get("agent") == "news_research" for t in tasks)
        if not has_news_task:
            for comp in companies:
                n_task = build_task_from_clause(comp, f"recent {comp} news and market catalysts", query, len(tasks) + 1)
                tasks.append(n_task)

    # 3. SEC Retrieval Safeguard
    if not sec_retrieval_required:
        # Strip extraneous SEC research tasks when query is purely market data or news
        tasks = [t for t in tasks if t.get("category") in ["market_data", "news"]]
    else:
        # Ensure at least one SEC task exists if SEC retrieval is required
        has_sec_task = any(t.get("category") in ["financial_performance", "risk"] for t in tasks)
        if not has_sec_task:
            for comp in companies:
                default_clause = "disclosures and risks" if has_risk_focus else "financial performance and revenue"
                s_task = build_task_from_clause(comp, default_clause, query, len(tasks) + 1)
                tasks.append(s_task)

    # Guarantee required fields for all tasks and align agents & data sources
    sanitized_tasks: List[Dict[str, Any]] = []
    for idx, t in enumerate(tasks, 1):
        t["id"] = f"task_{idx:03d}"
        if not t.get("company"):
            t["company"] = companies[0] if companies else "Target Company"

        t_sub_q = t.get("sub_question", "")
        c_clause = t.get("clause", "")
        c_combined = (c_clause + " " + t_sub_q).lower()
        comp = t.get("company", "")

        # Reconcile category and agent
        if t.get("category") == "market_data" or any(k in c_combined for k in ["stock price", "price performance", "valuation", "pe ratio", "52-week", "returns"]):
            t["category"] = "market_data"
            t["agent"] = "market_data"
            t["required_data_sources"] = ["market_telemetry"]
            t["required_doc_types"] = ["market_feed"]
            t["required_sections"] = ["quote", "overview"]
            t["required_evidence_type"] = "market_telemetry"
            t["required_metrics"] = ["latest_price", "change_percent", "52_week_high", "52_week_low", "pe_ratio"]
            t["semantic_keywords"] = list(dict.fromkeys(t.get("semantic_keywords", []) + ["price", "$", "%", "pe ratio"]))
        elif t.get("category") == "news" or any(k in c_combined for k in ["news", "headlines", "recent events", "sentiment", "catalyst"]):
            t["category"] = "news"
            t["agent"] = "news_research"
            t["required_data_sources"] = ["news_feed"]
            t["required_doc_types"] = ["news_feed"]
            t["required_sections"] = ["headlines"]
            t["required_evidence_type"] = "news_sentiment"
            t["required_metrics"] = ["title", "published", "sentiment_score", "sentiment_label"]
            t["semantic_keywords"] = list(dict.fromkeys(t.get("semantic_keywords", []) + ["news", "sentiment"]))
        else:
            if not t.get("agent"):
                t["agent"] = "financial_research"
            if not t.get("required_data_sources"):
                t["required_data_sources"] = ["sec_filings"]
            if not t.get("required_doc_types"):
                inferred = infer_clause_requirements(t_sub_q, query)
                t["required_doc_types"] = inferred["required_doc_types"]
            if not t.get("required_sections"):
                inferred = infer_clause_requirements(t_sub_q, query)
                t["required_sections"] = inferred["required_sections"]
            if not t.get("required_evidence_type"):
                inferred = infer_clause_requirements(t_sub_q, query)
                t["required_evidence_type"] = inferred["required_evidence_type"]
            if not t.get("semantic_keywords"):
                inferred = infer_clause_requirements(t_sub_q, query)
                t["semantic_keywords"] = inferred["semantic_keywords"]

            # Augment semantic keywords and only supply fallback sub_question if missing
            has_sub_q = bool(t.get("sub_question") and len(t["sub_question"].strip()) >= 15)

            if comp == "Apple" and "services" in c_combined and any(k in c_combined for k in ["revenue", "sales", "growth"]):
                if not has_sub_q:
                    t["sub_question"] = "Analyze Apple's Services revenue growth trajectory over the latest three fiscal years (FY2023–FY2025)."
                t["semantic_keywords"] = list(dict.fromkeys(t.get("semantic_keywords", []) + ["FY2023", "FY2024", "FY2025", "services", "revenue", "growth"]))
            elif comp == "NVIDIA" and any(k in c_combined for k in ["data center", "datacenter", "revenue trajectory"]):
                if not has_sub_q:
                    t["sub_question"] = "Analyze NVIDIA's Data Center revenue trajectory across recent fiscal quarters and years."
                t["semantic_keywords"] = list(dict.fromkeys(t.get("semantic_keywords", []) + ["data center", "compute", "revenue", "growth"]))
            elif comp == "Microsoft" and any(k in c_combined for k in ["azure", "cloud"]):
                if not has_sub_q:
                    t["sub_question"] = "Evaluate Microsoft's Azure and Intelligent Cloud revenue growth trajectory."
                t["semantic_keywords"] = list(dict.fromkeys(t.get("semantic_keywords", []) + ["azure", "cloud", "intelligent cloud", "growth"]))

            # Company-specific margin trends
            if "operating margin" in c_combined:
                if not has_sub_q:
                    t["sub_question"] = f"Assess {comp}'s operating margin trend across recent fiscal periods."
                t["semantic_keywords"] = list(dict.fromkeys(t.get("semantic_keywords", []) + ["operating margin", "operating income", "%"]))
            elif "margin" in c_combined:
                if not has_sub_q:
                    if comp == "Apple":
                        t["sub_question"] = "Assess Apple's Services gross margin and total company gross margin trends over the latest three fiscal years (FY2023–FY2025)."
                    elif comp == "NVIDIA":
                        t["sub_question"] = "Assess NVIDIA's gross margin trend across recent fiscal periods."
                    else:
                        t["sub_question"] = f"Assess {comp}'s gross margin trend across recent fiscal periods."
                t["semantic_keywords"] = list(dict.fromkeys(t.get("semantic_keywords", []) + ["gross margin", "%"]))

            # Regulatory and export disclosures
            if any(k in c_combined for k in ["export", "china", "trade", "geopolitical", "licensing", "sanction"]):
                if not has_sub_q:
                    t["sub_question"] = f"Evaluate export-control restrictions, licensing requirements, and regulatory risks affecting {comp}'s operations in China."
                t["category"] = "risk"
                t["required_sections"] = list(dict.fromkeys(t.get("required_sections", []) + ["Item 1A", "Item 7"]))
                t["semantic_keywords"] = list(dict.fromkeys(t.get("semantic_keywords", []) + ["export control", "China", "license", "BIS", "Item 1A"]))
            elif any(k in c_combined for k in ["europe", "european", "eu", "dma", "antitrust"]):
                if not has_sub_q:
                    t["sub_question"] = f"Identify and evaluate regulatory risk factors disclosed in Item 1A and legal proceedings in Item 3 affecting {comp} in European markets."
                t["category"] = "risk"
                t["required_sections"] = list(dict.fromkeys(t.get("required_sections", []) + ["Item 1A", "Item 3"]))
                t["required_doc_types"] = list(dict.fromkeys(t.get("required_doc_types", []) + ["10-K", "10-Q"]))
                t["semantic_keywords"] = list(dict.fromkeys(t.get("semantic_keywords", []) + ["regulatory", "European", "Europe", "Item 1A", "Item 3", "antitrust"]))

        sanitized_tasks.append(t)

    tasks = sanitized_tasks

    # Synchronize Coverage Ledger
    coverage_ledger: List[CoverageLedgerEntry] = []
    existing_ledger_map = {e["task_id"]: e for e in existing_ledger}

    for t in tasks:
        tid = t["id"]
        if tid in existing_ledger_map:
            coverage_ledger.append(existing_ledger_map[tid])
        else:
            entry: CoverageLedgerEntry = {
                "task_id": tid,
                "task": t.get("sub_question") or t.get("clause", ""),
                "company": t["company"],
                "required_data_sources": t.get("required_data_sources", ["sec_filings"]),
                "required_doc_types": t.get("required_doc_types", ["10-K"]),
                "required_sections": t.get("required_sections", []),
                "required_evidence_type": t.get("required_evidence_type", "financial_metric"),
                "semantic_keywords": t.get("semantic_keywords", []),
                "evidence_retrieved": [],
                "final_finding": None,
                "finding_id": None,
                "qc_status": "PENDING",
                "evidence_limitation": None
            }
            coverage_ledger.append(entry)

    if sse_callback:
        sse_callback({
            "agent": "planner",
            "status": "plan_created",
            "tasks_count": len(tasks),
            "companies": companies,
            "coverage_ledger": coverage_ledger,
            "intent": intent
        })

    return {
        "companies": companies,
        "market_data_required": market_data_required,
        "news_required": news_required,
        "sec_retrieval_required": sec_retrieval_required,
        "intent_classification": intent,
        "tasks": tasks,
        "coverage_ledger": coverage_ledger,
        "run_status": "retrieving"
    }

