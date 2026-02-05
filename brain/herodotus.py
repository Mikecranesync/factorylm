"""
HERODOTUS - The Archivist
Named after the Father of History (c. 484 – c. 425 BC)

Role: Collect, synthesize, and archive data from all sources into Mike's Brain.
- Pulls Telegram logs
- Extracts GitHub activity  
- Processes synthetic KB entries
- Ingests user data exhaust

"The only good is knowledge, and the only evil is ignorance." - Herodotus
"""

import os
import json
import asyncio
from datetime import datetime
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum

# Placeholder imports - will be implemented
# from brain.db import BrainDB
# from brain.embeddings import get_embedding


class DataSource(Enum):
    TELEGRAM = "telegram"
    GITHUB = "github"
    SYNTHETIC_KB = "synthetic_kb"
    USER_DATA = "user_data"


@dataclass
class Entity:
    """A knowledge entity to be archived in the brain."""
    content: str
    type: str
    source: DataSource
    source_id: Optional[str] = None
    source_url: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "content": self.content,
            "type": self.type,
            "source": self.source.value,
            "source_id": self.source_id,
            "source_url": self.source_url,
            "metadata": self.metadata or {}
        }


class Herodotus:
    """
    The Archivist - collects and synthesizes knowledge from all sources.
    
    Workflow:
    1. Poll data sources for new content
    2. Extract entities (insights, decisions, code, etc.)
    3. Generate embeddings for semantic search
    4. Archive to Neon database
    5. Hand off to Hammurabi for quality judgment
    """
    
    def __init__(self, db_url: Optional[str] = None):
        self.db_url = db_url or os.getenv("NEON_DATABASE_URL")
        self.processed_count = 0
        self.error_count = 0
        
    async def collect_telegram(self, session_path: str) -> List[Entity]:
        """
        Parse Telegram session logs and extract entities.
        
        Args:
            session_path: Path to JSONL session file
            
        Returns:
            List of extracted entities
        """
        entities = []
        
        try:
            with open(session_path, 'r') as f:
                for line in f:
                    msg = json.loads(line)
                    
                    # Extract user messages
                    if msg.get('type') == 'message':
                        message = msg.get('message', {})
                        role = message.get('role')
                        content = message.get('content', [])
                        
                        # Process text content
                        for block in content:
                            if isinstance(block, dict) and block.get('type') == 'text':
                                text = block.get('text', '')
                                
                                # Classify the entity type
                                entity_type = self._classify_content(text, role)
                                
                                if entity_type:
                                    entities.append(Entity(
                                        content=text,
                                        type=entity_type,
                                        source=DataSource.TELEGRAM,
                                        source_id=msg.get('id'),
                                        metadata={
                                            'role': role,
                                            'timestamp': msg.get('timestamp')
                                        }
                                    ))
        except Exception as e:
            self.error_count += 1
            print(f"Error processing Telegram session: {e}")
            
        return entities
    
    async def collect_github(self, repo: str) -> List[Entity]:
        """
        Collect GitHub activity (commits, issues, PRs) from a repository.
        
        Args:
            repo: Repository in format 'owner/repo'
            
        Returns:
            List of extracted entities
        """
        entities = []
        # TODO: Implement GitHub collection using gh CLI or API
        return entities
    
    async def collect_synthetic_kb(self, kb_path: str) -> List[Entity]:
        """
        Ingest synthetic knowledge base Q&A pairs.
        
        Args:
            kb_path: Path to synthetic KB directory
            
        Returns:
            List of extracted entities
        """
        entities = []
        # TODO: Implement synthetic KB collection
        return entities
    
    def _classify_content(self, text: str, role: str) -> Optional[str]:
        """
        Classify content into entity types.
        
        Types:
        - insight: Valuable observation or learning
        - decision: A choice or determination made
        - question: Query or request for information
        - answer: Response to a question
        - code: Code snippet or technical implementation
        - task: Action item or todo
        """
        text_lower = text.lower()
        
        # Skip very short content
        if len(text) < 50:
            return None
            
        # Basic classification rules (will be enhanced with LLM)
        if role == 'user':
            if '?' in text:
                return 'question'
            elif any(word in text_lower for word in ['todo', 'need to', 'should', 'must']):
                return 'task'
            elif any(word in text_lower for word in ['i think', 'i believe', 'realized', 'learned']):
                return 'insight'
            elif any(word in text_lower for word in ['decided', 'going to', 'will do', 'chose']):
                return 'decision'
        elif role == 'assistant':
            if '```' in text:
                return 'code'
            else:
                return 'answer'
                
        return None
    
    async def archive(self, entities: List[Entity]) -> int:
        """
        Archive entities to Mike's Brain (Neon database).
        
        Args:
            entities: List of entities to archive
            
        Returns:
            Number of successfully archived entities
        """
        archived = 0
        
        for entity in entities:
            try:
                # TODO: Generate embedding
                # embedding = await get_embedding(entity.content)
                
                # TODO: Insert into database
                # await self.db.insert_entity(entity, embedding)
                
                archived += 1
                self.processed_count += 1
            except Exception as e:
                self.error_count += 1
                print(f"Error archiving entity: {e}")
                
        return archived
    
    async def run(self):
        """Main worker loop."""
        print(f"🏛️  Herodotus awakens - The Archivist is ready")
        print(f"   Database: {self.db_url[:30]}..." if self.db_url else "   Database: Not configured")
        
        # TODO: Implement continuous collection loop
        # while True:
        #     await self.collect_all_sources()
        #     await asyncio.sleep(300)  # Every 5 minutes


if __name__ == "__main__":
    herodotus = Herodotus()
    asyncio.run(herodotus.run())
