import sys
import io
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.agents.planner import plan_research, detect_companies_from_query

print("--- TEST B.1: Apple Services Revenue Query ---")
state_apple = {"query": "Evaluate Apple's Services revenue growth, gross margin impact, and Item 1A regulatory risks in European markets."}
plan_apple = plan_research(state_apple)
tasks_apple = plan_apple["tasks"]
print(f"Apple tasks count: {len(tasks_apple)}")
for t in tasks_apple:
    print(f"  [{t['id']}] {t['company']} | {t['category']} | {t['sub_question']}")
assert any("services" in t["sub_question"].lower() and "revenue" in t["sub_question"].lower() for t in tasks_apple)
assert any("services" in t["sub_question"].lower() and "gross margin" in t["sub_question"].lower() for t in tasks_apple)
assert any("european" in t["sub_question"].lower() or "europe" in t["sub_question"].lower() for t in tasks_apple)
print("[PASS] Apple query correctly generated Services revenue, Services margin, and European regulatory tasks.")

print("\n--- TEST B.2: NVIDIA Data Center Revenue Query (No Services contamination) ---")
state_nvda = {"query": "Evaluate NVIDIA's Data Center revenue trajectory, gross margin trend, and export-control risks to China."}
plan_nvda = plan_research(state_nvda)
tasks_nvda = plan_nvda["tasks"]
print(f"NVIDIA tasks count: {len(tasks_nvda)}")
for t in tasks_nvda:
    print(f"  [{t['id']}] {t['company']} | {t['category']} | {t['sub_question']}")
    assert "services" not in t["sub_question"].lower(), f"Contaminated with Services: {t['sub_question']}"
    assert "apple" not in t["sub_question"].lower(), f"Contaminated with Apple: {t['sub_question']}"
assert any("data center" in t["sub_question"].lower() for t in tasks_nvda)
assert any("gross margin" in t["sub_question"].lower() for t in tasks_nvda)
assert any("china" in t["sub_question"].lower() or "export" in t["sub_question"].lower() for t in tasks_nvda)
print("[PASS] NVIDIA tasks preserved Data Center, gross margin, and China export controls without Apple or Services contamination.")

print("\n--- TEST B.3: Microsoft Azure Operating Margin Query ---")
state_msft = {"query": "Evaluate Microsoft's Azure growth, operating margin trend, and European regulatory risks."}
plan_msft = plan_research(state_msft)
tasks_msft = plan_msft["tasks"]
print(f"Microsoft tasks count: {len(tasks_msft)}")
for t in tasks_msft:
    print(f"  [{t['id']}] {t['company']} | {t['category']} | {t['sub_question']}")
    assert "apple" not in t["sub_question"].lower()
    assert "services gross margin" not in t["sub_question"].lower()
assert any("azure" in t["sub_question"].lower() for t in tasks_msft)
assert any("operating margin" in t["sub_question"].lower() for t in tasks_msft)
print("[PASS] Microsoft tasks preserved Azure growth, operating margin, and European risks.")

print("\n--- TEST B.4: Multi-Company Comparison Preserves Both Companies ---")
state_comp = {"query": "Compare semiconductor supply chain dependencies and geopolitical trade exposure across NVIDIA and Apple."}
plan_comp = plan_research(state_comp)
tasks_comp = plan_comp["tasks"]
comps_in_plan = set(t["company"] for t in tasks_comp)
print("Companies in plan:", comps_in_plan)
assert "NVIDIA" in comps_in_plan and "Apple" in comps_in_plan
print("[PASS] Multi-company comparison preserved distinct tasks for both NVIDIA and Apple.")

print("\n--- TEST B.5: Unknown Company Name Does NOT Silently Default ---")
detected_unknown = detect_companies_from_query("Analyze AcmeCorp revenue growth")
assert detected_unknown == [], f"Expected [], got {detected_unknown}"
print("[PASS] Unknown company does not silently default to NVIDIA or Apple.")

print("\nALL PLANNER UNIT TESTS PASSED!")
