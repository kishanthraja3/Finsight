import sys
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.config import settings
from backend.agents.verifier import validate_causal_claims, extract_reporting_periods
from backend.agents.critic import execute_critic
from backend.graph.build_graph import compile_final_report

print("--- TEST 1: Causal Claims Validation (Instruction 21) ---")
test_chunk = [{"chunk_id": "c1", "text": "NVIDIA GAAP gross margin was 75.1% for the second quarter."}]

stmt1 = "NVIDIA GAAP gross margin was 75.1% because of massive Blackwell deployment in cloud datacenters"
cleaned1, was_split1 = validate_causal_claims(stmt1, test_chunk)
print("Original:", stmt1)
print("Cleaned: ", cleaned1)
print("Was Split:", was_split1)
assert was_split1 == True, "Expected claim to be split due to unsupported causal factor"
assert "Blackwell" not in cleaned1, "Expected unbacked causal factor to be removed"

stmt2 = "NVIDIA GAAP gross margin was 75.1% for the second quarter."
cleaned2, was_split2 = validate_causal_claims(stmt2, test_chunk)
assert was_split2 == False, "Expected non-causal claim to remain unchanged"

print("\n--- TEST 2: Completeness Check in Critic (Instruction 18) ---")
incomplete_trend_state = {
    "tasks": [{
        "id": "t1",
        "category": "financial_performance",
        "sub_question": "Analyze NVIDIA gross margin trend across periods",
        "company": "NVIDIA",
        "semantic_keywords": ["gross margin", "trend"]
    }],
    "findings": [{
        "id": "f1",
        "task_id": "t1",
        "category": "financial_performance",
        "statement": "NVIDIA gross margin was 75.1% in Q2 FY2027.", # only 1 period
        "confidence": "high",
        "evidence_chunk_ids": ["c1"],
        "status": "pending",
        "numerically_verified": True
    }],
    "coverage_ledger": [{
        "task_id": "t1",
        "task": "Analyze NVIDIA gross margin trend across periods",
        "company": "NVIDIA",
        "required_doc_types": ["8-K"],
        "required_sections": ["Item 2"],
        "required_evidence_type": "financial_metric",
        "semantic_keywords": ["gross margin", "trend"],
        "evidence_retrieved": ["c1", "c2", "c3"],
        "cited_chunks": [],
        "retrieved_unused_chunks": [],
        "final_finding": None,
        "finding_id": None,
        "qc_status": "PENDING",
        "evidence_limitation": None
    }],
    "retry_count": 0,
    "max_retries": 3,
    "synthesis_draft": "Test draft"
}

crit_res = execute_critic(incomplete_trend_state)
print("Critic passed on incomplete 1-period trend?:", crit_res["critic_result"]["passed"])
print("Critic issues:", crit_res["critic_result"]["issues"])
assert crit_res["critic_result"]["passed"] == False, "Critic should fail 1-period trend"
assert "t1" in crit_res["affected_tasks"], "t1 should be marked affected for gap-fill retry"

print("\n--- TEST 3: Evidence Limitation after MAX_RETRIES (Instruction 18 & 20) ---")
incomplete_trend_state["retry_count"] = 3
crit_res_lim = execute_critic(incomplete_trend_state)
ledger_entry = crit_res_lim["coverage_ledger"][0]
print("QC status after max_retries:", ledger_entry["qc_status"])
print("Evidence limitation note:", ledger_entry["evidence_limitation"])
print("Cited chunks in ledger:", ledger_entry["cited_chunks"])
print("Unused chunks in ledger:", ledger_entry["retrieved_unused_chunks"])
assert ledger_entry["qc_status"] == "LIMITATION", "Expected LIMITATION status"
assert ledger_entry["evidence_limitation"] is not None, "Expected limitation note"
assert "c1" in ledger_entry["cited_chunks"], "Expected c1 to be recognized as cited"

print("\n--- TEST 4: Hide Empty Report Sections (Instruction 22) ---")
test_state = {
    "query": "Gross margin and risk analysis",
    "companies": ["NVIDIA"],
    "coverage_ledger": crit_res_lim["coverage_ledger"]
}
# Findings only have financial_performance and risk; NO market_data, NO news
test_findings = [
    {
        "id": "finding_001",
        "task_id": "t1",
        "category": "financial_performance",
        "statement": "NVIDIA GAAP gross margin was 75.1% in Q2 FY2027.",
        "confidence": "high",
        "evidence_chunk_ids": ["c1"],
        "status": "approved",
        "numerically_verified": True
    },
    {
        "id": "finding_002",
        "task_id": "t1",
        "category": "risk",
        "statement": "NVIDIA export control restrictions on H20 under BIS regulations.",
        "confidence": "high",
        "evidence_chunk_ids": ["c2"],
        "status": "approved",
        "numerically_verified": False
    }
]

report = compile_final_report(test_state, test_findings)
print("\nGenerated Report Sections:")
for line in report.split("\n"):
    if line.startswith("## "):
        print(" ", line)

assert "## Market Valuation & Telemetry Metrics" not in report, "Empty Market Valuation section should be hidden"
assert "## News, Catalysts & Market Landscape" not in report, "Empty News section should be hidden"
assert "## Financial Performance & Segment Trajectory" in report, "Financial performance section should be present"
assert "## Strategic & Regulatory Risk Disclosures (Item 1A / Item 3)" in report, "Risk section should be present"

print("\nALL INSTRUCTIONS (18, 19, 20, 21, 22) VERIFIED SUCCESSFULLY!")
