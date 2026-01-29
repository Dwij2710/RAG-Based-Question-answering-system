
print("Testing google.generativeai import...")
try:
    import google.generativeai as genai
    print(f"GenAI imported: {genai.__version__}")
except Exception as e:
    print(f"Error importing genai: {e}")
