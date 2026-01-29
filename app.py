"""
RAG-Based Question Answering System
Main FastAPI application
"""
import os
print("DEBUG: Starting app.py...")
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

import uuid
import time
from typing import List, Optional
from datetime import datetime, timedelta
from collections import defaultdict

from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import uvicorn
print("DEBUG: Standard libs imported.")

print("DEBUG: Importing DocumentProcessor...")
from document_processor import DocumentProcessor
print("DEBUG: Importing VectorStore...")
from vector_store import VectorStore
print("DEBUG: Importing LLMService...")
from llm_service import LLMService
print("DEBUG: Importing MetricsTracker...")
from metrics_tracker import MetricsTracker
print("DEBUG: Imports complete.")

from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

# Initialize FastAPI app
app = FastAPI(
    title="RAG QA System",
    description="Document-based Question Answering using RAG",
    version="1.0.0"
)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def read_root():
    return FileResponse('static/index.html')

# Initialize services
doc_processor = DocumentProcessor()
vector_store = VectorStore()
llm_service = LLMService()
metrics = MetricsTracker()
print("DEBUG: Services initialized.")

# Rate limiting storage
rate_limit_store = defaultdict(list)
RATE_LIMIT = 10  # requests per minute
RATE_LIMIT_WINDOW = 60  # seconds


# Pydantic models for request/response validation
class QuestionRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=500, description="Question to ask")
    document_id: Optional[str] = Field(None, description="Specific document ID to query")
    top_k: int = Field(5, ge=1, le=20, description="Number of chunks to retrieve")


class AnswerResponse(BaseModel):
    answer: str
    source_chunks: List[dict]
    confidence_score: float
    latency_ms: float
    document_ids: List[str]


class DocumentUploadResponse(BaseModel):
    document_id: str
    filename: str
    status: str
    message: str


class DocumentStatus(BaseModel):
    document_id: str
    filename: str
    status: str
    chunks_count: Optional[int] = None
    processed_at: Optional[str] = None


# Rate limiting middleware
def check_rate_limit(client_ip: str) -> bool:
    """Check if client has exceeded rate limit"""
    now = time.time()
    # Clean old entries
    rate_limit_store[client_ip] = [
        timestamp for timestamp in rate_limit_store[client_ip]
        if now - timestamp < RATE_LIMIT_WINDOW
    ]
    
    if len(rate_limit_store[client_ip]) >= RATE_LIMIT:
        return False
    
    rate_limit_store[client_ip].append(now)
    return True


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    """Apply rate limiting to all requests"""
    client_ip = request.client.host
    
    if not check_rate_limit(client_ip):
        return JSONResponse(
            status_code=429,
            content={
                "error": "Rate limit exceeded",
                "message": f"Maximum {RATE_LIMIT} requests per minute"
            }
        )
    
    response = await call_next(request)
    return response


def process_document_background(document_id: str, file_path: str, filename: str):
    """Background task to process document"""
    try:
        # Extract text from document
        text = doc_processor.extract_text(file_path)
        
        # Chunk the document
        chunks = doc_processor.chunk_text(text, filename)
        
        # Generate embeddings and store
        vector_store.add_chunks(document_id, chunks)
        
        # Update status
        vector_store.update_document_status(
            document_id, 
            "completed", 
            len(chunks),
            datetime.now().isoformat()
        )
        
        print(f"Document {document_id} processed successfully: {len(chunks)} chunks")
        
    except Exception as e:
        print(f"Error processing document {document_id}: {str(e)}")
        vector_store.update_document_status(document_id, "failed", 0, None)
    finally:
        # Clean up uploaded file
        if os.path.exists(file_path):
            os.remove(file_path)


@app.post("/upload", response_model=DocumentUploadResponse)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...)
):
    """
    Upload a document (PDF or TXT) for processing
    """
    # Validate file type
    allowed_extensions = ['.pdf', '.txt']
    file_ext = os.path.splitext(file.filename)[1].lower()
    
    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type. Allowed: {', '.join(allowed_extensions)}"
        )
    
    # Generate unique document ID
    document_id = str(uuid.uuid4())
    
    # Save uploaded file temporarily
    upload_dir = "uploads"
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, f"{document_id}{file_ext}")
    
    try:
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")
    
    # Initialize document status
    vector_store.update_document_status(document_id, "processing", 0, None, filename=file.filename)
    
    # Add background task for processing
    background_tasks.add_task(
        process_document_background,
        document_id,
        file_path,
        file.filename
    )
    
    return DocumentUploadResponse(
        document_id=document_id,
        filename=file.filename,
        status="processing",
        message="Document uploaded and processing started"
    )


@app.post("/ask", response_model=AnswerResponse)
async def ask_question(question_req: QuestionRequest):
    """
    Ask a question based on uploaded documents
    """
    start_time = time.time()
    
    # Check if we have any documents
    if not vector_store.has_documents():
        raise HTTPException(
            status_code=400,
            detail="No documents available. Please upload documents first."
        )
    
    try:
        # Retrieve relevant chunks
        retrieval_start = time.time()
        retrieved_chunks = vector_store.search(
            question_req.question,
            top_k=question_req.top_k,
            document_id=question_req.document_id
        )
        retrieval_time = (time.time() - retrieval_start) * 1000
        
        if not retrieved_chunks:
            raise HTTPException(
                status_code=404,
                detail="No relevant information found in documents"
            )
        
        # Generate answer using LLM
        llm_start = time.time()
        answer, confidence = llm_service.generate_answer(
            question_req.question,
            retrieved_chunks
        )
        llm_time = (time.time() - llm_start) * 1000
        
        # Calculate total latency
        total_latency = (time.time() - start_time) * 1000
        
        # Extract document IDs
        document_ids = list(set(chunk['document_id'] for chunk in retrieved_chunks))
        
        # Track metrics
        metrics.log_query(
            question=question_req.question,
            latency_ms=total_latency,
            retrieval_time_ms=retrieval_time,
            llm_time_ms=llm_time,
            chunks_retrieved=len(retrieved_chunks),
            confidence=confidence,
            avg_similarity=sum(c['score'] for c in retrieved_chunks) / len(retrieved_chunks)
        )
        
        return AnswerResponse(
            answer=answer,
            source_chunks=retrieved_chunks,
            confidence_score=confidence,
            latency_ms=round(total_latency, 2),
            document_ids=document_ids
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing question: {str(e)}")


@app.get("/documents/{document_id}", response_model=DocumentStatus)
async def get_document_status(document_id: str):
    """
    Get the processing status of a document
    """
    status = vector_store.get_document_status(document_id)
    
    if not status:
        raise HTTPException(status_code=404, detail="Document not found")
    
    return DocumentStatus(**status)


@app.get("/documents", response_model=List[DocumentStatus])
async def list_documents():
    """
    List all uploaded documents and their status
    """
    documents = vector_store.list_documents()
    return [DocumentStatus(**doc) for doc in documents]


@app.get("/metrics")
async def get_metrics():
    """
    Get system metrics
    """
    return metrics.get_summary()


@app.get("/health")
async def health_check():
    """
    Health check endpoint
    """
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "documents_count": len(vector_store.list_documents())
    }


@app.delete("/documents/{document_id}")
async def delete_document(document_id: str):
    """
    Delete a document and its embeddings
    """
    success = vector_store.delete_document(document_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Document not found")
    
    return {"message": "Document deleted successfully", "document_id": document_id}


if __name__ == "__main__":
    print("DEBUG: Starting Uvicorn server...")
    print("INFO:     Access the application at http://localhost:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)
