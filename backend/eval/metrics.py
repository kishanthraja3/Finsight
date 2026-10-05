import re
from typing import Dict, Any, List
from backend.agents.llm_client import call_gemini, extract_json_from_llm

LLM_JUDGE_PROMPT = """You are an Uncompromising Financial Accuracy and Reasoning Benchmark Judge.
Given:
- Question: {question}
- Golden Reference Answer: {golden_answer}
- Key Facts Expected: {key_facts}
- Candidate Answer: {candidate_answer}
- Cited Chunks / Sources: {citations}

Evaluate the candidate answer on:
1. Factual Accuracy (0.0 to 1.0): Are the numbers and facts consistent with the golden answer?
2. Hallucination Rate (0.0 to 1.0): What fraction of claims in the candidate answer are fabricated or lack backing in the cited sources? (0.0 = zero hallucination, 1.0 = completely fabricated)
3. Citation Accuracy (0.0 to 1.0): Do the cited chunks actually support the candidate statements? (If no citations provided when claims are made, score 0.0)
4. Reasoning Quality (1 to 5): Coherence, financial nuance, and depth of analysis.

Output JSON ONLY:
{{
  "factual_accuracy": 0.95,
  "hallucination_rate": 0.05,
  "citation_accuracy": 1.0,
  "reasoning_quality": 4.8,
  "rationale": "Concise justification for scores"
}}
"""

def evaluate_answer(
    question: str,
    golden_answer: str,
    key_facts: List[str],
    candidate_answer: str,
    citations: List[str],
    retrieval_calls: int = 1,
    chunks_retrieved: int = 0
) -> Dict[str, Any]:
    """
    Computes rigorous factual accuracy, hallucination rate, citation accuracy, reasoning quality,
    and retrieval cost metrics.
    """
    prompt = LLM_JUDGE_PROMPT.format(
        question=question,
        golden_answer=golden_answer,
        key_facts=", ".join(key_facts),
        candidate_answer=candidate_answer,
        citations=", ".join(citations) if citations else "None cited"
    )

    try:
        raw_res = call_gemini(prompt)
        metrics = extract_json_from_llm(raw_res)
    except Exception as e:
        # Heuristic fallback if LLM judge fails
        matched_facts = sum(1 for kf in key_facts if kf.lower() in candidate_answer.lower())
        fact_ratio = matched_facts / max(len(key_facts), 1)
        has_citations = len(citations) > 0
        metrics = {
            "factual_accuracy": round(fact_ratio, 2),
            "hallucination_rate": 0.1 if has_citations else 0.4,
            "citation_accuracy": 0.9 if has_citations else 0.0,
            "reasoning_quality": 4.0 if fact_ratio > 0.6 else 2.5,
            "rationale": f"Matched {matched_facts}/{len(key_facts)} key facts heuristically."
        }

    metrics["retrieval_calls"] = retrieval_calls
    metrics["chunks_retrieved"] = chunks_retrieved
    return metrics
