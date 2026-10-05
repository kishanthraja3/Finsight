import sys
import time
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8')
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.config import settings
from backend.agents.planner import PLANNER_SYSTEM_PROMPT
from backend.agents.llm_client import call_gemini

prompt = """New Research Request:
User Query: Evaluate Apple's Services revenue growth, gross margin impact, and Item 1A regulatory risks in European markets.
Target Companies Identified: ['Apple']
Risk/Regulation Focus: True

Emit one task per clause of the query for each target company.
"""

print(f"Calling model: {settings.MODEL_PLANNER}...", flush=True)
t0 = time.time()
resp = call_gemini(prompt, system_instruction=PLANNER_SYSTEM_PROMPT, model=settings.MODEL_PLANNER)
print(f"Completed in {time.time()-t0:.2f}s", flush=True)
print("Response length:", len(resp), flush=True)
print("Response text:\n", resp, flush=True)
