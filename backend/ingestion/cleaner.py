import re
from io import StringIO
from bs4 import BeautifulSoup
import pandas as pd

def table_to_markdown(table_tag) -> str:
    """Convert an HTML <table> element into clean Markdown table format preserving alignment."""
    rows = []
    for tr in table_tag.find_all("tr"):
        cells = tr.find_all(["th", "td"])
        if not cells:
            continue
        row_text = []
        for cell in cells:
            text = " ".join(cell.get_text(separator=" ", strip=True).split())
            text = text.replace("|", "\\|")
            row_text.append(text)
        if any(cell_str for cell_str in row_text):  # ignore totally empty rows
            rows.append(row_text)

    if not rows:
        return ""

    # Normalize column lengths
    max_cols = max(len(r) for r in rows)
    if max_cols == 0:
        return ""

    normalized_rows = [r + [""] * (max_cols - len(r)) for r in rows]

    header = normalized_rows[0]
    separator = ["---"] * max_cols
    body = normalized_rows[1:] if len(normalized_rows) > 1 else []

    md_lines = [
        "| " + " | ".join(header) + " |",
        "| " + " | ".join(separator) + " |"
    ]
    for r in body:
        md_lines.append("| " + " | ".join(r) + " |")

    return "\n" + "\n".join(md_lines) + "\n"

def clean_html_document(html_content: str) -> str:
    """
    Cleans raw HTML SEC filing:
    - Removes <script>, <style>, navigation, boilerplate, hidden elements
    - Unwraps inline XBRL (<ix:...>) tags to preserve underlying text
    - Preserves headings, section titles, paragraphs, footnotes
    - Converts every <table> into aligned Markdown table
    """
    soup = BeautifulSoup(html_content, "lxml")

    # 1. Remove non-content and hidden tags
    for tag in soup(["script", "style", "noscript", "meta", "link", "header", "footer"]):
        tag.decompose()

    for hidden in soup.find_all(attrs={"style": re.compile(r"display:\s*none", re.I)}):
        hidden.decompose()

    for hidden in soup.find_all(attrs={"aria-hidden": "true"}):
        hidden.decompose()

    # 2. Unwrap inline XBRL tags (e.g., <ix:nonnumeric>, <ix:nonfraction>)
    for ix_tag in soup.find_all(re.compile(r"^ix:")):
        ix_tag.unwrap()

    # 3. Process tables into Markdown
    for table in soup.find_all("table"):
        md_table = table_to_markdown(table)
        table.replace_with(soup.new_string(md_table))

    # 4. Format headings
    for h in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]):
        level = int(h.name[1])
        heading_text = h.get_text(separator=" ", strip=True)
        h.replace_with(soup.new_string(f"\n\n{'#' * level} {heading_text}\n\n"))

    # 5. Extract text with paragraph spacing
    text = soup.get_text(separator="\n")

    # 6. Normalize whitespace while keeping table and paragraph structure
    lines = [line.strip() for line in text.splitlines()]
    cleaned_lines = []
    empty_count = 0
    for line in lines:
        if not line:
            empty_count += 1
            if empty_count <= 2:
                cleaned_lines.append("")
        else:
            empty_count = 0
            cleaned_lines.append(line)

    return "\n".join(cleaned_lines).strip()
