import json
import os
import sys
import time
import asyncio
from typing import List, Dict

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import settings
from app.documents.vectorstore.chroma import chroma_store
from app.llm.factory import get_chat_model
from langchain_core.messages import HumanMessage, SystemMessage
from app.graph.nodes import get_reranker
from app.graph.prompts import RAG_PROMPT_WITH_CONTEXT

async def evaluate():
    dataset_path = "eval/dataset.json"
    results_path = "eval/results.json"
    
    if not os.path.exists(dataset_path):
        print(f"Dataset not found at {dataset_path}. Please run generate_dataset.py first.")
        return
        
    with open(dataset_path, "r") as f:
        dataset = json.load(f)
        
    total_q = len(dataset)
    if total_q == 0:
        print("Empty dataset.")
        return

    # Metrics
    recalls = {1: 0, 3: 0, 5: 0, 10: 0}
    mrrs = {1: 0, 3: 0, 5: 0, 10: 0}
    answer_relevance_scores = []
    faithfulness_scores = []
    hallucination_count = 0
    citation_correct_count = 0
    invalid_citation_count = 0
    
    latencies = []
    
    llm = get_chat_model()
    
    # Prompts for LLM-as-a-judge
    relevance_prompt = SystemMessage(content="You are an evaluator. Given a question and an answer, score the relevance of the answer to the question from 0.0 to 1.0. Just return the float number. Examples: 1.0 (perfectly answers), 0.5 (partially), 0.0 (irrelevant).")
    faithfulness_prompt = SystemMessage(content="You are an evaluator. Given context and an answer, score the faithfulness of the answer to the context from 0.0 to 1.0. If the answer contains information NOT in the context (hallucination), the score should be lower. Just return the float number.")
    
    print(f"Evaluating {total_q} questions...")
    
    for item in dataset:
        q = item["question"]
        expected_sources = item.get("expected_sources", [])
        
        t0 = time.perf_counter()
        
        # 1. RETRIEVAL
        # Simulate retrieval as in nodes.py
        k = settings.rerank_top_k if settings.enable_reranking else settings.top_k
        docs = chroma_store.retrieve(query=q, thread_id="", n_results=k)
        
        # Reranking
        if settings.enable_reranking and docs:
            reranker = get_reranker()
            if reranker:
                pairs = [[q, doc.page_content] for doc in docs]
                scores = reranker.predict(pairs)
                scored_docs = list(zip(docs, scores))
                scored_docs.sort(key=lambda x: x[1], reverse=True)
                docs = [doc for doc, score in scored_docs[:settings.final_context_k]]
        
        retrieval_latency = time.perf_counter() - t0
        
        # Evaluate Recall & MRR
        # expected filename and page
        expected = [(src["filename"], src["page_number"]) for src in expected_sources]
        
        retrieved_meta = [(d.metadata.get("filename", ""), d.metadata.get("page_number", "")) for d in docs]
        
        rank_of_first_relevant = -1
        for i, meta in enumerate(retrieved_meta):
            if meta in expected:
                rank_of_first_relevant = i + 1
                break
                
        for k_val in [1, 3, 5, 10]:
            if rank_of_first_relevant != -1 and rank_of_first_relevant <= k_val:
                recalls[k_val] += 1
                mrrs[k_val] += 1.0 / rank_of_first_relevant
                
        # 2. GENERATION
        context_parts = []
        for i, doc in enumerate(docs[:settings.max_context_chunks], 1):
            meta = doc.metadata or {}
            filename = meta.get("filename", "unknown")
            page = meta.get("page_number", "?")
            context_parts.append(f"SOURCE {i}\nDocument: {filename}\nPage: {page}\n\n{doc.page_content}")
            
        context = "\n\n---\n\n".join(context_parts)
        
        t1 = time.perf_counter()
        
        has_context = bool(context.strip())
        chain = RAG_PROMPT_WITH_CONTEXT | llm
        
        invoke_args = {"chat_history": [], "question": q, "context": context}
        try:
            response = await chain.ainvoke(invoke_args)
            ans = response.content
        except:
            ans = "Error generating."
            
        gen_latency = time.perf_counter() - t1
        latencies.append(retrieval_latency + gen_latency)
        
        # 3. CITATION ACCURACY
        # Check if expected source was actually retrieved and used
        # We can loosely check if the answer mentions the filename, or just check precision of retrieval vs ground truth
        # Since citation formatting isn't explicitly in the prompt generated answer string in this standard setup,
        # we evaluate citation based on what the attach_sources node would output.
        # attach_sources outputs all retrieved docs as citations.
        if rank_of_first_relevant != -1:
            citation_correct_count += 1
        else:
            invalid_citation_count += 1
            
        # 4. LLM-AS-A-JUDGE
        try:
            rel_res = await llm.ainvoke([relevance_prompt, HumanMessage(content=f"Question: {q}\nAnswer: {ans}")])
            answer_relevance_scores.append(float(rel_res.content.strip()))
        except:
            answer_relevance_scores.append(0.0)
            
        try:
            faith_res = await llm.ainvoke([faithfulness_prompt, HumanMessage(content=f"Context: {context}\nAnswer: {ans}")])
            f_score = float(faith_res.content.strip())
            faithfulness_scores.append(f_score)
            if f_score < 0.5:
                hallucination_count += 1
        except:
            faithfulness_scores.append(0.0)
            hallucination_count += 1
            
    # Calculate final metrics
    report = {
        "dataset_size": total_q,
        "retrieval": {
            "recall_at_1": recalls[1] / total_q,
            "recall_at_3": recalls[3] / total_q,
            "recall_at_5": recalls[5] / total_q,
            "recall_at_10": recalls[10] / total_q,
        },
        "ranking": {
            "mrr_at_1": mrrs[1] / total_q,
            "mrr_at_3": mrrs[3] / total_q,
            "mrr_at_5": mrrs[5] / total_q,
            "mrr_at_10": mrrs[10] / total_q,
        },
        "generation": {
            "answer_relevance": sum(answer_relevance_scores) / total_q if total_q else 0,
            "faithfulness": sum(faithfulness_scores) / total_q if total_q else 0,
            "hallucination_rate": hallucination_count / total_q if total_q else 0,
        },
        "citations": {
            "citation_accuracy": citation_correct_count / total_q if total_q else 0,
            "invalid_citation_rate": invalid_citation_count / total_q if total_q else 0,
        },
        "performance": {
            "average_latency": sum(latencies) / total_q if total_q else 0,
            "p50": sorted(latencies)[int(total_q * 0.5)] if total_q else 0,
            "p95": sorted(latencies)[int(total_q * 0.95)] if total_q else 0,
        }
    }
    
    with open(results_path, "w") as f:
        json.dump(report, f, indent=2)
        
    print("="*40)
    print("RAG EVALUATION REPORT")
    print("="*40)
    print(f"Dataset:\nQuestions: {total_q}\n")
    print("RETRIEVAL")
    for k, v in report["retrieval"].items():
        print(f"{k.capitalize()}: {v:.2f}")
    print("\nRANKING")
    for k, v in report["ranking"].items():
        print(f"{k.upper()}: {v:.2f}")
    print("\nGENERATION")
    for k, v in report["generation"].items():
        print(f"{k.replace('_', ' ').title()}: {v:.2f}")
    print("\nCITATIONS")
    for k, v in report["citations"].items():
        print(f"{k.replace('_', ' ').title()}: {v:.2f}")
    print("\nPERFORMANCE")
    for k, v in report["performance"].items():
        print(f"{k.upper()}: {v:.3f}s")
    print("="*40)

if __name__ == "__main__":
    asyncio.run(evaluate())
