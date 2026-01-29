"""
Test script for RAG QA System
Demonstrates upload, query, and metrics functionality
"""
import requests
import time
import json


BASE_URL = "http://localhost:8000"


def test_health():
    """Test health check endpoint"""
    print("\n=== Testing Health Check ===")
    response = requests.get(f"{BASE_URL}/health")
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    return response.status_code == 200


def test_upload(filename):
    """Test document upload"""
    print(f"\n=== Uploading Document: {filename} ===")
    
    try:
        with open(filename, 'rb') as f:
            response = requests.post(
                f"{BASE_URL}/upload",
                files={'file': (filename, f)}
            )
        
        print(f"Status: {response.status_code}")
        result = response.json()
        print(f"Response: {json.dumps(result, indent=2)}")
        
        if response.status_code == 200:
            return result['document_id']
        return None
        
    except FileNotFoundError:
        print(f"Error: File {filename} not found")
        return None


def test_document_status(document_id):
    """Test document status check"""
    print(f"\n=== Checking Document Status ===")
    response = requests.get(f"{BASE_URL}/documents/{document_id}")
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    return response.json()


def wait_for_processing(document_id, max_wait=30):
    """Wait for document to finish processing"""
    print(f"\n=== Waiting for Processing ===")
    start_time = time.time()
    
    while time.time() - start_time < max_wait:
        status = test_document_status(document_id)
        
        if status.get('status') == 'completed':
            print(f"[OK] Processing completed in {time.time() - start_time:.2f}s")
            return True
        elif status.get('status') == 'failed':
            print("[FAIL] Processing failed")
            return False
        
        print("  Still processing...")
        time.sleep(2)
    
    print(f"[FAIL] Timeout after {max_wait}s")
    return False


def test_query(question, document_id=None, top_k=5):
    """Test question answering"""
    print(f"\n=== Asking Question ===")
    print(f"Question: {question}")
    
    payload = {
        "question": question,
        "top_k": top_k
    }
    
    if document_id:
        payload["document_id"] = document_id
    
    response = requests.post(
        f"{BASE_URL}/ask",
        json=payload
    )
    
    print(f"Status: {response.status_code}")
    
    if response.status_code == 200:
        result = response.json()
        print(f"\nAnswer: {result['answer']}\n")
        print(f"Confidence: {result['confidence_score']:.3f}")
        print(f"Latency: {result['latency_ms']:.2f}ms")
        print(f"\nTop {len(result['source_chunks'])} Source Chunks:")
        
        for i, chunk in enumerate(result['source_chunks'], 1):
            print(f"  {i}. Score: {chunk['score']:.3f} | {chunk['filename']} (chunk {chunk['chunk_index']})")
            print(f"     Preview: {chunk['text'][:100]}...")
        
        return result
    else:
        print(f"Error: {response.json()}")
        return None


def test_list_documents():
    """Test listing all documents"""
    print("\n=== Listing All Documents ===")
    response = requests.get(f"{BASE_URL}/documents")
    print(f"Status: {response.status_code}")
    documents = response.json()
    print(f"Total documents: {len(documents)}")
    
    for doc in documents:
        print(f"  - {doc['filename']} ({doc['status']}) - {doc.get('chunks_count', 0)} chunks")
    
    return documents


def test_metrics():
    """Test metrics endpoint"""
    print("\n=== System Metrics ===")
    response = requests.get(f"{BASE_URL}/metrics")
    print(f"Status: {response.status_code}")
    
    if response.status_code == 200:
        metrics = response.json()
        print(f"\nTotal Queries: {metrics.get('total_queries', 0)}")
        
        if 'latency' in metrics:
            lat = metrics['latency']
            print(f"\nLatency Metrics:")
            print(f"  Average: {lat.get('avg_ms', 0):.2f}ms")
            print(f"  P95: {lat.get('p95_ms', 0):.2f}ms")
            print(f"  P99: {lat.get('p99_ms', 0):.2f}ms")
        
        if 'retrieval' in metrics:
            ret = metrics['retrieval']
            print(f"\nRetrieval Metrics:")
            print(f"  Avg Time: {ret.get('avg_time_ms', 0):.2f}ms")
            print(f"  Avg Similarity: {ret.get('avg_similarity', 0):.3f}")
        
        if 'confidence' in metrics:
            conf = metrics['confidence']
            print(f"\nConfidence Metrics:")
            print(f"  Average: {conf.get('avg', 0):.3f}")
            print(f"  Min: {conf.get('min', 0):.3f}")
            print(f"  Max: {conf.get('max', 0):.3f}")
        
        return metrics
    else:
        print(f"Error: {response.json()}")
        return None


def test_rate_limiting():
    """Test rate limiting"""
    print("\n=== Testing Rate Limiting ===")
    print("Sending 12 requests rapidly (limit is 10/min)...")
    
    success_count = 0
    rate_limited = False
    
    for i in range(12):
        response = requests.get(f"{BASE_URL}/health")
        if response.status_code == 200:
            success_count += 1
        elif response.status_code == 429:
            rate_limited = True
            print(f"  Request {i+1}: Rate limited (429)")
            break
    
    if rate_limited:
        print(f"[OK] Rate limiting working: {success_count} requests succeeded before limit")
    else:
        print(f"[FAIL] No rate limiting detected after {success_count} requests")


def run_full_test():
    """Run complete test suite"""
    print("=" * 60)
    print("RAG QA System - Full Test Suite")
    print("=" * 60)
    
    # 1. Health check
    if not test_health():
        print("\n[FAIL] Server not responding. Make sure it's running on port 8000")
        return
    
    # 2. Upload document
    document_id = test_upload("sample_document.txt")
    if not document_id:
        print("\n[FAIL] Upload failed. Creating sample document...")
        # Create sample document
        with open("sample_document.txt", "w") as f:
            f.write("""
RAG Systems and Artificial Intelligence

Retrieval-Augmented Generation (RAG) is a powerful technique in artificial intelligence that combines information retrieval with language generation. This approach addresses one of the key limitations of large language models: their tendency to hallucinate or provide outdated information.

How RAG Works

RAG systems work by first retrieving relevant documents or passages from a knowledge base, then using these retrieved contexts to generate more accurate and grounded responses. The process involves three main steps:

1. Document Processing: Documents are split into chunks and converted into vector embeddings
2. Retrieval: When a query arrives, relevant chunks are retrieved using similarity search
3. Generation: An LLM uses the retrieved context to generate an informed answer

Benefits of RAG

RAG systems offer several advantages over traditional language models. They can access up-to-date information without retraining, cite sources for their answers, and reduce hallucinations by grounding responses in actual documents. Additionally, RAG systems are more cost-effective than fine-tuning large models for specific domains.

Vector Databases

Vector databases like FAISS, Pinecone, and Weaviate are crucial components of RAG systems. They enable efficient similarity search over millions of document embeddings, making real-time retrieval possible.

Chunking Strategies

Effective chunking is critical for RAG performance. Chunks should be large enough to contain complete concepts but small enough to be semantically focused. Common chunk sizes range from 256 to 1024 tokens, with overlap to preserve context.

Future Directions

The future of RAG systems includes hybrid search combining vector and keyword approaches, iterative retrieval for multi-hop reasoning, and integration with specialized databases for structured data.
            """)
        document_id = test_upload("sample_document.txt")
    
    if not document_id:
        print("\n[FAIL] Could not upload document")
        return
    
    # 3. Wait for processing
    if not wait_for_processing(document_id):
        print("\n[FAIL] Processing timeout")
        return
    
    # 4. List documents
    test_list_documents()
    
    # 5. Query tests
    test_queries = [
        "What is RAG?",
        "How does retrieval-augmented generation work?",
        "What are the benefits of RAG systems?",
        "What chunk size should I use?",
        "What is a vector database?"
    ]
    
    for query in test_queries:
        test_query(query, document_id)
        time.sleep(1)
    
    # 6. Test query without document_id (search all documents)
    test_query("Tell me about artificial intelligence", top_k=3)
    
    # 7. Check metrics
    test_metrics()
    
    # 8. Test rate limiting
    test_rate_limiting()
    
    print("\n" + "=" * 60)
    print("Test Suite Complete!")
    print("=" * 60)


if __name__ == "__main__":
    run_full_test()
