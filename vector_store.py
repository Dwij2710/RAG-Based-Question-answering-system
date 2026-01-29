import os
import json
import pickle
import numpy as np
from typing import List, Dict, Optional
import google.generativeai as genai
from rank_bm25 import BM25Okapi

class VectorStore:
    """
    Vector store using Numpy (Cosine Similarity) + BM25 (Keyword) + Google Gemini Embeddings
    Replacing FAISS/Torch due to local environment compatibility issues.
    """
    
    def __init__(self, model_name: str = "models/text-embedding-004", storage_dir: str = "vector_store"):
        """
        Initialize vector store
        
        Args:
            model_name: Google Gemini embedding model
            storage_dir: Directory to persist vector store
        """
        self.storage_dir = storage_dir
        os.makedirs(storage_dir, exist_ok=True)
        
        # Configure GenAI
        self.api_key = os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            print("WARNING: GEMINI_API_KEY not set. Vector store will fail to generate embeddings.")
        else:
            genai.configure(api_key=self.api_key)
            
        self.embedding_model_name = model_name
        
        # In-memory storage
        self.vectors = None # Numpy array
        self.chunks_metadata = []  # List of chunk metadata
        self.document_metadata = {}  # Document status and info
        
        # BM25 Index
        self.bm25 = None
        self.tokenized_corpus = []
        
        # Load existing data if available
        self._load_from_disk()
    
    def add_chunks(self, document_id: str, chunks: List[Dict]):
        """
        Generate embeddings for chunks and add to vector store
        """
        if not chunks:
            return
        
        # Extract text from chunks
        texts = [chunk['text'] for chunk in chunks]
        
        # Generate embeddings using Google GenAI
        print(f"Generating embeddings for {len(texts)} chunks using Gemini...")
        try:
            # Batch generation if possible, but simplest is one by one or small batches
            embeddings = []
            # Process in batches of 20 to avoid payload limits
            batch_size = 20
            for i in range(0, len(texts), batch_size):
                batch_texts = texts[i:i+batch_size]
                try:
                    result = genai.embed_content(
                        model=self.embedding_model_name,
                        content=batch_texts,
                        task_type="retrieval_document"
                    )
                    # Result is a dict with 'embedding' key which is a list of embeddings
                    batch_embeddings = result['embedding']
                    embeddings.extend(batch_embeddings)
                except Exception as e:
                    print(f"Error embedding batch {i}: {e}")
                    raise e
                    
            embeddings_np = np.array(embeddings, dtype='float32')
            
            # Add to Vectors (Numpy)
            if self.vectors is None:
                self.vectors = embeddings_np
            else:
                self.vectors = np.vstack((self.vectors, embeddings_np))
            
            # Add to BM25 Corpus
            for text in texts:
                tokens = self._tokenize(text)
                self.tokenized_corpus.append(tokens)
                
            # Rebuild BM25 Index
            if self.tokenized_corpus:
                self.bm25 = BM25Okapi(self.tokenized_corpus)

            # Store metadata
            for i, chunk in enumerate(chunks):
                chunk_meta = {
                    'document_id': document_id,
                    'chunk_id': f"{document_id}_chunk_{i}",
                    'text': chunk['text'],
                    'chunk_index': chunk['chunk_index'],
                    'filename': chunk['filename'],
                    'char_count': chunk['char_count'],
                    'approx_tokens': chunk['approx_tokens']
                }
                self.chunks_metadata.append(chunk_meta)
            
            # Save to disk
            self._save_to_disk()
            
        except Exception as e:
            print(f"Failed to generate embeddings: {e}")
            raise e
    
    def search(
        self, 
        query: str, 
        top_k: int = 5, 
        document_id: Optional[str] = None,
        alpha: float = 0.7
    ) -> List[Dict]:
        """
        Search using Cosine Similarity (Numpy) + BM25
        """
        if self.vectors is None or len(self.chunks_metadata) == 0:
            return []

        # --- Vector Search ---
        vector_results = {}
        try:
            embedding_result = genai.embed_content(
                model=self.embedding_model_name,
                content=query,
                task_type="retrieval_query"
            )
            query_embedding = np.array(embedding_result['embedding'], dtype='float32')
            
            # Cosine Similarity: A . B / (|A|*|B|)
            # Normalized Query
            norm_query = np.linalg.norm(query_embedding)
            if norm_query > 0:
                query_embedding = query_embedding / norm_query
                
            # Normalize document vectors 
            doc_norms = np.linalg.norm(self.vectors, axis=1)
            doc_norms[doc_norms == 0] = 1.0  # Avoid division by zero
            
            # Dot product
            if self.vectors.shape[1] == query_embedding.shape[0]:
                dot_products = np.dot(self.vectors, query_embedding)
                cosine_scores = dot_products / doc_norms
                
                for idx, score in enumerate(cosine_scores):
                     vector_results[idx] = float(score)
            else:
                print(f"Dimension mismatch: vectors {self.vectors.shape} vs query {query_embedding.shape}")

        except Exception as e:
            print(f"Error in vector search: {e}")

        # --- BM25 Search ---
        bm25_results = {}
        if self.bm25:
            tokenized_query = self._tokenize(query)
            bm25_scores = self.bm25.get_scores(tokenized_query)
            
            # Normalize BM25
            max_bm25 = max(bm25_scores) if len(bm25_scores) > 0 else 1.0
            if max_bm25 == 0: max_bm25 = 1.0
            
            for idx, score in enumerate(bm25_scores):
                 bm25_results[idx] = score / max_bm25

        # --- Hybrid Fusion ---
        all_candidates = set(vector_results.keys()) | set(bm25_results.keys())
        
        final_results = []
        for idx in all_candidates:
            if idx >= len(self.chunks_metadata): continue
            
            chunk_meta = self.chunks_metadata[idx].copy()
            
            if document_id and chunk_meta['document_id'] != document_id:
                continue
                
            v_score = vector_results.get(idx, 0.0)
            b_score = bm25_results.get(idx, 0.0)
            
            final_score = (alpha * v_score) + ((1 - alpha) * b_score)
            
            chunk_meta['score'] = final_score
            chunk_meta['vector_score'] = v_score
            chunk_meta['bm25_score'] = b_score
            
            final_results.append(chunk_meta)
            
        final_results.sort(key=lambda x: x['score'], reverse=True)
        return final_results[:top_k]
    
    def _tokenize(self, text: str) -> List[str]:
         return text.lower().split()

    def update_document_status(self, document_id: str, status: str, chunks_count: int, processed_at: Optional[str], filename: Optional[str] = None):
        """Update document processing status"""
        if document_id not in self.document_metadata:
            if not filename:
                filename = "unknown"
                for chunk in self.chunks_metadata:
                    if chunk['document_id'] == document_id:
                        filename = chunk['filename']
                        break
            
            self.document_metadata[document_id] = {
                'document_id': document_id,
                'filename': filename,
                'status': status,
                'chunks_count': chunks_count,
                'processed_at': processed_at
            }
        else:
            update_data = {
                'status': status,
                'chunks_count': chunks_count,
                'processed_at': processed_at
            }
            if filename:
                update_data['filename'] = filename
            self.document_metadata[document_id].update(update_data)
        
        self._save_to_disk()
    
    def get_document_status(self, document_id: str) -> Optional[Dict]:
        return self.document_metadata.get(document_id)
    
    def list_documents(self) -> List[Dict]:
        return list(self.document_metadata.values())
    
    def has_documents(self) -> bool:
        return len(self.chunks_metadata) > 0
    
    def delete_document(self, document_id: str) -> bool:
        if document_id not in self.document_metadata:
            return False
        
        del self.document_metadata[document_id]
        
        # Filter chunks
        remaining_indices = [i for i, c in enumerate(self.chunks_metadata) if c['document_id'] != document_id]
        
        if len(remaining_indices) == len(self.chunks_metadata):
            return False
            
        self.chunks_metadata = [self.chunks_metadata[i] for i in remaining_indices]
        if self.vectors is not None:
             self.vectors = self.vectors[remaining_indices]
             
        # Rebuild BM25
        self.tokenized_corpus = []
        if self.chunks_metadata:
            for chunk in self.chunks_metadata:
                self.tokenized_corpus.append(self._tokenize(chunk['text']))
            self.bm25 = BM25Okapi(self.tokenized_corpus)
        else:
            self.bm25 = None
            self.vectors = None
            
        self._save_to_disk()
        return True
    
    def _save_to_disk(self):
        if self.vectors is not None:
            np.save(os.path.join(self.storage_dir, "vectors.npy"), self.vectors)
        
        with open(os.path.join(self.storage_dir, "chunks_metadata.pkl"), 'wb') as f:
            pickle.dump(self.chunks_metadata, f)
        
        with open(os.path.join(self.storage_dir, "document_metadata.json"), 'w') as f:
            json.dump(self.document_metadata, f, indent=2)
    
    def _load_from_disk(self):
        vectors_path = os.path.join(self.storage_dir, "vectors.npy")
        chunks_path = os.path.join(self.storage_dir, "chunks_metadata.pkl")
        docs_path = os.path.join(self.storage_dir, "document_metadata.json")
        
        if os.path.exists(vectors_path):
            try:
                self.vectors = np.load(vectors_path)
                print(f"Loaded {len(self.vectors)} vectors")
            except Exception as e:
                print(f"Error loading vectors: {e}")
                self.vectors = None
        
        if os.path.exists(chunks_path):
            try:
                with open(chunks_path, 'rb') as f:
                    self.chunks_metadata = pickle.load(f)
                print(f"Loaded {len(self.chunks_metadata)} chunk metadata entries")
                
                # Rebuild BM25
                if self.chunks_metadata:
                     self.tokenized_corpus = [self._tokenize(chunk['text']) for chunk in self.chunks_metadata]
                     self.bm25 = BM25Okapi(self.tokenized_corpus)
            except Exception as e:
                print(f"Error loading metadata: {e}")
                self.chunks_metadata = []
        
        if os.path.exists(docs_path):
            try:
                with open(docs_path, 'r') as f:
                    self.document_metadata = json.load(f)
            except Exception as e:
                print(f"Error loading document metadata: {e}")
                self.document_metadata = {}
