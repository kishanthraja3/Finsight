import os
import sys
import json
from pathlib import Path
from typing import Dict, Any, List
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import chromadb
from sentence_transformers import SentenceTransformer
from backend.config import settings
from backend.agents.llm_client import call_gemini
from backend.agents.financial_research import execute_financial_research, get_resources
from backend.eval.metrics import evaluate_answer

def run_no_rag(question: str, company: str) -> Dict[str, Any]:
    prompt = f"Answer this financial research question accurately for {company} based strictly on verified public disclosures:\n\n{question}"
    ans = call_gemini(prompt)
    return {
        "answer": ans,
        "citations": [],
        "retrieval_calls": 0,
        "chunks_retrieved": 0
    }

def run_basic_rag(question: str, company: str, collection, model) -> Dict[str, Any]:
    query_emb = model.encode([question]).tolist()
    results = collection.query(
        query_embeddings=query_emb,
        n_results=3,
        where={"company": company} if company else None
    )
    docs = results["documents"][0] if results and results["documents"] else []
    ids = results["ids"][0] if results and results["ids"] else []
    
    context = "\n\n".join([f"[{cid}]: {doc}" for cid, doc in zip(ids, docs)])
    prompt = f"""Use ONLY the following retrieved SEC evidence to answer the question. Cite chunk IDs in brackets.
Evidence:
{context}

Question: {question}
"""
    ans = call_gemini(prompt)
    return {
        "answer": ans,
        "citations": ids,
        "retrieval_calls": 1,
        "chunks_retrieved": len(docs)
    }

def run_agentic_rag(question: str, company: str) -> Dict[str, Any]:
    state = {
        "query": question,
        "companies": [company],
        "tasks": [{
            "id": "eval_task_01",
            "agent": "financial_research",
            "category": "financial_performance",
            "sub_question": question,
            "company": company
        }],
        "financial_evidence": [],
        "max_retries": 3,
        "retry_count": 0
    }
    output = execute_financial_research(state)
    evidence = output.get("financial_evidence", [])
    citations = [e["chunk_id"] for e in evidence]
    total_calls = max([e.get("attempts", 1) for e in evidence]) if evidence else 1
    
    context = "\n\n".join([f"[{e['chunk_id']}] (Confidence: {e['confidence']}):\n{e['text']}" for e in evidence[:6]])
    prompt = f"""You are FinSight's Agentic Financial Synthesizer.
Answer the following financial research question accurately using the thoroughly evaluated evidence below.
Include citations to chunk_ids in square brackets.

Evaluated SEC Evidence:
{context}

Question: {question}
"""
    ans = call_gemini(prompt)
    return {
        "answer": ans,
        "citations": citations,
        "retrieval_calls": total_calls,
        "chunks_retrieved": len(evidence)
    }

def run_full_benchmark(limit: int = 4):
    golden_path = PROJECT_ROOT / "eval" / "golden_qa.json"
    if not golden_path.exists():
        raise FileNotFoundError(f"Golden QA dataset not found at {golden_path}")

    with open(golden_path, "r", encoding="utf-8") as f:
        qa_pairs = json.load(f)[:limit]

    model, chroma_client = get_resources()
    collection = chroma_client.get_collection("finsight_documents")

    results = {
        "no_rag": [],
        "basic_rag": [],
        "agentic_rag": []
    }

    print(f"\nRunning 3-Way Comparative Benchmark on {len(qa_pairs)} golden questions...\n")

    for i, qa in enumerate(qa_pairs, 1):
        q = qa["question"]
        gold = qa["golden_answer"]
        facts = qa["key_facts"]
        comp = qa["company"]

        print(f"\n[{i}/{len(qa_pairs)}] Question: {q}")

        # 1. No-RAG
        print("  Evaluating No-RAG...")
        no_rag_res = run_no_rag(q, comp)
        no_rag_metrics = evaluate_answer(
            q, gold, facts, no_rag_res["answer"], no_rag_res["citations"],
            retrieval_calls=no_rag_res["retrieval_calls"], chunks_retrieved=no_rag_res["chunks_retrieved"]
        )
        results["no_rag"].append(no_rag_metrics)

        # 2. Basic RAG
        print("  Evaluating Basic RAG...")
        basic_res = run_basic_rag(q, comp, collection, model)
        basic_metrics = evaluate_answer(
            q, gold, facts, basic_res["answer"], basic_res["citations"],
            retrieval_calls=basic_res["retrieval_calls"], chunks_retrieved=basic_res["chunks_retrieved"]
        )
        results["basic_rag"].append(basic_metrics)

        # 3. Agentic RAG
        print("  Evaluating Agentic RAG (Iterative loop + 4-criteria evaluation)...")
        agentic_res = run_agentic_rag(q, comp)
        agentic_metrics = evaluate_answer(
            q, gold, facts, agentic_res["answer"], agentic_res["citations"],
            retrieval_calls=agentic_res["retrieval_calls"], chunks_retrieved=agentic_res["chunks_retrieved"]
        )
        results["agentic_rag"].append(agentic_metrics)

    # Compute averages
    def avg(lst, key):
        return sum(item.get(key, 0) for item in lst) / max(len(lst), 1)

    summary = {
        "No-RAG": {
            "Factual Accuracy": f"{avg(results['no_rag'], 'factual_accuracy') * 100:.1f}%",
            "Hallucination Rate": f"{avg(results['no_rag'], 'hallucination_rate') * 100:.1f}%",
            "Citation Accuracy": f"{avg(results['no_rag'], 'citation_accuracy') * 100:.1f}%",
            "Reasoning Quality (1-5)": f"{avg(results['no_rag'], 'reasoning_quality'):.2f}",
            "Avg Retrieval Calls": f"{avg(results['no_rag'], 'retrieval_calls'):.1f}",
            "Avg Chunks Retrieved": f"{avg(results['no_rag'], 'chunks_retrieved'):.1f}"
        },
        "Basic RAG": {
            "Factual Accuracy": f"{avg(results['basic_rag'], 'factual_accuracy') * 100:.1f}%",
            "Hallucination Rate": f"{avg(results['basic_rag'], 'hallucination_rate') * 100:.1f}%",
            "Citation Accuracy": f"{avg(results['basic_rag'], 'citation_accuracy') * 100:.1f}%",
            "Reasoning Quality (1-5)": f"{avg(results['basic_rag'], 'reasoning_quality'):.2f}",
            "Avg Retrieval Calls": f"{avg(results['basic_rag'], 'retrieval_calls'):.1f}",
            "Avg Chunks Retrieved": f"{avg(results['basic_rag'], 'chunks_retrieved'):.1f}"
        },
        "Agentic RAG": {
            "Factual Accuracy": f"{avg(results['agentic_rag'], 'factual_accuracy') * 100:.1f}%",
            "Hallucination Rate": f"{avg(results['agentic_rag'], 'hallucination_rate') * 100:.1f}%",
            "Citation Accuracy": f"{avg(results['agentic_rag'], 'citation_accuracy') * 100:.1f}%",
            "Reasoning Quality (1-5)": f"{avg(results['agentic_rag'], 'reasoning_quality'):.2f}",
            "Avg Retrieval Calls": f"{avg(results['agentic_rag'], 'retrieval_calls'):.1f}",
            "Avg Chunks Retrieved": f"{avg(results['agentic_rag'], 'chunks_retrieved'):.1f}"
        }
    }

    # Print summary table
    print("\n" + "=" * 80)
    print("FIN SIGHT THREE-WAY EVALUATION BENCHMARK RESULTS")
    print("=" * 80)
    header = f"{'Metric':<26} | {'No-RAG':<14} | {'Basic RAG':<14} | {'Agentic RAG':<14}"
    print(header)
    print("-" * 80)
    for m in ["Factual Accuracy", "Hallucination Rate", "Citation Accuracy", "Reasoning Quality (1-5)", "Avg Retrieval Calls", "Avg Chunks Retrieved"]:
        print(f"{m:<26} | {summary['No-RAG'][m]:<14} | {summary['Basic RAG'][m]:<14} | {summary['Agentic RAG'][m]:<14}")
    print("=" * 80)

    # Save to JSON
    output_path = PROJECT_ROOT / "eval" / "benchmark_results.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({"summary": summary, "detailed_runs": results}, f, indent=2)
    print(f"\nDetailed evaluation results saved to: {output_path}")

if __name__ == "__main__":
    run_full_benchmark(limit=4)
