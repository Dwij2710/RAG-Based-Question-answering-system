
print("Testing faiss import...")
try:
    import faiss
    print(f"Faiss imported successfully: {faiss.__version__}")
except Exception as e:
    print(f"Error importing faiss: {e}")
