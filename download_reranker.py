from sentence_transformers import CrossEncoder
import sys

print("Downloading reranker model...", flush=True)
try:
    model = CrossEncoder("BAAI/bge-reranker-base")
    print("Successfully loaded reranker model.", flush=True)
except Exception as e:
    print(f"Error: {e}", flush=True)
