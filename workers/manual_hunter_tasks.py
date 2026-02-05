"""
MANUAL HUNTER - Celery Tasks
============================
Searches industrial manuals for troubleshooting information.
Connected to pgvector knowledge base in PostgreSQL.
"""

import os
import sys
from typing import List, Dict, Any, Optional
sys.path.insert(0, '/opt/master_of_puppets')
from celery_app import app
from workers.base_worker import BaseAgent, with_retry, with_token_tracking, with_celery_tracing
from observability import traced, track_llm_call, track_api_call

# Database connection
DB_CONFIG = {
    "host": os.getenv("POSTGRES_HOST", "localhost"),
    "port": int(os.getenv("POSTGRES_PORT", "5432")),
    "database": os.getenv("POSTGRES_DB", "rivet"),
    "user": os.getenv("POSTGRES_USER", "rivet"),
    "password": os.getenv("POSTGRES_PASSWORD", "rivet_factory_2025!"),
}


class ManualHunter(BaseAgent):
    """Searches manuals for troubleshooting info using pgvector."""
    
    def __init__(self):
        super().__init__("ManualHunter")
        self.conn = None
    
    def _get_connection(self):
        """Get or create database connection."""
        if self.conn is None or self.conn.closed:
            try:
                import psycopg2
                self.conn = psycopg2.connect(**DB_CONFIG)
            except ImportError:
                self.logger.error("psycopg2 not installed")
                return None
            except Exception as e:
                self.logger.error(f"DB connection failed: {e}")
                return None
        return self.conn
    
    def search_fulltext(self, query: str, vendor: str = None, limit: int = 5) -> List[Dict]:
        """Full-text search on knowledge atoms."""
        conn = self._get_connection()
        if not conn:
            return []
        
        try:
            cur = conn.cursor()
            
            # Build query with optional vendor filter
            sql = """
                SELECT atom_id, atom_type, vendor, product, title, 
                       LEFT(summary, 500) as summary,
                       ts_rank(to_tsvector('english', title || ' ' || summary || ' ' || content), 
                               plainto_tsquery('english', %s)) as rank
                FROM knowledge_atoms
                WHERE to_tsvector('english', title || ' ' || summary || ' ' || content) 
                      @@ plainto_tsquery('english', %s)
            """
            params = [query, query]
            
            if vendor:
                sql += " AND (vendor ILIKE %s OR product ILIKE %s)"
                params.extend([f"%{vendor}%", f"%{vendor}%"])
            
            sql += " ORDER BY rank DESC LIMIT %s"
            params.append(limit)
            
            cur.execute(sql, params)
            columns = [desc[0] for desc in cur.description]
            results = [dict(zip(columns, row)) for row in cur.fetchall()]
            cur.close()
            
            return results
            
        except Exception as e:
            self.logger.error(f"Search failed: {e}")
            conn.rollback()
            return []
    
    def search_semantic(self, query: str, vendor: str = None, limit: int = 5) -> List[Dict]:
        """Semantic search using embeddings (requires embedding the query first)."""
        # For now, fall back to full-text search
        # TODO: Add embedding generation via OpenAI/Ollama
        return self.search_fulltext(query, vendor, limit)
    
    def search(self, query: str, plc_vendor: str = None, limit: int = 5) -> dict:
        """Search manuals for relevant information."""
        self.logger.info(f"Searching manuals: {query} (vendor: {plc_vendor})")
        
        # Try full-text search
        results = self.search_fulltext(query, plc_vendor, limit)
        
        return {
            "query": query,
            "vendor": plc_vendor,
            "results": results,
            "count": len(results),
            "search_type": "fulltext",
            "database": "rivet/knowledge_atoms"
        }
    
    def get_stats(self) -> dict:
        """Get knowledge base statistics."""
        conn = self._get_connection()
        if not conn:
            return {"error": "No database connection"}
        
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT 
                    COUNT(*) as total_atoms,
                    COUNT(DISTINCT vendor) as vendors,
                    COUNT(DISTINCT product) as products,
                    COUNT(CASE WHEN embedding IS NOT NULL THEN 1 END) as with_embeddings
                FROM knowledge_atoms
            """)
            row = cur.fetchone()
            cur.close()
            
            return {
                "total_atoms": row[0],
                "vendors": row[1],
                "products": row[2],
                "with_embeddings": row[3],
            }
        except Exception as e:
            self.logger.error(f"Stats query failed: {e}")
            return {"error": str(e)}


manual_hunter = ManualHunter()


@app.task(bind=True, name='manual_hunter.search_manuals')
@with_token_tracking('manual_hunter')
def search_manuals(self, query: str, plc_vendor: str = None, limit: int = 5) -> dict:
    """
    Search industrial manuals for troubleshooting information.
    
    Args:
        query: Search query (e.g., "ControlLogix fault" or "motor overload")
        plc_vendor: Optional vendor filter (rockwell, siemens, abb)
        limit: Max results to return
    
    Returns:
        Relevant manual excerpts from knowledge base
    """
    manual_hunter.log_start('search_manuals', query=query, plc_vendor=plc_vendor)
    
    try:
        result = manual_hunter.search(query, plc_vendor, limit)
        manual_hunter.log_complete('search_manuals', result)
        return result
    except Exception as e:
        manual_hunter.log_error('search_manuals', e)
        raise


@app.task(bind=True, name='manual_hunter.get_stats')
@with_celery_tracing("get_stats")
@traced(name="get_stats", layer="execution")
def get_stats(self) -> dict:
    """Get knowledge base statistics."""
    return manual_hunter.get_stats()


@app.task(bind=True, name='manual_hunter.health')
@with_celery_tracing("health")
@traced(name="health", layer="execution")
def health(self) -> dict:
    """Health check with DB status."""
    stats = manual_hunter.get_stats()
    return {
        "status": "ok" if "total_atoms" in stats else "degraded",
        "agent": "ManualHunter",
        "knowledge_base": stats
    }


# ============== BUSINESS DOCS INDEXING ==============

BUSINESS_DOCS_DIR = "/opt/factorylm-sync/business-docs"


def extract_text_from_file(filepath: str) -> str:
    """Extract text content from various file types."""
    import os
    from pathlib import Path
    
    path = Path(filepath)
    suffix = path.suffix.lower()
    
    try:
        if suffix == '.txt' or suffix == '.md':
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                return f.read()
        
        elif suffix == '.pdf':
            try:
                import pypdf
                reader = pypdf.PdfReader(filepath)
                text = ""
                for page in reader.pages:
                    text += page.extract_text() + "\n"
                return text
            except ImportError:
                return f"[PDF file - pypdf not installed: {path.name}]"
        
        elif suffix in ['.docx', '.doc']:
            try:
                from docx import Document
                doc = Document(filepath)
                return "\n".join([para.text for para in doc.paragraphs])
            except ImportError:
                return f"[Word doc - python-docx not installed: {path.name}]"
        
        elif suffix == '.json':
            import json
            with open(filepath, 'r') as f:
                return json.dumps(json.load(f), indent=2)
        
        else:
            # Try reading as text
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                return f.read()
    
    except Exception as e:
        return f"[Error reading {path.name}: {e}]"


@app.task(bind=True, name='manual_hunter.index_business_docs')
@with_token_tracking('manual_hunter')
def index_business_docs(self) -> Dict:
    """
    Index all documents in the synced business-docs folder.
    Adds them to the knowledge base for search.
    """
    import os
    from pathlib import Path
    from datetime import datetime
    
    manual_hunter.log_start('index_business_docs')
    
    docs_path = Path(BUSINESS_DOCS_DIR)
    if not docs_path.exists():
        return {"error": "Business docs folder not found", "path": BUSINESS_DOCS_DIR}
    
    indexed = 0
    errors = []
    
    conn = manual_hunter._get_connection()
    if not conn:
        return {"error": "Database connection failed"}
    
    try:
        cur = conn.cursor()
        
        # Ensure table exists
        cur.execute("""
            CREATE TABLE IF NOT EXISTS business_docs (
                id SERIAL PRIMARY KEY,
                file_path VARCHAR(500) UNIQUE,
                filename VARCHAR(255),
                file_type VARCHAR(50),
                content TEXT,
                indexed_at TIMESTAMP DEFAULT NOW(),
                file_modified TIMESTAMP
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_business_docs_content ON business_docs USING gin(to_tsvector('english', content))")
        conn.commit()
        
        # Scan all files
        for root, dirs, files in os.walk(docs_path):
            for filename in files:
                filepath = os.path.join(root, filename)
                suffix = Path(filename).suffix.lower()
                
                # Skip hidden files and non-documents
                if filename.startswith('.'):
                    continue
                if suffix not in ['.txt', '.md', '.pdf', '.docx', '.doc', '.json', '.csv']:
                    continue
                
                try:
                    # Get file modification time
                    mtime = datetime.fromtimestamp(os.path.getmtime(filepath))
                    
                    # Check if already indexed with same mtime
                    cur.execute("""
                        SELECT id FROM business_docs 
                        WHERE file_path = %s AND file_modified = %s
                    """, (filepath, mtime))
                    
                    if cur.fetchone():
                        continue  # Already indexed
                    
                    # Extract text
                    content = extract_text_from_file(filepath)
                    
                    # Upsert
                    cur.execute("""
                        INSERT INTO business_docs (file_path, filename, file_type, content, file_modified)
                        VALUES (%s, %s, %s, %s, %s)
                        ON CONFLICT (file_path) 
                        DO UPDATE SET content = EXCLUDED.content, 
                                      file_modified = EXCLUDED.file_modified,
                                      indexed_at = NOW()
                    """, (filepath, filename, suffix, content, mtime))
                    
                    indexed += 1
                    
                except Exception as e:
                    errors.append({"file": filename, "error": str(e)})
        
        conn.commit()
        cur.close()
        
    except Exception as e:
        conn.rollback()
        return {"error": str(e)}
    
    result = {
        "indexed": indexed,
        "errors": len(errors),
        "error_details": errors[:5],  # First 5 errors
    }
    
    manual_hunter.log_complete('index_business_docs', result)
    return result


@app.task(bind=True, name='manual_hunter.search_business_docs')
@with_token_tracking('manual_hunter')
def search_business_docs(self, query: str, limit: int = 5) -> Dict:
    """Search indexed business documents."""
    manual_hunter.log_start('search_business_docs', query=query)
    
    conn = manual_hunter._get_connection()
    if not conn:
        return {"error": "Database connection failed", "results": []}
    
    try:
        cur = conn.cursor()
        
        cur.execute("""
            SELECT filename, file_type, 
                   LEFT(content, 500) as snippet,
                   ts_rank(to_tsvector('english', content), plainto_tsquery('english', %s)) as rank
            FROM business_docs
            WHERE to_tsvector('english', content) @@ plainto_tsquery('english', %s)
            ORDER BY rank DESC
            LIMIT %s
        """, (query, query, limit))
        
        columns = ['filename', 'file_type', 'snippet', 'rank']
        results = [dict(zip(columns, row)) for row in cur.fetchall()]
        cur.close()
        
        return {
            "query": query,
            "count": len(results),
            "results": results,
        }
        
    except Exception as e:
        return {"error": str(e), "results": []}
