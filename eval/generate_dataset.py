import json
import os
import sys
from typing import List, Dict

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.documents.vectorstore.chroma import chroma_store
from app.llm.factory import get_chat_model
from langchain_core.messages import HumanMessage, SystemMessage

def generate_dataset(output_path="eval/dataset.json", target_count=10):
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    # Try to get chunks from Chroma
    try:
        results = chroma_store._collection.get(
            include=["documents", "metadatas"],
            limit=target_count * 2 # get more chunks to pick from
        )
    except Exception as e:
        print(f"Failed to load from Chroma: {e}")
        return

    docs = results.get("documents", [])
    metas = results.get("metadatas", [])
    
    if not docs:
        print("No documents found in ChromaDB. Upload some PDFs first to generate a dataset.")
        # Create a tiny fallback dataset
        fallback = [
            {
                "id": "fallback_001",
                "question": "What is the capital of France?",
                "ground_truth_answer": "Paris.",
                "expected_sources": [{"filename": "geography.pdf", "page_number": 1}]
            }
        ]
        with open(output_path, "w") as f:
            json.dump(fallback, f, indent=2)
        return

    dataset = []
    llm = get_chat_model()
    
    system_prompt = SystemMessage(content="You are an expert dataset creator. Generate a specific question that can be answered entirely by the provided text, and provide the exact answer. Output format must be valid JSON: {\"question\": \"...\", \"answer\": \"...\"}")
    
    count = 0
    for doc, meta in zip(docs, metas):
        if len(doc.strip()) < 100:
            continue
            
        prompt = f"Text:\n{doc}\n\nGenerate JSON:"
        try:
            response = llm.invoke([system_prompt, HumanMessage(content=prompt)])
            # naive json parse
            content = response.content.replace("```json", "").replace("```", "").strip()
            parsed = json.loads(content)
            
            dataset.append({
                "id": f"q{count+1:03d}",
                "question": parsed["question"],
                "ground_truth_answer": parsed["answer"],
                "expected_sources": [
                    {
                        "filename": meta.get("filename", "unknown"),
                        "page_number": meta.get("page_number", 1)
                    }
                ]
            })
            count += 1
            print(f"Generated {count}/{target_count}")
            if count >= target_count:
                break
        except Exception as e:
            print(f"Error generating question: {e}")
            
    with open(output_path, "w") as f:
        json.dump(dataset, f, indent=2)
    print(f"Saved dataset to {output_path}")

if __name__ == "__main__":
    generate_dataset(target_count=5)
