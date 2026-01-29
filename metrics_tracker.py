"""
Metrics Tracker Module
Track and analyze system performance metrics
"""
import json
import os
from datetime import datetime
from typing import List, Dict
from collections import defaultdict


class MetricsTracker:
    """
    Track system metrics: latency, similarity scores, retrieval quality
    """
    
    def __init__(self, metrics_file: str = "metrics/query_metrics.json"):
        """Initialize metrics tracker"""
        self.metrics_file = metrics_file
        os.makedirs(os.path.dirname(metrics_file), exist_ok=True)
        
        self.queries = []
        self._load_metrics()
    
    def log_query(
        self,
        question: str,
        latency_ms: float,
        retrieval_time_ms: float,
        llm_time_ms: float,
        chunks_retrieved: int,
        confidence: float,
        avg_similarity: float
    ):
        """
        Log query metrics
        
        Args:
            question: User question
            latency_ms: Total query latency in milliseconds
            retrieval_time_ms: Time for retrieval phase
            llm_time_ms: Time for LLM generation
            chunks_retrieved: Number of chunks retrieved
            confidence: Answer confidence score
            avg_similarity: Average similarity score of retrieved chunks
        """
        entry = {
            'timestamp': datetime.now().isoformat(),
            'question': question[:100],  # Truncate for privacy
            'latency_ms': round(latency_ms, 2),
            'retrieval_time_ms': round(retrieval_time_ms, 2),
            'llm_time_ms': round(llm_time_ms, 2),
            'chunks_retrieved': chunks_retrieved,
            'confidence': round(confidence, 3),
            'avg_similarity': round(avg_similarity, 3)
        }
        
        self.queries.append(entry)
        
        # Save periodically (every 10 queries)
        if len(self.queries) % 10 == 0:
            self._save_metrics()
    
    def get_summary(self) -> Dict:
        """
        Get metrics summary
        
        Returns:
            Dictionary with aggregated metrics
        """
        if not self.queries:
            return {
                'total_queries': 0,
                'message': 'No queries logged yet'
            }
        
        # Calculate statistics
        latencies = [q['latency_ms'] for q in self.queries]
        retrieval_times = [q['retrieval_time_ms'] for q in self.queries]
        llm_times = [q['llm_time_ms'] for q in self.queries]
        confidences = [q['confidence'] for q in self.queries]
        similarities = [q['avg_similarity'] for q in self.queries]
        
        summary = {
            'total_queries': len(self.queries),
            'latency': {
                'avg_ms': round(sum(latencies) / len(latencies), 2),
                'min_ms': round(min(latencies), 2),
                'max_ms': round(max(latencies), 2),
                'p95_ms': round(self._percentile(latencies, 95), 2),
                'p99_ms': round(self._percentile(latencies, 99), 2)
            },
            'retrieval': {
                'avg_time_ms': round(sum(retrieval_times) / len(retrieval_times), 2),
                'avg_similarity': round(sum(similarities) / len(similarities), 3)
            },
            'llm': {
                'avg_time_ms': round(sum(llm_times) / len(llm_times), 2)
            },
            'confidence': {
                'avg': round(sum(confidences) / len(confidences), 3),
                'min': round(min(confidences), 3),
                'max': round(max(confidences), 3)
            },
            'quality_metrics': {
                'high_confidence_queries': sum(1 for c in confidences if c > 0.7),
                'low_similarity_queries': sum(1 for s in similarities if s < 0.5),
                'slow_queries_over_1s': sum(1 for l in latencies if l > 1000)
            }
        }
        
        # Add recent queries
        summary['recent_queries'] = self.queries[-5:] if len(self.queries) > 5 else self.queries
        
        return summary
    
    def _percentile(self, data: List[float], percentile: int) -> float:
        """Calculate percentile"""
        if not data:
            return 0.0
        sorted_data = sorted(data)
        index = int(len(sorted_data) * (percentile / 100))
        return sorted_data[min(index, len(sorted_data) - 1)]
    
    def _save_metrics(self):
        """Save metrics to file"""
        with open(self.metrics_file, 'w') as f:
            json.dump({
                'queries': self.queries,
                'last_updated': datetime.now().isoformat()
            }, f, indent=2)
    
    def _load_metrics(self):
        """Load metrics from file if exists"""
        if os.path.exists(self.metrics_file):
            try:
                with open(self.metrics_file, 'r') as f:
                    data = json.load(f)
                    self.queries = data.get('queries', [])
                    print(f"Loaded {len(self.queries)} historical queries")
            except Exception as e:
                print(f"Error loading metrics: {e}")
                self.queries = []
