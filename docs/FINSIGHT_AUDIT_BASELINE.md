# FinSight Audit Baseline

**Date:** 2026-10-04  
**Auditor:** Senior AI Engineer (FinSight Reliability & RAG Optimization)

---

## 1. Relevant Files & Responsibilities

| File Path | Role / Responsibility | LLM Used? |
| :--- | :--- | :--- |
| `backend/config.py` | Configuration settings, API keys, retry limits, model identifiers. | No |
| `backend/agents/llm_client.py` | Central LLM client wrapper for Groq, rate-limit sleep, retry, and JSON parsing. | Central Caller |
| `backend/graph/state.py` | TypedDict state definitions (`FinSightState`, `Finding`, `CoverageLedgerEntry`, etc.). | No |
| `backend/graph/build_graph.py` | LangGraph StateGraph definition, node functions, conditional edges, checkpointing, SSE. | No (orchestrator) |
| `backend/agents/planner.py` | Query decomposition into structured sub-tasks, required doc types, and keywords. | Yes (`MODEL_PLANNER`) |
| `backend/agents/financial_research.py` | ChromaDB vector retrieval, section matching, candidate reranking, gap-fill query expansion. | Yes (`MODEL_GAP_FILL` for gap-fill only) |
| `backend/agents/market_data.py` | Yahoo Finance market data and fundamentals fetching, caching. | No |
| `backend/agents/news_research.py` | Financial news & sentiment retrieval via Alpha Vantage/RSS feeds. | No |
| `backend/agents/risk.py` | Risk analysis extracting Item 1A / Item 3 risk factors from SEC evidence. | Yes (`MODEL_RISK`) |
| `backend/agents/synthesis.py` | Multi-source institutional markdown synthesis, structured findings generation. | Yes (`MODEL_SYNTHESIS`) |
| `backend/agents/verifier.py` | Deterministic numerical validation (scale, billions vs millions), temporal & causal claims checking. | No (Deterministic) |
| `backend/agents/critic.py` | Task completeness review, coverage ledger integrity, semantic hallucination check. | Yes (`MODEL_CRITIC`) |
| `backend/agents/replanner.py` | Targeted query and task reformulation for failed coverage ledger tasks. | Yes (`MODEL_REPLANNER`) |
| `backend/api/routes.py` | FastAPI REST API endpoints (`/api/runs`, `/api/runs/{id}/resume`, etc.). | No |
| `frontend/src/*` | Next.js frontend, human-in-the-loop draft review screen, final report viewer. | No |

---

## 2. Current LangGraph Execution Flow

```text
START 
  │
  ▼
[planner_node]
  │
  ├───────────────────┬───────────────────┬───────────────────┐
  ▼                   ▼                   ▼                   ▼
[financial_research] [market_data]       [news_research]     [risk_node]
  │                   │                   │                   │
  └───────────────────┴───────────────────┴───────────────────┘
                      │ (join)
                      ▼
               [synthesis_node]
                      │
                      ▼
               [human_review] (interrupt)
                      │ (resume with human decisions)
                      ▼
                [critic_node]
                      │
            ┌─────────┴─────────┐
      (passed)             (failed / retries < max)
            ▼                   ▼
      [compile_report]    [replanner_node]
            │                   │
           END                  └──> (loops back to research nodes)
```

### Path Tracing:
1. **Normal Query Path**:
   `planner_node` -> Parallel Research (`financial_research`, `market_data`, `news_research`, `risk_node`) -> `synthesis_node` -> `human_review` (interrupt) -> `critic_node` -> `compile_final_report` -> `END`.
2. **Failed Evidence / Task Incompleteness Path**:
   `critic_node` evaluates Coverage Ledger -> detects failed/incomplete tasks -> routes to `replanner_node` -> generates targeted sub-queries -> sets `affected_categories` -> re-runs research nodes for affected tasks -> re-synthesizes -> re-evaluates.
3. **HITL Path**:
   The workflow interrupts before `critic_node`. User approves, edits, rejects, or requests more evidence on findings. Resume payload is received via `/api/runs/{id}/resume`.

---

## 3. Current LLM Call Sites & Configuration

- **Configured Provider**: Groq API (`https://api.groq.com/openai/v1`).
- **Target Models**:
  - `MODEL_PLANNER`: `openai/gpt-oss-120b` (Default in config; user requested `qwen/qwen3.8-27b` for regression run due to OSS TPD limits)
  - `MODEL_GAP_FILL`: `openai/gpt-oss-20b` / `qwen/qwen3.8-27b`
  - `MODEL_SYNTHESIS`: `openai/gpt-oss-120b` / `qwen/qwen3.8-27b`
  - `MODEL_CRITIC`: `openai/gpt-oss-120b` / `qwen/qwen3.8-27b`
  - `MODEL_RISK`: `openai/gpt-oss-120b` / `qwen/qwen3.8-27b`
  - `MODEL_REPLANNER`: `openai/gpt-oss-120b` / `qwen/qwen3.8-27b`
- **Call Sites**:
  1. `backend/agents/planner.py` line 217 (`call_gemini` -> `call_llm`)
  2. `backend/agents/financial_research.py` line 162 (`call_gemini` for gap-fill query rewriting)
  3. `backend/agents/risk.py` line 68 (`call_gemini` for risk statements)
  4. `backend/agents/synthesis.py` line 133 (`call_gemini` for synthesis draft + findings)
  5. `backend/agents/critic.py` line 75 (`call_gemini` for critic review)
  6. `backend/agents/replanner.py` line 101 (`call_gemini` for replanning)

---

## 4. Existing Retry Limits & Rate Limiting

- **LLM Client Retry**: Currently fixed at `max_retries: 2` in `llm_client.py` with fixed `_MIN_CALL_INTERVAL = 0.2s`.
- **Workflow / Graph Retry**: `MAX_RETRIES = 3` in `backend/config.py`.
- **Identified Deficiency**:
  - `llm_client.py` retried immediately across fallback models on 429 quota exhaustion without respecting provider headers (`Retry-After`, `x-ratelimit-reset-tokens`).
  - Fallback loops could multiply calls unnecessarily when daily TPD was exhausted for the whole account.
  - Rate limiting did not track token usage per report or provide typed exceptions.

---

## 5. ChromaDB Schema & Distance Metric

- **Path**: `backend/vectorstore/chroma_db`
- **Collection**: `finsight_documents` (1,063 chunks total across Apple, NVIDIA, and Microsoft)
- **Metadata Fields**:
  - `company` (`str`: "Apple", "NVIDIA", "Microsoft")
  - `doc_type` (`str`: "10-K", "10-Q", "8-K")
  - `fiscal_period` (`str`: e.g. "FY2025", "LATEST", "Q3 FY2026")
  - `section` (`str`: e.g. "Item 1A. Risk Factors", "Item 3. Legal Proceedings", "Item 7. MD&A", "Item 8. Financial Statements")
  - `chunk_id` (`str`: e.g. `apple_10_k_fy2025_item_3_legal_proceedings_052`)
  - `chunk_order` (`int`)
  - `source_file` (`str`)
- **Distance Metric**: Cosine distance ($d \in [0, 2]$, where similarity is $1 - d$).

---

## 6. Known Inconsistencies & Deficiencies Identified Prior to Fixes

1. **Hardcoded Task Rewrites**:
   - `planner.py` contained clauses that rewrote margin tasks specifically to Apple Services gross margin (`Assess Apple's Services gross margin...`), risking contamination when querying NVIDIA or Microsoft.
2. **Missing Token & Request Budgets**:
   - No structured per-report telemetry tracking logical vs HTTP requests, input/output tokens, or latency.
3. **Provider Credential Cross-Talk**:
   - `config.py` allowed `GEMINI_API_KEY` to be used in place of `GROQ_API_KEY`.
4. **Market Data & News Executing Unconditionally**:
   - Both agents ran on every query, even for SEC-only queries (e.g. gross margin or regulatory risk).
5. **In-Memory Checkpointing**:
   - `MemorySaver` was used in `build_graph.py`, losing state on server restart. A durable SQLite checkpointer is needed.
6. **Risk Agent Integration**:
   - Synthesizer prompts did not clearly isolate pre-validated `risk_findings` from raw SEC chunks.

---

## 7. Baseline Test Results (Pre-Modification)

- **`backend/eval/test_verifier_units.py`**:
  - 12 / 12 Unit Tests Passed (Billions vs millions conversion, rounding tolerance, YoY growth, percentage point checks).
- **`backend/eval/test_completeness_and_ledger.py`**:
  - All 4 tests Passed (Causal claim split, Critic incompleteness detection, Evidence limitation after max retries, Empty section omission).
- **Regression Diagnostic (`run_full_diagnostic.py`)**:
  - Apple 3-task evaluation passed Critic QC.
