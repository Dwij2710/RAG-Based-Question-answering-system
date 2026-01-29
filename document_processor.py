"""
Document Processing Module
Handles text extraction and chunking strategies
"""
import re
from typing import List, Dict
import PyPDF2


class DocumentProcessor:
    """
    Process documents: extract text and chunk intelligently
    """
    
    # Chunk size: 512 tokens (~400 words)
    # Rationale explained in DESIGN_DECISIONS.md
    CHUNK_SIZE = 512
    CHUNK_OVERLAP = 50  # 10% overlap for context preservation
    
    def extract_text(self, file_path: str) -> str:
        """
        Extract text from PDF or TXT file
        
        Args:
            file_path: Path to the document
            
        Returns:
            Extracted text content
        """
        if file_path.endswith('.pdf'):
            return self._extract_from_pdf(file_path)
        elif file_path.endswith('.txt'):
            return self._extract_from_txt(file_path)
        else:
            raise ValueError(f"Unsupported file format: {file_path}")
    
    def _extract_from_pdf(self, file_path: str) -> str:
        """Extract text from PDF"""
        text = ""
        try:
            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                for page in pdf_reader.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
        except Exception as e:
            raise Exception(f"Error reading PDF: {str(e)}")
        
        return text.strip()
    
    def _extract_from_txt(self, file_path: str) -> str:
        """Extract text from TXT file"""
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                return file.read()
        except UnicodeDecodeError:
            # Try with different encoding
            with open(file_path, 'r', encoding='latin-1') as file:
                return file.read()
    
    def chunk_text(self, text: str, filename: str) -> List[Dict]:
        """
        Chunk text using semantic-aware strategy
        
        Strategy:
        1. Split by paragraphs (double newlines)
        2. Combine small paragraphs
        3. Split large paragraphs by sentences
        4. Ensure chunks are within token limits
        
        Args:
            text: Full document text
            filename: Original filename for metadata
            
        Returns:
            List of chunk dictionaries
        """
        # Clean text
        text = self._clean_text(text)
        
        # Split into paragraphs
        paragraphs = re.split(r'\n\s*\n', text)
        paragraphs = [p.strip() for p in paragraphs if p.strip()]
        
        chunks = []
        current_chunk = ""
        chunk_index = 0
        
        for paragraph in paragraphs:
            # Approximate token count (1 token ≈ 4 characters)
            para_tokens = len(paragraph) // 4
            current_tokens = len(current_chunk) // 4
            
            # If paragraph fits in current chunk
            if current_tokens + para_tokens <= self.CHUNK_SIZE:
                if current_chunk:
                    current_chunk += "\n\n" + paragraph
                else:
                    current_chunk = paragraph
            else:
                # Save current chunk if not empty
                if current_chunk:
                    chunks.append(self._create_chunk_dict(
                        current_chunk, 
                        chunk_index, 
                        filename
                    ))
                    chunk_index += 1
                
                # If paragraph is too large, split by sentences
                if para_tokens > self.CHUNK_SIZE:
                    sentence_chunks = self._split_by_sentences(paragraph)
                    for sent_chunk in sentence_chunks:
                        chunks.append(self._create_chunk_dict(
                            sent_chunk,
                            chunk_index,
                            filename
                        ))
                        chunk_index += 1
                    current_chunk = ""
                else:
                    current_chunk = paragraph
        
        # Add final chunk
        if current_chunk:
            chunks.append(self._create_chunk_dict(
                current_chunk,
                chunk_index,
                filename
            ))
        
        return chunks
    
    def _split_by_sentences(self, text: str) -> List[str]:
        """Split large paragraph by sentences"""
        # Simple sentence splitter
        sentences = re.split(r'(?<=[.!?])\s+', text)
        
        chunks = []
        current_chunk = ""
        
        for sentence in sentences:
            sent_tokens = len(sentence) // 4
            current_tokens = len(current_chunk) // 4
            
            if current_tokens + sent_tokens <= self.CHUNK_SIZE:
                if current_chunk:
                    current_chunk += " " + sentence
                else:
                    current_chunk = sentence
            else:
                if current_chunk:
                    chunks.append(current_chunk)
                current_chunk = sentence
        
        if current_chunk:
            chunks.append(current_chunk)
        
        return chunks
    
    def _clean_text(self, text: str) -> str:
        """Clean and normalize text"""
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text)
        # Restore paragraph breaks
        text = re.sub(r'([.!?])\s+', r'\1\n\n', text)
        # Remove special characters but keep punctuation
        text = re.sub(r'[^\w\s.,!?;:\-\'"()\n]', '', text)
        return text.strip()
    
    def _create_chunk_dict(self, text: str, index: int, filename: str) -> Dict:
        """Create chunk dictionary with metadata"""
        return {
            "text": text,
            "chunk_index": index,
            "filename": filename,
            "char_count": len(text),
            "approx_tokens": len(text) // 4
        }
