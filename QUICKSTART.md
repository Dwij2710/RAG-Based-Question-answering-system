# Quick Start Guide

Get the RAG QA System running in 5 minutes!

## Prerequisites

- Python 3.9 or higher
- pip (Python package manager)
- 2GB free disk space

## Installation

### 1. Clone or Download

```bash
# If using git
git clone <repository-url>
cd rag-qa-system

# Or download and extract the ZIP file
```

### 2. Create Virtual Environment

```bash
# Create virtual environment
python -m venv venv

# Activate it
# On Linux/Mac:
source venv/bin/activate

# On Windows:
venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

This will install:
- FastAPI (web framework)
- Sentence Transformers (embeddings)
- FAISS (vector search)
- PyPDF2 (PDF processing)
- Anthropic (Claude API)
- Other dependencies

**Note**: First installation may take 5-10 minutes as it downloads embedding models.

### 4. (Optional) Set Claude API Key

For real LLM responses (recommended):

```bash
# On Linux/Mac:
export ANTHROPIC_API_KEY="your-key-here"

# On Windows:
set ANTHROPIC_API_KEY=your-key-here
```

**Don't have an API key?** No problem! The system will use mock responses.

Get a key at: https://console.anthropic.com/

## Running the Server

```bash
python app.py
```

You should see:

```
INFO:     Started server process
INFO:     Waiting for application startup.
Loading embedding model: all-MiniLM-L6-v2
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000
```

The server is now running! 🎉

## Testing the System

### Option 1: Use the Test Script (Recommended)

```bash
# In a new terminal (keep server running)
python test_system.py
```

This will:
- Upload a sample document
- Run several test queries
- Display metrics
- Test rate limiting

### Option 2: Manual Testing with curl

#### 1. Check Health

```bash
curl http://localhost:8000/health
```

#### 2. Upload a Document

```bash
curl -X POST "http://localhost:8000/upload" \
  -F "file=@sample_document.txt"
```

Save the `document_id` from the response!

#### 3. Wait for Processing (10-15 seconds)

#### 4. Ask a Question

```bash
curl -X POST "http://localhost:8000/ask" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What is quantum computing?",
    "top_k": 5
  }'
```

### Option 3: Use the Interactive API Docs

Open your browser and go to:

**http://localhost:8000/docs**

This provides:
- Interactive API interface
- Automatic request/response examples
- Try-it-out functionality
- Schema documentation

## Quick Usage Examples

### Upload Multiple Documents

```python
import requests

files = ["doc1.pdf", "doc2.txt", "doc3.pdf"]
doc_ids = []

for file in files:
    with open(file, 'rb') as f:
        response = requests.post(
            'http://localhost:8000/upload',
            files={'file': f}
        )
        doc_ids.append(response.json()['document_id'])

print(f"Uploaded {len(doc_ids)} documents")
```

### Ask Questions

```python
import requests

# Ask a question
response = requests.post(
    'http://localhost:8000/ask',
    json={
        'question': 'What is the main topic?',
        'top_k': 5
    }
)

result = response.json()
print(f"Answer: {result['answer']}")
print(f"Confidence: {result['confidence_score']}")
```

### Check System Metrics

```python
import requests

response = requests.get('http://localhost:8000/metrics')
metrics = response.json()

print(f"Total queries: {metrics['total_queries']}")
print(f"Average latency: {metrics['latency']['avg_ms']}ms")
print(f"Average similarity: {metrics['retrieval']['avg_similarity']}")
```

## Common Issues & Solutions

### Issue: "Address already in use"

**Solution**: Port 8000 is already taken. Change port in `app.py`:

```python
uvicorn.run(app, host="0.0.0.0", port=8001)  # Use 8001 instead
```

### Issue: "ANTHROPIC_API_KEY not set" warning

**Solution**: This is just a warning. System will use mock responses.

To use real Claude API:
```bash
export ANTHROPIC_API_KEY="your-key"
```

### Issue: Slow first query

**Explanation**: First query loads the embedding model into memory (~100MB).
Subsequent queries will be faster.

### Issue: "No documents available"

**Solution**: Wait 10-15 seconds after upload for processing to complete.

Check status:
```bash
curl http://localhost:8000/documents/{document_id}
```

### Issue: Import errors

**Solution**: Make sure virtual environment is activated:
```bash
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows
```

Then reinstall:
```bash
pip install -r requirements.txt
```

## Next Steps

### 1. Read the Documentation
- **README.md** - Full API documentation
- **DESIGN_DECISIONS.md** - Technical rationale
- **ARCHITECTURE.md** - System architecture

### 2. Customize the System
- Adjust chunk size in `document_processor.py`
- Change embedding model in `vector_store.py`
- Modify rate limits in `app.py`

### 3. Add Your Documents
- PDF files (research papers, reports)
- TXT files (articles, notes)
- Multiple documents for cross-document queries

### 4. Explore Advanced Features
- Query specific documents with `document_id`
- Adjust `top_k` for more/fewer retrieved chunks
- Monitor metrics for performance tuning

## Development Mode

For development with auto-reload:

```bash
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

## Stopping the Server

Press `Ctrl+C` in the terminal where the server is running.

## Getting Help

- Check the logs for error messages
- Review `README.md` for detailed documentation
- Examine `test_system.py` for usage examples

## Production Deployment

For production use, see deployment guides for:
- Docker containerization
- Cloud deployment (AWS, GCP, Azure)
- Scaling strategies
- Security hardening

## System Requirements

- **RAM**: 2GB minimum, 4GB recommended
- **Storage**: 2GB for models and indexes
- **CPU**: Multi-core recommended for faster embeddings
- **GPU**: Optional, for faster embedding generation

## Performance Expectations

- **Document Processing**: 2-5 seconds per page
- **Query Latency**: 
  - Without API key: 100-300ms
  - With Claude API: 500-2000ms
- **Throughput**: 10-20 queries/second

## What's Next?

You now have a working RAG system! Try:

1. Upload your own documents
2. Experiment with different questions
3. Monitor metrics to understand performance
4. Customize chunking and retrieval parameters

Happy querying! 🚀
