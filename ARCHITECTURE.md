# System Architecture

## Architecture Diagram

```mermaid
graph TD
    User[User] -->|Uploads PDF/TXT| API[FastAPI Server]
    User -->|Asks Question| API
    
    subgraph "Backend System"
        API -->|Extracts Text| Processor[Document Processor]
        Processor -->|Chunks Text| Processor
        Processor -->|Generates Embeddings| VectorStore[Vector Store (FAISS)]
        
        API -->|Search Query| VectorStore
        VectorStore -->|Retrieves Chunks| API
        
        API -->|Context + Question| LLM[LLM Service (Google Gemini)]
        LLM -->|Generates Answer| API
    end
    
    VectorStore -->|Persists Data| Disk[Local Storage]
    
    style User fill:#f9f,stroke:#333
    style API fill:#bbf,stroke:#333
    style VectorStore fill:#bfb,stroke:#333
    style LLM fill:#fb9,stroke:#333
```

## Component Description

1.  **FastAPI Server**: Handles HTTP requests, file uploads, and routing.
2.  **Document Processor**: 
    - Extracts text from PDF/TXT files.
    - Chunks text into 512-token segments (see `DESIGN_DECISIONS.md`).
3.  **Vector Store (FAISS)**:
    - Generates embeddings using `sentence-transformers`.
    - Stores vectors locally.
    - Performs similarity search (Cosine/Inner Product).
4.  **LLM Service (Google Gemini)**:
    - Recieves context + question.
    - Generates natural language answer.
5.  **Metrics Tracker**:
    - Logs latency, similarity scores, and usage stats.
