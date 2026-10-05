import re
from typing import List, Dict, Any, Tuple

def parse_document_metadata_from_filename(filename: str) -> Dict[str, str]:
    """
    Derives company, doc_type, and fiscal_period from filename according to Section 0.3.
    """
    fn_lower = filename.lower()
    
    # Company
    if "apple" in fn_lower:
        company = "Apple"
    elif "microsoft" in fn_lower:
        company = "Microsoft"
    elif "nvidia" in fn_lower:
        company = "NVIDIA"
    else:
        company = "Unknown"

    # Doc type
    if "10k" in fn_lower:
        doc_type = "10-K"
    elif "10q" in fn_lower:
        doc_type = "10-Q"
    elif "earnings" in fn_lower:
        doc_type = "8-K"
    else:
        doc_type = "Other"

    # Fiscal period
    # Match patterns like Q3_FY2026, FY2025, FY2026, Q2_FY2027, Latest
    period_match = re.search(r'(Q[1-4]_FY\d{4}|FY\d{4}|Latest)', filename, re.IGNORECASE)
    if period_match:
        fiscal_period = period_match.group(1).replace("_", " ").upper()
    else:
        fiscal_period = "Unknown"

    return {
        "company": company,
        "doc_type": doc_type,
        "fiscal_period": fiscal_period,
        "source_file": filename
    }

def slugify(text: str) -> str:
    """Generate a clean slug for chunk IDs."""
    text = text.lower()
    text = re.sub(r'[^a-z0-9]+', '_', text).strip('_')
    return text[:25]

def sub_split_text(text: str, max_chunk_chars: int = 2400, overlap_chars: int = 250) -> List[str]:
    """
    Splits text blocks into sub-chunks of ~500-800 tokens (approx 2000-3200 characters)
    respecting paragraph and markdown table boundaries.
    """
    if len(text) <= max_chunk_chars:
        return [text]

    paragraphs = text.split("\n\n")
    sub_chunks = []
    current_chunk = []
    current_len = 0

    for para in paragraphs:
        para_len = len(para)
        # If a single paragraph/table is itself massive, split by lines
        if para_len > max_chunk_chars:
            if current_chunk:
                sub_chunks.append("\n\n".join(current_chunk).strip())
                current_chunk = []
                current_len = 0
            
            lines = para.split("\n")
            line_chunk = []
            line_len = 0
            for line in lines:
                if line_len + len(line) > max_chunk_chars and line_chunk:
                    sub_chunks.append("\n".join(line_chunk).strip())
                    line_chunk = [line]
                    line_len = len(line)
                else:
                    line_chunk.append(line)
                    line_len += len(line) + 1
            if line_chunk:
                sub_chunks.append("\n".join(line_chunk).strip())
            continue

        if current_len + para_len > max_chunk_chars and current_chunk:
            sub_chunks.append("\n\n".join(current_chunk).strip())
            current_chunk = [para]
            current_len = para_len
        else:
            current_chunk.append(para)
            current_len += para_len + 2

    if current_chunk:
        sub_chunks.append("\n\n".join(current_chunk).strip())

    return [c for c in sub_chunks if c]

def classify_8k_block(text: str) -> str:
    """
    Classifies 8-K blocks into results_summary, segment_breakdown, guidance, or other.
    """
    lower = text.lower()
    if any(k in lower for k in ["outlook", "guidance", "forward-looking", "expect", "target", "projection"]):
        return "guidance"
    elif any(k in lower for k in ["segment", "data center", "gaming", "professional visualization", 
                                 "automotive", "iphone", "services", "mac", "ipad", "wearables", 
                                 "intelligent cloud", "productivity and business", "more personal computing"]):
        return "segment_breakdown"
    elif any(k in lower for k in ["revenue", "net income", "diluted earnings", "operating income", "cash flow", "gross margin", "dividend"]):
        return "results_summary"
    else:
        return "other"

def chunk_10k_document(cleaned_text: str, metadata: Dict[str, str]) -> List[Dict[str, Any]]:
    """
    Splits 10-K text by Item boundaries.
    """
    # Regex to detect SEC 10-K Item headings (e.g. 'Item 1A. Risk Factors', 'ITEM 7. MANAGEMENT'S DISCUSSION...')
    item_regex = re.compile(
        r'(?:^|\n)(?:#{1,4}\s*)?(ITEM\s+(?:1[A-C]?|[2-9]|1[0-6])[\.:\s\-]+[^\n]{2,80})',
        re.IGNORECASE
    )
    matches = list(item_regex.finditer(cleaned_text))
    sections: List[Tuple[str, str]] = []

    if not matches:
        # Fallback if no item headers detected
        sections.append(("General", cleaned_text))
    else:
        # Preamble before first item
        if matches[0].start() > 0:
            preamble = cleaned_text[:matches[0].start()].strip()
            if preamble:
                sections.append(("Preamble", preamble))

        for i, match in enumerate(matches):
            section_title = match.group(1).strip()
            # Clean title
            section_title = re.sub(r'^[#\s]+', '', section_title)
            start_pos = match.start()
            end_pos = matches[i + 1].start() if i + 1 < len(matches) else len(cleaned_text)
            sec_content = cleaned_text[start_pos:end_pos].strip()
            if sec_content:
                sections.append((section_title, sec_content))

    chunks = []
    chunk_order = 1
    comp_slug = slugify(metadata["company"])
    doc_slug = slugify(metadata["doc_type"])
    period_slug = slugify(metadata["fiscal_period"])

    for sec_title, sec_content in sections:
        sec_slug = slugify(sec_title)
        sub_chunks = sub_split_text(sec_content)
        for sub in sub_chunks:
            chunk_id = f"{comp_slug}_{doc_slug}_{period_slug}_{sec_slug}_{chunk_order:03d}"
            chunks.append({
                "chunk_id": chunk_id,
                "text": sub,
                "metadata": {
                    "chunk_id": chunk_id,
                    "chunk_order": chunk_order,
                    "company": metadata["company"],
                    "doc_type": metadata["doc_type"],
                    "fiscal_period": metadata["fiscal_period"],
                    "section": sec_title,
                    "source_file": metadata["source_file"]
                }
            })
            chunk_order += 1

    return chunks

def chunk_10q_document(cleaned_text: str, metadata: Dict[str, str]) -> List[Dict[str, Any]]:
    """
    Splits 10-Q text by Part and Item boundaries.
    """
    part_item_regex = re.compile(
        r'(?:^|\n)(?:#{1,4}\s*)?((?:PART\s+[I|II]+|ITEM\s+(?:[1-6][A-C]?))[\.:\s\-]+[^\n]{2,80})',
        re.IGNORECASE
    )
    matches = list(part_item_regex.finditer(cleaned_text))
    sections: List[Tuple[str, str]] = []

    if not matches:
        sections.append(("General", cleaned_text))
    else:
        if matches[0].start() > 0:
            preamble = cleaned_text[:matches[0].start()].strip()
            if preamble:
                sections.append(("Preamble", preamble))

        for i, match in enumerate(matches):
            section_title = match.group(1).strip()
            section_title = re.sub(r'^[#\s]+', '', section_title)
            start_pos = match.start()
            end_pos = matches[i + 1].start() if i + 1 < len(matches) else len(cleaned_text)
            sec_content = cleaned_text[start_pos:end_pos].strip()
            if sec_content:
                sections.append((section_title, sec_content))

    chunks = []
    chunk_order = 1
    comp_slug = slugify(metadata["company"])
    doc_slug = slugify(metadata["doc_type"])
    period_slug = slugify(metadata["fiscal_period"])

    for sec_title, sec_content in sections:
        sec_slug = slugify(sec_title)
        sub_chunks = sub_split_text(sec_content)
        for sub in sub_chunks:
            chunk_id = f"{comp_slug}_{doc_slug}_{period_slug}_{sec_slug}_{chunk_order:03d}"
            chunks.append({
                "chunk_id": chunk_id,
                "text": sub,
                "metadata": {
                    "chunk_id": chunk_id,
                    "chunk_order": chunk_order,
                    "company": metadata["company"],
                    "doc_type": metadata["doc_type"],
                    "fiscal_period": metadata["fiscal_period"],
                    "section": sec_title,
                    "source_file": metadata["source_file"]
                }
            })
            chunk_order += 1

    return chunks

def chunk_8k_document(cleaned_text: str, metadata: Dict[str, str]) -> List[Dict[str, Any]]:
    """
    Splits 8-K earnings release by paragraph/table blocks and classifies tags.
    """
    sub_chunks = sub_split_text(cleaned_text, max_chunk_chars=2000, overlap_chars=200)
    chunks = []
    chunk_order = 1
    comp_slug = slugify(metadata["company"])
    doc_slug = slugify(metadata["doc_type"])
    period_slug = slugify(metadata["fiscal_period"])

    for sub in sub_chunks:
        tag = classify_8k_block(sub)
        section_name = f"8-K_{tag.upper()}"
        sec_slug = slugify(section_name)
        chunk_id = f"{comp_slug}_{doc_slug}_{period_slug}_{sec_slug}_{chunk_order:03d}"
        chunks.append({
            "chunk_id": chunk_id,
            "text": sub,
            "metadata": {
                "chunk_id": chunk_id,
                "chunk_order": chunk_order,
                "company": metadata["company"],
                "doc_type": metadata["doc_type"],
                "fiscal_period": metadata["fiscal_period"],
                "section": section_name,
                "tag": tag,
                "source_file": metadata["source_file"]
            }
        })
        chunk_order += 1

    return chunks

def chunk_document(cleaned_text: str, filename: str) -> List[Dict[str, Any]]:
    """
    Master chunker routing according to document type.
    """
    meta = parse_document_metadata_from_filename(filename)
    doc_type = meta["doc_type"]

    if doc_type == "10-K":
        return chunk_10k_document(cleaned_text, meta)
    elif doc_type == "10-Q":
        return chunk_10q_document(cleaned_text, meta)
    else:
        return chunk_8k_document(cleaned_text, meta)
