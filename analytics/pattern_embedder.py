"""
Pattern Embedder - Celery Tasks
================================
Embeds drift events into vector DB for similarity search and learning.
Uses pgvector in PostgreSQL (already have it from Rivet KB).
"""

import os
import sys
from datetime import datetime
from typing import Dict, Any, List, Optional
import json
from pathlib import Path

sys.path.insert(0, '/opt/master_of_puppets')
from celery_app import app
from workers.base_worker import BaseAgent, with_token_tracking

# Database config
DB_CONFIG = {
    "host": os.getenv("POSTGRES_HOST", "localhost"),
    "port": int(os.getenv("POSTGRES_PORT", "5432")),
    "database": os.getenv("POSTGRES_DB", "rivet"),
    "user": os.getenv("POSTGRES_USER", "rivet"),
    "password": os.getenv("POSTGRES_PASSWORD", "rivet_factory_2025!"),
}


class PatternEmbedder(BaseAgent):
    """Embeds drift patterns for similarity search."""
    
    def __init__(self):
        super().__init__("PatternEmbedder")
        self.conn = None
        self.embedding_dim = 1536  # OpenAI/Gemini embedding size
        self._ensure_table()
    
    def _get_connection(self):
        """Get database connection."""
        if self.conn is None or self.conn.closed:
            try:
                import psycopg2
                self.conn = psycopg2.connect(**DB_CONFIG)
            except Exception as e:
                self.logger.error(f"DB connection failed: {e}")
                return None
        return self.conn
    
    def _ensure_table(self):
        """Create drift_patterns table if needed."""
        conn = self._get_connection()
        if not conn:
            return
        
        try:
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS drift_patterns (
                    id SERIAL PRIMARY KEY,
                    pattern_id VARCHAR(100) UNIQUE NOT NULL,
                    metric_name VARCHAR(100) NOT NULL,
                    vendor VARCHAR(50),
                    plc_ip VARCHAR(50),
                    drift_magnitude FLOAT,
                    severity VARCHAR(20),
                    description TEXT,
                    resolution TEXT,
                    outcome VARCHAR(50),  -- resolved, false_positive, escalated
                    detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    resolved_at TIMESTAMP,
                    related_metrics TEXT[],
                    embedding vector(1536),
                    metadata JSONB
                )
            """)
            # Create indexes
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_patterns_metric ON drift_patterns(metric_name)
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_patterns_vendor ON drift_patterns(vendor)
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_patterns_embedding ON drift_patterns 
                USING hnsw (embedding vector_cosine_ops)
            """)
            conn.commit()
            cur.close()
        except Exception as e:
            self.logger.warning(f"Table creation: {e}")
            conn.rollback()
    
    def _generate_description(self, drift_event: Dict) -> str:
        """Generate text description for embedding."""
        parts = [
            f"Sensor {drift_event.get('metric', 'unknown')}",
            f"on {drift_event.get('vendor', 'unknown')} PLC",
            f"drifted {drift_event.get('drift_sigma', 0):.1f} sigma",
            f"from baseline.",
            f"Current value: {drift_event.get('current_value', 'N/A')}",
            f"Baseline mean: {drift_event.get('baseline_mean', 'N/A')}",
            f"Severity: {drift_event.get('severity', 'unknown')}",
        ]
        
        if drift_event.get('related_metrics'):
            parts.append(f"Related metrics: {', '.join(drift_event['related_metrics'])}")
        
        return " ".join(parts)
    
    def _get_embedding(self, text: str) -> Optional[List[float]]:
        """Generate embedding for text using available model."""
        
        # Try Gemini first (FREE!)
        gemini_key = os.getenv("GEMINI_API_KEY")
        if gemini_key:
            try:
                import requests
                response = requests.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/text-embedding-004:embedContent?key={gemini_key}",
                    json={
                        "model": "models/text-embedding-004",
                        "content": {"parts": [{"text": text}]}
                    },
                    timeout=30
                )
                if response.ok:
                    data = response.json()
                    embedding = data.get("embedding", {}).get("values", [])
                    if embedding:
                        # Gemini returns 768 dims, pad to 1536 for compatibility
                        if len(embedding) < 1536:
                            embedding.extend([0.0] * (1536 - len(embedding)))
                        self.logger.info("Used Gemini embedding (free)")
                        return embedding[:1536]
            except Exception as e:
                self.logger.warning(f"Gemini embedding failed: {e}")
        
        # Try Groq (if available) - no embeddings, skip
        
        # Try DeepSeek (if available) - no embeddings API yet, skip
        
        # Try OpenAI as fallback
        openai_key = os.getenv("OPENAI_API_KEY")
        if openai_key:
            try:
                import openai
                client = openai.OpenAI(api_key=openai_key)
                response = client.embeddings.create(
                    model="text-embedding-3-small",
                    input=text
                )
                return response.data[0].embedding
            except Exception as e:
                self.logger.warning(f"OpenAI embedding failed: {e}")
        
        # Try sentence-transformers (local, free)
        try:
            from sentence_transformers import SentenceTransformer
            model = SentenceTransformer('all-MiniLM-L6-v2')
            embedding = model.encode(text).tolist()
            # Pad to 1536 dimensions if needed
            if len(embedding) < 1536:
                embedding.extend([0.0] * (1536 - len(embedding)))
            return embedding[:1536]
        except Exception as e:
            self.logger.warning(f"Local embedding failed: {e}")
        
        # Return None if no embedding method available
        return None
    
    def store_pattern(self, drift_event: Dict) -> Dict:
        """Store a drift pattern with embedding."""
        conn = self._get_connection()
        if not conn:
            return {"error": "No database connection"}
        
        # Generate pattern ID
        pattern_id = f"{drift_event.get('metric', 'unknown')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Generate description and embedding
        description = self._generate_description(drift_event)
        embedding = self._get_embedding(description)
        
        try:
            cur = conn.cursor()
            
            if embedding:
                cur.execute("""
                    INSERT INTO drift_patterns 
                    (pattern_id, metric_name, vendor, plc_ip, drift_magnitude, severity,
                     description, related_metrics, embedding, metadata)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (
                    pattern_id,
                    drift_event.get("metric"),
                    drift_event.get("vendor"),
                    drift_event.get("plc_ip"),
                    drift_event.get("drift_sigma"),
                    drift_event.get("severity"),
                    description,
                    drift_event.get("related_metrics", []),
                    embedding,
                    json.dumps(drift_event)
                ))
            else:
                # Store without embedding
                cur.execute("""
                    INSERT INTO drift_patterns 
                    (pattern_id, metric_name, vendor, plc_ip, drift_magnitude, severity,
                     description, related_metrics, metadata)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (
                    pattern_id,
                    drift_event.get("metric"),
                    drift_event.get("vendor"),
                    drift_event.get("plc_ip"),
                    drift_event.get("drift_sigma"),
                    drift_event.get("severity"),
                    description,
                    drift_event.get("related_metrics", []),
                    json.dumps(drift_event)
                ))
            
            row_id = cur.fetchone()[0]
            conn.commit()
            cur.close()
            
            return {
                "status": "stored",
                "pattern_id": pattern_id,
                "db_id": row_id,
                "has_embedding": embedding is not None
            }
            
        except Exception as e:
            self.logger.error(f"Store pattern failed: {e}")
            conn.rollback()
            return {"error": str(e)}
    
    def find_similar(self, query_text: str, limit: int = 5, 
                    vendor: str = None) -> List[Dict]:
        """Find similar patterns using vector similarity."""
        conn = self._get_connection()
        if not conn:
            return []
        
        # Get query embedding
        embedding = self._get_embedding(query_text)
        if not embedding:
            self.logger.warning("Could not generate embedding for query")
            return self._fallback_search(query_text, limit, vendor)
        
        try:
            cur = conn.cursor()
            
            # Vector similarity search
            sql = """
                SELECT pattern_id, metric_name, vendor, severity, description,
                       resolution, outcome, detected_at,
                       1 - (embedding <=> %s::vector) as similarity
                FROM drift_patterns
                WHERE embedding IS NOT NULL
            """
            params = [embedding]
            
            if vendor:
                sql += " AND (vendor = %s OR vendor IS NULL)"
                params.append(vendor)
            
            sql += " ORDER BY embedding <=> %s::vector LIMIT %s"
            params.extend([embedding, limit])
            
            cur.execute(sql, params)
            
            results = []
            for row in cur.fetchall():
                results.append({
                    "pattern_id": row[0],
                    "metric": row[1],
                    "vendor": row[2],
                    "severity": row[3],
                    "description": row[4],
                    "resolution": row[5],
                    "outcome": row[6],
                    "detected_at": row[7].isoformat() if row[7] else None,
                    "similarity": round(row[8], 3) if row[8] else None,
                })
            
            cur.close()
            return results
            
        except Exception as e:
            self.logger.error(f"Similarity search failed: {e}")
            return []
    
    def _fallback_search(self, query: str, limit: int, vendor: str = None) -> List[Dict]:
        """Fallback to text search if no embeddings available."""
        conn = self._get_connection()
        if not conn:
            return []
        
        try:
            cur = conn.cursor()
            sql = """
                SELECT pattern_id, metric_name, vendor, severity, description,
                       resolution, outcome, detected_at
                FROM drift_patterns
                WHERE description ILIKE %s
            """
            params = [f"%{query}%"]
            
            if vendor:
                sql += " AND (vendor = %s OR vendor IS NULL)"
                params.append(vendor)
            
            sql += " ORDER BY detected_at DESC LIMIT %s"
            params.append(limit)
            
            cur.execute(sql, params)
            
            results = []
            for row in cur.fetchall():
                results.append({
                    "pattern_id": row[0],
                    "metric": row[1],
                    "vendor": row[2],
                    "severity": row[3],
                    "description": row[4],
                    "resolution": row[5],
                    "outcome": row[6],
                    "detected_at": row[7].isoformat() if row[7] else None,
                    "similarity": None,  # No similarity score for text search
                })
            
            cur.close()
            return results
            
        except Exception as e:
            self.logger.error(f"Fallback search failed: {e}")
            return []
    
    def update_outcome(self, pattern_id: str, outcome: str, resolution: str = None) -> bool:
        """Update pattern outcome after resolution."""
        conn = self._get_connection()
        if not conn:
            return False
        
        try:
            cur = conn.cursor()
            cur.execute("""
                UPDATE drift_patterns 
                SET outcome = %s, resolution = %s, resolved_at = CURRENT_TIMESTAMP
                WHERE pattern_id = %s
            """, (outcome, resolution, pattern_id))
            
            updated = cur.rowcount > 0
            conn.commit()
            cur.close()
            return updated
            
        except Exception as e:
            self.logger.error(f"Update outcome failed: {e}")
            conn.rollback()
            return False
    
    def get_stats(self) -> Dict:
        """Get pattern statistics."""
        conn = self._get_connection()
        if not conn:
            return {"error": "No connection"}
        
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT 
                    COUNT(*) as total,
                    COUNT(CASE WHEN embedding IS NOT NULL THEN 1 END) as with_embeddings,
                    COUNT(CASE WHEN outcome IS NOT NULL THEN 1 END) as resolved
                FROM drift_patterns
            """)
            row = cur.fetchone()
            cur.close()
            
            return {
                "total_patterns": row[0],
                "with_embeddings": row[1],
                "resolved": row[2],
            }
        except Exception as e:
            return {"error": str(e)}


embedder = PatternEmbedder()


@app.task(bind=True, name='pattern.store')
@with_token_tracking('pattern')
def store(self, drift_event: Dict) -> Dict:
    """Store a drift pattern for learning."""
    embedder.log_start('store', metric=drift_event.get('metric'))
    result = embedder.store_pattern(drift_event)
    embedder.log_complete('store', result)
    return result


@app.task(bind=True, name='pattern.find_similar')
@with_token_tracking('pattern')
def find_similar(self, query: str, limit: int = 5, vendor: str = None) -> List[Dict]:
    """Find similar patterns."""
    embedder.log_start('find_similar', query=query[:50])
    results = embedder.find_similar(query, limit, vendor)
    embedder.log_complete('find_similar', {"count": len(results)})
    return results


@app.task(bind=True, name='pattern.update_outcome')
def update_outcome(self, pattern_id: str, outcome: str, resolution: str = None) -> Dict:
    """Update pattern outcome (resolved, false_positive, escalated)."""
    success = embedder.update_outcome(pattern_id, outcome, resolution)
    return {"updated": success, "pattern_id": pattern_id, "outcome": outcome}


@app.task(bind=True, name='pattern.stats')
def stats(self) -> Dict:
    """Get pattern statistics."""
    return embedder.get_stats()


@app.task(bind=True, name='pattern.health')
def health(self) -> Dict:
    """Health check."""
    s = embedder.get_stats()
    return {
        "status": "ok" if "error" not in s else "degraded",
        "agent": "PatternEmbedder",
        "patterns": s.get("total_patterns", 0),
        "with_embeddings": s.get("with_embeddings", 0)
    }
