"""
🔍 GITHUB SCRUBBER WORKER
=========================
Continuously scans all GitHub repos for:
- Technical content (whitepapers, PRDs, architecture docs)
- Code patterns and innovations
- README/documentation updates
- Inventions and novel implementations

Feeds the Article Publisher worker with indexed content.
"""

import os
import sys
import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
import logging
import hashlib

sys.path.insert(0, '/opt/master_of_puppets')
from celery_app import app
from workers.base_worker import BaseAgent

logger = logging.getLogger(__name__)

# Paths
KNOWLEDGE_BASE = Path('/root/jarvis-workspace/knowledge-base')
SCRUB_INDEX = KNOWLEDGE_BASE / 'github-index.json'
CONTENT_QUEUE = KNOWLEDGE_BASE / 'content-queue.jsonl'

# Ensure directories exist
KNOWLEDGE_BASE.mkdir(parents=True, exist_ok=True)

# Content patterns to extract
CONTENT_PATTERNS = {
    'whitepaper': ['**/WHITEPAPER*.md', '**/whitepaper*.md', '**/docs/*whitepaper*.md'],
    'prd': ['**/PRD*.md', '**/prd*.md'],
    'architecture': ['**/ARCHITECTURE*.md', '**/architecture*.md', '**/docs/ARCHITECTURE*.md'],
    'readme': ['**/README.md'],
    'claude_instructions': ['**/CLAUDE.md', '**/.claude/**/*.md'],
    'technical_docs': ['**/docs/*.md', '**/documentation/*.md'],
    'inventions': ['**/patents/*.md', '**/inventions/*.md', '**/innovations/*.md'],
}

# Repos to scan
WORKSPACE_REPOS = [
    '/root/jarvis-workspace',
    '/root/jarvis-workspace/projects/Rivet-PRO',
    '/root/jarvis-workspace/factorylm-dev',
    '/root/jarvis-workspace/landing-page',
]


class GitHubScrubber(BaseAgent):
    """Scrubs GitHub repos for technical content."""
    
    def __init__(self):
        super().__init__("GitHubScrubber")
        self.index = self._load_index()
    
    def _load_index(self) -> Dict:
        """Load existing index."""
        if SCRUB_INDEX.exists():
            try:
                with open(SCRUB_INDEX) as f:
                    return json.load(f)
            except:
                pass
        return {'files': {}, 'last_scan': None, 'stats': {}}
    
    def _save_index(self):
        """Save index to disk."""
        with open(SCRUB_INDEX, 'w') as f:
            json.dump(self.index, f, indent=2, default=str)
    
    def _hash_content(self, content: str) -> str:
        """Generate content hash for change detection."""
        return hashlib.md5(content.encode()).hexdigest()
    
    def _find_files(self, repo_path: str, patterns: List[str]) -> List[Path]:
        """Find files matching patterns in repo."""
        found = []
        repo = Path(repo_path)
        if not repo.exists():
            return found
        
        for pattern in patterns:
            found.extend(repo.glob(pattern))
        return found
    
    def scrub_repo(self, repo_path: str) -> Dict:
        """Scrub a single repo for content."""
        results = {
            'repo': repo_path,
            'timestamp': datetime.utcnow().isoformat(),
            'files_found': 0,
            'files_changed': 0,
            'content': []
        }
        
        for content_type, patterns in CONTENT_PATTERNS.items():
            files = self._find_files(repo_path, patterns)
            
            for filepath in files:
                try:
                    content = filepath.read_text()
                    content_hash = self._hash_content(content)
                    file_key = str(filepath)
                    
                    results['files_found'] += 1
                    
                    # Check if changed since last scan
                    if file_key in self.index['files']:
                        if self.index['files'][file_key]['hash'] == content_hash:
                            continue  # No change
                    
                    results['files_changed'] += 1
                    
                    # Extract metadata
                    file_info = {
                        'path': file_key,
                        'type': content_type,
                        'hash': content_hash,
                        'size': len(content),
                        'lines': content.count('\n'),
                        'title': self._extract_title(content),
                        'summary': content[:500],
                        'last_modified': datetime.fromtimestamp(
                            filepath.stat().st_mtime
                        ).isoformat(),
                    }
                    
                    # Update index
                    self.index['files'][file_key] = file_info
                    results['content'].append(file_info)
                    
                    # Queue for article publisher
                    self._queue_for_publishing(file_info, content)
                    
                except Exception as e:
                    logger.error(f"Error processing {filepath}: {e}")
        
        return results
    
    def _extract_title(self, content: str) -> str:
        """Extract title from markdown content."""
        lines = content.split('\n')
        for line in lines[:10]:
            if line.startswith('# '):
                return line[2:].strip()
        return "Untitled"
    
    def _queue_for_publishing(self, file_info: Dict, content: str):
        """Add content to publishing queue."""
        queue_entry = {
            'timestamp': datetime.utcnow().isoformat(),
            'file_info': file_info,
            'content': content,
            'status': 'pending'
        }
        
        with open(CONTENT_QUEUE, 'a') as f:
            f.write(json.dumps(queue_entry) + '\n')
    
    def scrub_all_repos(self) -> Dict:
        """Scrub all configured repos."""
        results = {
            'timestamp': datetime.utcnow().isoformat(),
            'repos_scanned': 0,
            'total_files': 0,
            'total_changed': 0,
            'repos': []
        }
        
        for repo_path in WORKSPACE_REPOS:
            if Path(repo_path).exists():
                repo_results = self.scrub_repo(repo_path)
                results['repos'].append(repo_results)
                results['repos_scanned'] += 1
                results['total_files'] += repo_results['files_found']
                results['total_changed'] += repo_results['files_changed']
        
        # Also scan GitHub repos via gh CLI
        try:
            gh_repos = subprocess.run(
                ['gh', 'repo', 'list', 'mikecranesync', '--limit', '50', '--json', 'name,url'],
                capture_output=True, text=True, timeout=30
            )
            if gh_repos.returncode == 0:
                repos = json.loads(gh_repos.stdout)
                results['github_repos_available'] = len(repos)
        except Exception as e:
            logger.error(f"Error listing GitHub repos: {e}")
        
        # Update index
        self.index['last_scan'] = results['timestamp']
        self.index['stats'] = {
            'total_files': len(self.index['files']),
            'repos_scanned': results['repos_scanned'],
        }
        self._save_index()
        
        return results
    
    def get_publishable_content(self, content_type: Optional[str] = None) -> List[Dict]:
        """Get content ready for article publishing."""
        publishable = []
        
        for file_key, file_info in self.index['files'].items():
            if content_type and file_info['type'] != content_type:
                continue
            
            # Prioritize high-value content
            if file_info['type'] in ['whitepaper', 'prd', 'architecture', 'inventions']:
                publishable.append(file_info)
        
        return sorted(publishable, key=lambda x: x.get('size', 0), reverse=True)


# Initialize scrubber
scrubber = GitHubScrubber()


@app.task(name='github.scrub_all')
def scrub_all_repos():
    """Celery task: Scrub all repos for content."""
    logger.info("🔍 Starting GitHub scrub cycle...")
    results = scrubber.scrub_all_repos()
    logger.info(f"✅ Scrub complete: {results['total_files']} files, {results['total_changed']} changed")
    return results


@app.task(name='github.scrub_repo')
def scrub_single_repo(repo_path: str):
    """Celery task: Scrub a single repo."""
    logger.info(f"🔍 Scrubbing repo: {repo_path}")
    return scrubber.scrub_repo(repo_path)


@app.task(name='github.get_publishable')
def get_publishable_content(content_type: Optional[str] = None):
    """Celery task: Get content ready for publishing."""
    return scrubber.get_publishable_content(content_type)


@app.task(name='github.get_index')
def get_index():
    """Celery task: Get current index status."""
    return scrubber.index
