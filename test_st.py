
print("Testing sentence_transformers import...")
try:
    from sentence_transformers import SentenceTransformer
    print("sentence_transformers imported successfully")
except Exception as e:
    print(f"Error importing sentence_transformers: {e}")
