"""
LLM Service Module
Handles answer generation using retrieved context
"""
from typing import List, Dict, Tuple
import google.generativeai as genai
import os


class LLMService:
    """
    Generate answers using Google Gemini LLM with retrieved context
    """
    
    def __init__(self):
        """Initialize LLM service"""
        # Check for API key
        self.api_key = os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            print("WARNING: GEMINI_API_KEY not set. Using mock responses.")
            self.client = None
        else:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel('gemini-flash-latest')
            self.client = True # Flag to indicate readiness
    
    def generate_answer(
        self, 
        question: str, 
        retrieved_chunks: List[Dict]
    ) -> Tuple[str, float]:
        """
        Generate answer using LLM with retrieved context
        
        Args:
            question: User's question
            retrieved_chunks: List of relevant chunks from vector store
            
        Returns:
            Tuple of (answer, confidence_score)
        """
        # Build context from retrieved chunks
        context = self._build_context(retrieved_chunks)
        
        # Create prompt
        prompt = self._create_prompt(question, context)
        
        # Generate answer
        if self.client:
            answer = self._generate_with_gemini(prompt)
        else:
            answer = self._generate_mock_answer(question, retrieved_chunks)
        
        # Calculate confidence based on similarity scores
        confidence = self._calculate_confidence(retrieved_chunks)
        
        return answer, confidence
    
    def _build_context(self, chunks: List[Dict]) -> str:
        """Build context string from retrieved chunks"""
        context_parts = []
        
        for i, chunk in enumerate(chunks, 1):
            context_parts.append(
                f"[Source {i}] (from {chunk['filename']}, similarity: {chunk['score']:.3f})\n"
                f"{chunk['text']}\n"
            )
        
        return "\n".join(context_parts)
    
    def _create_prompt(self, question: str, context: str) -> str:
        """Create prompt for LLM"""
        return f"""You are a helpful AI assistant answering questions based on provided documents.

Context from documents:
{context}

Question: {question}

Instructions:
1. Answer the question using ONLY information from the provided context
2. If the context doesn't contain enough information to answer, say so clearly
3. Cite which source(s) you used (e.g., "According to Source 1...")
4. Be concise but complete
5. If information is contradictory across sources, mention this

Answer:"""
    
    def _generate_with_gemini(self, prompt: str) -> str:
        """Generate answer using Gemini API"""
        try:
            response = self.model.generate_content(prompt)
            return response.text
            
        except Exception as e:
            return f"Error generating answer: {str(e)}"
    
    def _generate_mock_answer(self, question: str, chunks: List[Dict]) -> str:
        """Generate mock answer when API key is not available"""
        sources = [f"Source {i+1}" for i in range(min(3, len(chunks)))]
        return (
            f"Based on the provided documents ({', '.join(sources)}), "
            f"here is the answer to your question about '{question[:50]}...'.\n\n"
            f"[Note: This is a mock response. Set GEMINI_API_KEY environment variable "
            f"to use actual Gemini LLM for answer generation.]\n\n"
            f"The retrieved context contains {len(chunks)} relevant passages that discuss this topic. "
            f"The most relevant passage (similarity score: {chunks[0]['score']:.3f}) comes from "
            f"{chunks[0]['filename']}."
        )
    
    def _calculate_confidence(self, chunks: List[Dict]) -> float:
        """
        Calculate confidence score based on retrieval quality
        
        Factors:
        - Average similarity score
        - Number of high-quality chunks (score > 0.7)
        - Consistency across sources
        """
        if not chunks:
            return 0.0
        
        # Average similarity
        avg_similarity = sum(chunk['score'] for chunk in chunks) / len(chunks)
        
        # Count high-quality chunks
        high_quality = sum(1 for chunk in chunks if chunk['score'] > 0.7)
        quality_ratio = high_quality / len(chunks)
        
        # Combined confidence (weighted average)
        confidence = (avg_similarity * 0.7) + (quality_ratio * 0.3)
        
        return min(1.0, confidence)
