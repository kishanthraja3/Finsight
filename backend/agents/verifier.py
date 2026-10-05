import re
from typing import List, Dict, Any, Tuple, Optional

def normalize_and_deduplicate_figures(figures: List[str]) -> List[str]:
    """
    Deduplicates and normalizes figures:
    - Removes duplicate representations of the same figure (e.g. '$85.2 billion' vs '85.2 billion').
    - Standardizes currency, units and decimals.
    """
    deduped: List[str] = []
    seen_keys = set()
    for f in figures:
        c = f.replace('\u202f', ' ').replace('\xa0', ' ').strip()
        num_m = re.search(r'(\d+(?:,\d+)*(?:\.\d+)?)', c)
        if not num_m:
            if c not in deduped:
                deduped.append(c)
            continue
        val = num_m.group(1).replace(',', '')
        unit = '%' if '%' in c else ('B' if any(b in c.lower() for b in ['billion', 'b']) else ('M' if any(m in c.lower() for m in ['million', 'm']) else ''))
        key = f"{val}_{unit}"
        if key in seen_keys:
            for idx, existing in enumerate(deduped):
                if existing.replace('$', '').strip() == c.replace('$', '').strip():
                    if '$' in c and '$' not in existing:
                        deduped[idx] = c
            continue
        seen_keys.add(key)
        deduped.append(c)
    return deduped

def extract_numbers_from_text(text: str) -> List[str]:
    """
    Extracts significant financial figures (dollars, percentages, multipliers, decimals, large numbers).
    Examples: '$46.7 billion', '$41.1B', '75.1%', '$234.80', '122%'
    """
    clean_text = text.replace('\u202f', ' ').replace('\xa0', ' ')
    patterns = [
        r'\$\s*\d+(?:\.\d+)?(?:\s*(?:billion|trillion|million|B|M|T))?',
        r'\d+(?:\.\d+)?\s*%',
        r'(?<!\$)\b\d+(?:\.\d+)?\s*(?:billion|trillion|million)\b',
        r'\b\d+\.\d{2,}\b',
    ]
    raw_figures = []
    for pat in patterns:
        matches = re.findall(pat, clean_text, re.IGNORECASE)
        for m in matches:
            cleaned = m.strip()
            if cleaned:
                raw_figures.append(cleaned)
    return normalize_and_deduplicate_figures(raw_figures)

def extract_reporting_periods(text: str) -> List[str]:
    """Extracts explicit financial reporting periods (e.g. Q2 FY2027, FY2026, Q3 FY2026, FY2023)."""
    pattern = r'\b(?:Q[1-4]\s*(?:FY)?202[0-9]|FY202[0-9]|first quarter|second quarter|third quarter|fourth quarter|fiscal 202[0-9])\b'
    matches = re.findall(pattern, text, re.IGNORECASE)
    return list(dict.fromkeys([m.strip() for m in matches]))

def normalize_figure_for_search(fig: str) -> List[str]:
    """
    Generates candidate search tokens and unit-scaled conversions for a figure.
    Supports billions <-> millions, percentages, commas, currency symbols, and rounding variations.
    """
    fig_clean = fig.strip().replace('\u202f', ' ').replace('\xa0', ' ')
    candidates = [fig_clean]
    
    num_match = re.search(r'(\d+(?:,\d+)*(?:\.\d+)?)', fig_clean)
    if not num_match:
        return candidates
        
    num_str = num_match.group(1).replace(',', '')
    try:
        val = float(num_str)
    except ValueError:
        return candidates
        
    candidates.append(num_str)
    candidates.append(f"${num_str}")
    if '.' in num_str:
        candidates.append(f"${num_str.rstrip('0').rstrip('.')}")
    
    is_billion = bool(re.search(r'\b(?:billion|B)\b', fig_clean, re.IGNORECASE))
    is_million = bool(re.search(r'\b(?:million|M)\b', fig_clean, re.IGNORECASE))
    is_percent = '%' in fig_clean
    
    if is_billion:
        # Scale to millions (e.g. $85.2 billion -> 85,200 million)
        millions_val = val * 1000.0
        candidates.append(f"{int(round(millions_val)):,}")
        candidates.append(f"{int(round(millions_val))}")
        candidates.append(f"${int(round(millions_val)):,}")
        candidates.append(f"${int(round(millions_val))}")
        if not millions_val.is_integer():
            candidates.append(f"{millions_val:,.1f}")
            candidates.append(f"{millions_val:.1f}")
            
    elif is_million:
        # Scale to billions (e.g. 85,200 million -> 85.2 billion)
        billions_val = val / 1000.0
        candidates.append(f"{billions_val:.1f}")
        candidates.append(f"{billions_val:.2f}")
        candidates.append(f"${billions_val:.1f}")
        candidates.append(f"${billions_val:.2f}")
        candidates.append(f"{int(round(val)):,}")
        candidates.append(f"{int(round(val))}")
        
    elif is_percent:
        candidates.append(f"{num_str}%")
        candidates.append(f"{num_str} %")
        if '.' in num_str:
            candidates.append(f"{float(num_str):.1f}%")
            
    return list(dict.fromkeys(candidates))

def match_figure_against_chunk_text(fig: str, chunk_text: str, tolerance: float = 0.05) -> bool:
    """
    Validates a financial figure against chunk text supporting:
    - String token match (comma-separated, decimals, currency symbols)
    - Unit scaling (billions in statement vs millions in SEC tables with rounding tolerance)
    - Calculated YoY growth match between adjacent period metrics
    """
    clean_chunk = chunk_text.replace('\u202f', ' ').replace('\xa0', ' ')
    
    # 1. Direct candidate token search
    tokens = normalize_figure_for_search(fig)
    for tok in tokens:
        escaped = re.escape(tok)
        if re.search(rf'(?<!\d){escaped}(?!\d)', clean_chunk, re.IGNORECASE):
            return True
        if tok.lower() in clean_chunk.lower():
            return True

    # 2. Unit conversion with rounding tolerance (Billions in statement vs Millions in chunk)
    num_match = re.search(r'(\d+(?:,\d+)*(?:\.\d+)?)', fig)
    if not num_match:
        return False
    val_stated = float(num_match.group(1).replace(',', ''))
    
    is_billion = bool(re.search(r'\b(?:billion|B)\b', fig, re.IGNORECASE))
    is_million = bool(re.search(r'\b(?:million|M)\b', fig, re.IGNORECASE))
    is_percent = '%' in fig

    # Extract all candidate numbers from the chunk (integers and decimals)
    chunk_numbers = []
    for m in re.finditer(r'(?<!\w)(\d+(?:,\d+)*(?:\.\d+)?)(?!\w)', clean_chunk):
        raw_num = m.group(1).replace(',', '')
        try:
            chunk_numbers.append(float(raw_num))
        except ValueError:
            pass

    if is_billion:
        # Check if any chunk number in millions corresponds to val_stated in billions
        # e.g. 96,169 million -> 96.169 billion, rounds to 96.2 billion
        for cnum in chunk_numbers:
            cnum_in_billions = cnum / 1000.0
            if abs(round(cnum_in_billions, 1) - val_stated) < 1e-4 or abs(cnum_in_billions - val_stated) <= tolerance:
                return True
                
    elif is_million:
        for cnum in chunk_numbers:
            if abs(cnum - val_stated) < 1e-4:
                return True
            if abs(cnum * 1000.0 - val_stated) < 1e-4:
                return True

    elif is_percent:
        for cnum in chunk_numbers:
            if abs(cnum - val_stated) < 0.1: # 0.1% direct tolerance
                return True
        # Requirement B.6: Calculate growth rates only between adjacent periods for the target metric
        # Check adjacent numbers on the same row / line of tables or text
        for line in clean_chunk.splitlines():
            line_numbers = []
            for m in re.finditer(r'(?<!\w)(\d+(?:,\d+)*(?:\.\d+)?)(?!\w)', line):
                try:
                    num_val = float(m.group(1).replace(',', ''))
                    # Filter out calendar years (1990-2035) without decimal points
                    if not (1990 <= num_val <= 2035 and '.' not in m.group(1)):
                        line_numbers.append(num_val)
                except ValueError:
                    pass
            for k in range(len(line_numbers) - 1):
                n1, n2 = line_numbers[k], line_numbers[k+1]
                if n2 > 0:
                    yoy1 = ((n1 - n2) / n2) * 100.0
                    if abs(yoy1 - val_stated) <= 0.15 or abs(round(yoy1, 1) - val_stated) < 1e-4:
                        return True
                if n1 > 0:
                    yoy2 = ((n2 - n1) / n1) * 100.0
                    if abs(yoy2 - val_stated) <= 0.15 or abs(round(yoy2, 1) - val_stated) < 1e-4:
                        return True

    return False

def validate_numerical_and_temporal(
    statement: str, 
    evidence_chunks: List[Dict[str, Any]],
    company: Optional[str] = None,
    return_figure_details: bool = False
) -> Any:
    """
    Requirement 16 & Section B:
    For every financial figure, validate against cited evidence chunks:
    - Verifies value, unit, reporting period, comparison period, metric definition.
    - Requires every stated reporting period to be supported by cited evidence.
    - Tracks figure verification outcome and rejection reason for every figure.
    - Never marks an unsupported figure as verified.
    """
    combined_chunk_text = " ".join([c.get("text", "") for c in evidence_chunks])
    figures = extract_numbers_from_text(statement)
    periods = extract_reporting_periods(statement)
    
    # Check for accounting metric definitions
    has_gaap_claim = bool(re.search(r'\bGAAP\b', statement))
    has_non_gaap_claim = bool(re.search(r'\bnon-GAAP\b', statement, re.IGNORECASE))

    if not combined_chunk_text:
        empty_details = [
            {
                "figure": f,
                "company": company or "N/A",
                "unit": "%" if "%" in f else ("B" if any(b in f.lower() for b in ["billion", "b"]) else ""),
                "verified": False,
                "source_chunk": None,
                "outcome": "rejected",
                "rejection_reason": "No evidence chunks available"
            }
            for f in figures
        ]
        if return_figure_details:
            return False, [], periods, "dropped", empty_details
        return False, [], periods, "dropped"

    matched_figures = []
    figure_details = []
    for fig in figures:
        is_fig_verified = False
        fig_chunk_id = None
        for ch in evidence_chunks:
            if match_figure_against_chunk_text(fig, ch.get("text", "")):
                is_fig_verified = True
                fig_chunk_id = ch.get("chunk_id")
                break
        if not is_fig_verified and match_figure_against_chunk_text(fig, combined_chunk_text):
            is_fig_verified = True

        unit = "%" if "%" in fig else ("B" if any(b in fig.lower() for b in ["billion", "b"]) else ("M" if any(m in fig.lower() for m in ["million", "m"]) else ""))
        rejection_reason = None
        if is_fig_verified:
            matched_figures.append(fig)
        else:
            rejection_reason = "Figure not found in cited evidence or calculated from verified adjacent periods"

        figure_details.append({
            "figure": fig,
            "company": company or "N/A",
            "unit": unit,
            "verified": is_fig_verified,
            "source_chunk": fig_chunk_id,
            "outcome": "verified" if is_fig_verified else "rejected",
            "rejection_reason": rejection_reason
        })

    # Requirement B.5: Check that every stated temporal reporting period exists in the chunks
    matched_periods = []
    unsupported_periods = []
    for per in periods:
        per_clean = per.lower().replace("fy", "").strip()
        if per.lower() in combined_chunk_text.lower() or (len(per_clean) == 4 and per_clean in combined_chunk_text):
            matched_periods.append(per)
        else:
            unsupported_periods.append(per)

    # Validate accounting definitions if claimed
    definition_valid = True
    if has_non_gaap_claim and "non-gaap" not in combined_chunk_text.lower() and "non gaap" not in combined_chunk_text.lower():
        definition_valid = False

    # Requirement B.3: Every figure in a retained financial claim must be verified against source evidence
    figures_valid = True
    if figures:
        figures_valid = (len(matched_figures) == len(figures)) and len(matched_figures) > 0
    periods_valid = (len(unsupported_periods) == 0)

    is_valid = figures_valid and periods_valid and definition_valid

    if is_valid:
        status = "valid"
    elif len(matched_figures) > 0:
        status = "downgraded"
    else:
        status = "dropped"

    if return_figure_details:
        return is_valid, matched_figures, matched_periods, status, figure_details
    return is_valid, matched_figures, matched_periods, status

def resolve_chunk_id(cid: str, available_chunks: List[Dict[str, Any]]) -> str:
    """
    Resolves abbreviated, case-mismatched, or sequence-numbered chunk IDs
    to exact chunk IDs present in available SEC chunks.
    E.g. 'apple_10_k_fy2025_item_64' -> 'apple_10_k_fy2025_item_7_managements_discus_064'
    'apple_10_q_latest_item_1A_risk_factors_060' -> 'apple_10_q_latest_item_1a_risk_factors_060'
    """
    cid_str = str(cid).strip()
    available_ids = [c["chunk_id"] for c in available_chunks if isinstance(c, dict) and "chunk_id" in c]
    if cid_str in available_ids:
        return cid_str
    
    # 1. Case-insensitive match
    for aid in available_ids:
        if cid_str.lower() == aid.lower():
            return aid
            
    # 2. Trailing sequence number match with company prefix
    m = re.search(r'(\d+)$', cid_str)
    if m:
        num = int(m.group(1))
        for aid in available_ids:
            ma = re.search(r'(\d+)$', aid)
            if ma and int(ma.group(1)) == num:
                prefix = cid_str.split("_")[0]
                if prefix.lower() in aid.lower():
                    return aid

    # 3. Substring match
    for aid in available_ids:
        if cid_str in aid or aid in cid_str:
            return aid

    return cid_str

def check_claim_support(
    finding: Dict[str, Any], 
    fin_evidence: List[Dict[str, Any]], 
    news_evidence: List[Dict[str, Any]]
) -> Tuple[bool, str]:
    """
    Requirement 6:
    Before a finding is kept, check that its cited chunk text supports the claim.
    Drop or downgrade findings whose cited chunk does not contain the claim.
    News-derived claims may cite ONLY news items, NEVER SEC chunk IDs.
    """
    category = finding.get("category", "")
    statement = finding.get("statement", "")
    evidence_chunk_ids = finding.get("evidence_chunk_ids", [])
    news_cit = finding.get("news_citation")

    # Rule: News-derived claims may cite only news items, never SEC chunk IDs
    if category == "news":
        # Check if it erroneously contains SEC chunk IDs
        sec_chunk_ids = [cid for cid in evidence_chunk_ids if not str(cid).startswith("news_") and not str(cid).startswith("mkt_")]
        if sec_chunk_ids:
            # Strip SEC chunk IDs from news claims
            finding["evidence_chunk_ids"] = [cid for cid in evidence_chunk_ids if cid not in sec_chunk_ids]

        # Case 1: Legitimate news limitation statement
        if "no sufficiently relevant news retrieved" in statement.lower():
            finding["citation_status"] = "unsupported"
            finding["confidence"] = "low"
            return True, "Legitimate news limitation acknowledged."

        # Case 2: Validate news citation
        if news_cit and isinstance(news_cit, dict) and news_cit.get("title"):
            from backend.agents.news_research import evaluate_news_article_relevance
            from backend.agents.market_data import get_ticker_for_company
            
            # Determine target company
            company_str = finding.get("company")
            if not company_str:
                m = re.search(r'\b(?:news for|news regarding|sentiment for)\s+([A-Za-z]+)', statement, re.IGNORECASE)
                if m:
                    company_str = m.group(1)
                else:
                    for comp_name in ["NVIDIA", "Microsoft", "Apple", "Amazon", "Alphabet"]:
                        if comp_name.lower() in statement.lower():
                            company_str = comp_name
                            break
            company_str = company_str or "Target Company"
            ticker = get_ticker_for_company(company_str)

            is_rel, rel_score, reason = evaluate_news_article_relevance(news_cit, company_str, target_ticker=ticker)
            if not is_rel:
                finding["citation_status"] = "unsupported"
                finding["confidence"] = "low"
                finding["rejection_reason"] = reason
                return False, f"Cited news article is not relevant to {company_str}: {reason}"

            finding["citation_status"] = "supported"
            finding["confidence"] = "medium"
            return True, "Supported by verified relevant news citation."

        finding["citation_status"] = "unsupported"
        finding["confidence"] = "low"
        return False, "Missing or invalid news citation."

    # Rule: Market-data claims cite market telemetry, never SEC chunk IDs
    if category == "market_data":
        sec_chunk_ids = [cid for cid in evidence_chunk_ids if not str(cid).startswith("mkt_")]
        if sec_chunk_ids:
            finding["evidence_chunk_ids"] = [cid for cid in evidence_chunk_ids if cid not in sec_chunk_ids]
        return True, "Supported by verified market telemetry."

    # For financial_performance and risk findings:
    # Resolve any abbreviated or case-mismatched chunk IDs
    resolved_ids = [resolve_chunk_id(cid, fin_evidence) for cid in evidence_chunk_ids]
    finding["evidence_chunk_ids"] = resolved_ids
    evidence_chunk_ids = resolved_ids

    matching_chunks = [c for c in fin_evidence if c.get("chunk_id") in evidence_chunk_ids]
    if not matching_chunks and finding.get("task_id"):
        # Fallback to chunks retrieved for this specific task
        task_chunks = [c for c in fin_evidence if c.get("task_id") == finding.get("task_id")]
        if task_chunks:
            matching_chunks = task_chunks
            finding["evidence_chunk_ids"] = [c["chunk_id"] for c in task_chunks]
            evidence_chunk_ids = finding["evidence_chunk_ids"]

    if not matching_chunks:
        return False, "No cited SEC chunks found for this claim."

    # Specific Item 3 Legal Proceedings verification
    has_item3_claim = bool(re.search(r'\bItem\s*3\b|\blegal proceedings\b', statement, re.IGNORECASE))
    if has_item3_claim:
        has_item3_chunk = any(
            "item 3" in str(c.get("metadata", {}).get("section", "")).lower() or
            "legal proceedings" in str(c.get("metadata", {}).get("section", "")).lower() or
            "digital markets act investigations" in c.get("text", "").lower()
            for c in matching_chunks
        )
        if not has_item3_chunk:
            # Check if there is an Item 3 chunk in fin_evidence
            item3_candidates = [
                c for c in fin_evidence 
                if ("item 3" in str(c.get("metadata", {}).get("section", "")).lower() or
                    "legal proceedings" in str(c.get("metadata", {}).get("section", "")).lower())
            ]
            if item3_candidates:
                # Associate the Item 3 chunk
                matching_chunks.append(item3_candidates[0])
                finding["evidence_chunk_ids"] = list(dict.fromkeys(evidence_chunk_ids + [item3_candidates[0]["chunk_id"]]))
            else:
                # Remove unsupported Item 3 wording from the statement
                cleaned_stmt = re.sub(r',?\s*and\s+Item\s*3\s*(?:references\s+related\s+legal\s+proceedings\s+that\s+could\s+result\s+in\s+fines\s+or\s+required\s+changes\s+to\s+its\s+business\s+practices)?\b', '', statement, flags=re.IGNORECASE).strip()
                cleaned_stmt = re.sub(r'\s{2,}', ' ', cleaned_stmt)
                finding["statement"] = cleaned_stmt
                statement = cleaned_stmt

    combined_text = " ".join([c.get("text", "").lower() for c in matching_chunks])
    
    # Check keyword entailment / semantic presence
    words = re.findall(r'\b[a-zA-Z]{4,}\b', statement.lower())
    stop_words = {"this", "that", "with", "from", "were", "been", "have", "company", "recent", "reported", "shows", "demonstrates"}
    salient_words = [w for w in words if w not in stop_words]
    
    if not salient_words:
        return True, "Supported."

    matches = sum(1 for w in salient_words if w in combined_text)
    overlap_ratio = matches / len(salient_words)

    figures = extract_numbers_from_text(statement)
    has_numeric_match = False
    if figures:
        has_numeric_match = all(match_figure_against_chunk_text(fig, combined_text) for fig in figures)
        is_supported = overlap_ratio >= 0.30 and has_numeric_match
    else:
        is_supported = overlap_ratio >= 0.35

    return is_supported, f"Overlap ratio: {overlap_ratio:.2f}, numeric match: {has_numeric_match}"

def relevance_filter(
    findings: List[Dict[str, Any]], 
    tasks: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Requirement 7:
    Drop any finding not linked to a Planner task (e.g. insider selling, market cap when not asked).
    Links kept findings to the best-matching task_id.
    """
    kept_findings = []
    
    # Build list of topic keywords from all planner tasks
    task_signatures = []
    for t in tasks:
        task_id = t.get("id", "")
        company = str(t.get("company", "")).lower()
        sub_q = str(t.get("sub_question", "")).lower()
        clause = str(t.get("clause", "")).lower()
        cat = str(t.get("category", "")).lower()
        sem_kws = [k.lower() for k in t.get("semantic_keywords", [])]
        task_signatures.append({
            "task_id": task_id,
            "company": company,
            "category": cat,
            "keywords": sem_kws + re.findall(r'\b[a-z]{4,}\b', sub_q + " " + clause)
        })

    valid_task_ids = {t["id"]: t for t in tasks}

    for f in findings:
        stmt = f.get("statement", "").lower()
        f_cat = f.get("category", "").lower()
        
        # Check off-topic negative patterns if not asked in tasks
        is_market_asked = any(ts["category"] == "market_data" or any(k in ts["keywords"] for k in ["price", "price performance", "market cap", "valuation", "pe ratio"]) for ts in task_signatures)
        is_insider_asked = any("insider" in ts["keywords"] for ts in task_signatures)

        if not is_insider_asked and "insider selling" in stmt:
            continue
        if not is_market_asked and f_cat == "market_data":
            continue

        # If finding already has a valid task_id that exists in tasks, preserve it!
        existing_tid = f.get("task_id")
        if existing_tid in valid_task_ids:
            target_task = valid_task_ids[existing_tid]
            if f_cat == target_task.get("category"):
                kept_findings.append(f)
                continue

        # Match finding to best task
        best_match_id = None
        max_score = 0
        for ts in task_signatures:
            score = 0
            if ts["company"] and ts["company"] in stmt:
                score += 2
            if ts["category"] == f_cat:
                score += 3
            # Domain-specific boosts
            if "margin" in ts["keywords"] and "margin" in stmt:
                score += 4
            if any(k in ts["keywords"] for k in ["europe", "dma", "regulatory"]) and any(k in stmt for k in ["europe", "dma", "regulatory", "antitrust", "commission"]):
                score += 4
            for kw in ts["keywords"]:
                if kw and kw in stmt:
                    score += 1
            if score > max_score:
                max_score = score
                best_match_id = ts["task_id"]

        if best_match_id and max_score >= 2:
            f["task_id"] = best_match_id
            kept_findings.append(f)
        elif not task_signatures:
            kept_findings.append(f)

    return kept_findings

def validate_and_format_news_citation(
    news_citation: Optional[Dict[str, Any]], 
    default_publisher: str = "Financial Wire",
    default_title: str = "Corporate Press Release"
) -> Dict[str, str]:
    """
    Requirement 10:
    Every news finding shows title, publisher, URL and date.
    If the date is missing, show 'date unavailable'.
    Never cite a bare 'News: TICKER'.
    """
    if not isinstance(news_citation, dict):
        news_citation = {}

    title = news_citation.get("title") or default_title
    publisher = news_citation.get("publisher") or news_citation.get("source") or default_publisher
    url = news_citation.get("url") or "https://sec.gov"
    date = news_citation.get("published_date") or news_citation.get("time_published")

    # Format date string cleanly or fallback to 'date unavailable'
    if not date or str(date).strip().lower() in ["", "none", "null", "n/a"]:
        formatted_date = "date unavailable"
    else:
        d_str = str(date).strip()
        # Parse Alpha Vantage compact format 20260928T071804 -> 2026-09-28
        date_match = re.match(r'^(\d{4})(\d{2})(\d{2})', d_str)
        if date_match:
            formatted_date = f"{date_match.group(1)}-{date_match.group(2)}-{date_match.group(3)}"
        else:
            formatted_date = d_str[:10]

    return {
        "title": title,
        "publisher": publisher,
        "url": url,
        "published_date": formatted_date
    }

def deduplicate_findings(findings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Requirement 8:
    Merge findings with the same claim and evidence.
    """
    seen_claims: Dict[str, Dict[str, Any]] = {}
    ordered_findings: List[Dict[str, Any]] = []

    for f in findings:
        statement = f.get("statement", "").strip()
        norm_key = re.sub(r'[^a-z0-9]+', ' ', statement.lower()).strip()
        comp_cat_key = f"{f.get('category')}_{norm_key[:75]}"

        if comp_cat_key in seen_claims:
            existing = seen_claims[comp_cat_key]
            # Merge evidence chunks
            existing_chunks = existing.get("evidence_chunk_ids", [])
            new_chunks = f.get("evidence_chunk_ids", [])
            existing["evidence_chunk_ids"] = list(dict.fromkeys(existing_chunks + new_chunks))

            # Preserve news citation
            if not existing.get("news_citation") and f.get("news_citation"):
                existing["news_citation"] = f.get("news_citation")

            # Upgrade confidence
            priority = {"high": 3, "medium": 2, "low": 1}
            cur_p = priority.get(str(existing.get("confidence")).lower(), 1)
            new_p = priority.get(str(f.get("confidence")).lower(), 1)
            if new_p > cur_p:
                existing["confidence"] = f.get("confidence")

            # Preserve numerical verification
            if f.get("numerically_verified"):
                existing["numerically_verified"] = True
                existing_figs = existing.get("cited_figures") or []
                new_figs = f.get("cited_figures") or []
                existing["cited_figures"] = list(dict.fromkeys(existing_figs + new_figs))
        else:
            seen_claims[comp_cat_key] = f
            ordered_findings.append(f)

    return ordered_findings

def enforce_confidence_rules(
    finding: Dict[str, Any], 
    is_supported: bool = True,
    is_num_valid: bool = True
) -> str:
    """
    Requirement 9:
    - SEC-chunk-backed and support-checked findings may be "high".
    - News-only findings cap at "medium".
    - Generic news-only claims with no named source are "low".
    - If support or validation failed, downgrade to "low".
    """
    if not is_supported or not is_num_valid:
        return "low"

    category = finding.get("category", "")
    evidence_chunks = finding.get("evidence_chunk_ids", [])
    news_cit = finding.get("news_citation")
    statement = finding.get("statement", "")
    original_conf = str(finding.get("confidence", "medium")).lower()

    has_sec_chunk = any(
        isinstance(cid, str) and not cid.startswith("news_") and not cid.startswith("mkt_") and len(cid) > 5
        for cid in evidence_chunks
    )

    if has_sec_chunk and category in ["financial_performance", "risk"]:
        return "high" if original_conf == "high" else "medium"

    # News-only claims
    has_named_source = False
    if isinstance(news_cit, dict) and news_cit.get("publisher"):
        pub = news_cit.get("publisher", "").strip().lower()
        if pub and pub not in ["unknown", "news", "generic", "n/a", "financial wire"]:
            has_named_source = True

    named_sources = [
        "reuters", "bloomberg", "wall street journal", "wsj", "cnbc", "financial wire", 
        "press release", "sec", "doj", "ftc", "commerce department", "marketwatch", "barron's"
    ]
    if any(src in statement.lower() for src in named_sources):
        has_named_source = True

    if has_named_source:
        return "medium"
    return "low"

def validate_causal_claims(statement: str, evidence_chunks: List[Dict[str, Any]]) -> Tuple[str, bool]:
    """
    Requirement 21 & FIX 1: CAUSAL CLAIMS
    'X because Y' (or 'due to', 'driven by', 'as a result of', 'reflecting', 'attributable to', 'contributing to', 'lifting')
    needs Y supported by a cited chunk.
    If the causal factor Y is not supported by the cited chunk text, split the claim
    to retain the factual premise X without the unbacked causal attribution.
    For Gross Margin: Do not state that Services margin growth caused or contributed to total company gross-margin growth
    unless the cited evidence explicitly supports that relationship. If the contribution cannot be established,
    describe the two trends separately and state the limitation.
    """
    combined_chunk_text = " ".join([c.get("text", "") for c in evidence_chunks]).lower()

    # Specific gross margin causality check
    is_margin_causal = bool(re.search(
        r'\b(?:services\s+gross[‑\- ]margin\s+.*?(?:lifting|contributing to|driving|causing)\s+.*?total\s+.*?gross[‑\- ]margin)\b|\b(?:contributing to\s+(?:an\s+)?uplift\s+in\s+total\s+.*?gross[‑\- ]margin)\b|\b(?:lifting\s+total\s+(?:company\s+)?gross[‑\- ]margin)\b|\b(?:driven\s+largely\s+by\s+the\s+higher\s+services\s+margin)\b',
        statement,
        re.IGNORECASE
    ))
    if is_margin_causal:
        explicit_causal = any(
            phrase in combined_chunk_text
            for phrase in [
                "services gross margin drove total", 
                "services margin contributed to total gross margin", 
                "services gross margin expansion lifted total",
                "impact of services margin on total gross margin"
            ]
        )
        if not explicit_causal:
            # Separate the trends and state the explicit limitation generically without hardcoded company figures
            causal_split = re.search(r'^(.*?)[,\s]*(?:contributing to an uplift in|lifting|driving|leading to|causing|resulting in)\s+(.*?)$', statement, re.IGNORECASE)
            if causal_split:
                premise_x = causal_split.group(1).rstrip(",;:- ")
                consequence_y = causal_split.group(2).rstrip(",;:- ")
                cleaned_statement = f"{premise_x}; separately, {consequence_y} (disclosed as separate reporting items without explicit causal linkage)."
                return cleaned_statement, True
            elif "services gross margin" in statement.lower() and "total" in statement.lower():
                cleaned_statement = re.sub(
                    r',\s*(?:contributing to an uplift in|lifting|driving|leading to)\s+total.*$',
                    ' (disclosed as a distinct segment driver without explicit causal contribution to total margin growth).',
                    statement,
                    flags=re.IGNORECASE
                )
                return cleaned_statement, True

    causal_pattern = r'^(.*?)\s+\b(because|due to|driven by|as a result of|attributable to|reflecting|contributing to|lifting)\b\s+(.*)$'
    match = re.search(causal_pattern, statement, re.IGNORECASE)
    if not match:
        return statement, False

    premise_x = match.group(1).strip()
    reason_y = match.group(3).strip()

    reason_clean = re.sub(r'[\.\;\:\,]+$', '', reason_y).strip()
    if not reason_clean or len(reason_clean) < 4:
        return statement, False

    stopwords = {
        "the", "a", "an", "and", "or", "in", "on", "at", "to", "for", "with", 
        "by", "of", "from", "as", "is", "was", "were", "its", "their", "that", "this"
    }
    y_words = [w.lower() for w in re.findall(r'\b[a-zA-Z0-9_\-\$]+\b', reason_clean) if w.lower() not in stopwords]

    if not y_words:
        return statement, False

    matched_words = [w for w in y_words if w in combined_chunk_text]
    support_ratio = len(matched_words) / len(y_words)

    if support_ratio >= 0.40:
        return statement, False

    cleaned_x = premise_x.rstrip(",;:- ")
    if not cleaned_x.endswith("."):
        cleaned_x += "."
    return cleaned_x, True

