"""
📝 ARTICLE PUBLISHER WORKER
============================
Generates scientific articles and publishable content from:
- GitHub Scrubber output
- Whitepapers and PRDs
- Technical documentation
- Code patterns and inventions

Output formats:
- Academic papers (LaTeX/Markdown)
- Blog posts
- LinkedIn articles
- Patent application drafts
- Technical briefs
"""

import os
import sys
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
import logging
import requests

sys.path.insert(0, '/opt/master_of_puppets')
from celery_app import app
from workers.base_worker import BaseAgent

logger = logging.getLogger(__name__)

# Paths
KNOWLEDGE_BASE = Path('/root/jarvis-workspace/knowledge-base')
CONTENT_QUEUE = KNOWLEDGE_BASE / 'content-queue.jsonl'
ARTICLES_DIR = Path('/root/jarvis-workspace/articles')
DRAFTS_DIR = ARTICLES_DIR / 'drafts'
PUBLISHED_DIR = ARTICLES_DIR / 'published'

# Ensure directories exist
for d in [ARTICLES_DIR, DRAFTS_DIR, PUBLISHED_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# LLM Configuration
GROQ_API_KEY = os.getenv('GROQ_API_KEY', '')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '')

# Article templates
ARTICLE_TYPES = {
    'academic': {
        'sections': ['Abstract', 'Introduction', 'Background', 'Methodology', 
                    'Implementation', 'Results', 'Discussion', 'Conclusion', 'References'],
        'format': 'markdown',
        'min_words': 2000,
    },
    'blog': {
        'sections': ['Hook', 'Problem', 'Solution', 'How It Works', 
                    'Results', 'Call to Action'],
        'format': 'markdown',
        'min_words': 800,
    },
    'linkedin': {
        'sections': ['Hook', 'Story', 'Insight', 'Call to Action'],
        'format': 'text',
        'min_words': 200,
        'max_words': 700,
    },
    'technical_brief': {
        'sections': ['Overview', 'Technical Details', 'Architecture', 
                    'Implementation Notes', 'Future Work'],
        'format': 'markdown',
        'min_words': 500,
    },
    'patent_draft': {
        'sections': ['Title', 'Field of Invention', 'Background', 
                    'Summary', 'Detailed Description', 'Claims'],
        'format': 'markdown',
        'min_words': 1500,
    },
}


class ArticlePublisher(BaseAgent):
    """Generates articles from technical content."""
    
    def __init__(self):
        super().__init__("ArticlePublisher")
        self.published_count = 0
    
    def _call_llm(self, prompt: str, max_tokens: int = 2000) -> str:
        """Call LLM for content generation."""
        # Try Groq first (fast)
        if GROQ_API_KEY:
            try:
                resp = requests.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
                    json={
                        "model": "llama-3.1-70b-versatile",
                        "messages": [{"role": "user", "content": prompt}],
                        "max_tokens": max_tokens,
                        "temperature": 0.7,
                    },
                    timeout=60
                )
                if resp.status_code == 200:
                    return resp.json()['choices'][0]['message']['content']
            except Exception as e:
                logger.error(f"Groq error: {e}")
        
        # Fallback to Gemini
        if GEMINI_API_KEY:
            try:
                resp = requests.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}",
                    json={
                        "contents": [{"parts": [{"text": prompt}]}],
                        "generationConfig": {"maxOutputTokens": max_tokens}
                    },
                    timeout=60
                )
                if resp.status_code == 200:
                    return resp.json()['candidates'][0]['content']['parts'][0]['text']
            except Exception as e:
                logger.error(f"Gemini error: {e}")
        
        return "Error: No LLM available"
    
    def generate_article(
        self, 
        source_content: str,
        source_info: Dict,
        article_type: str = 'technical_brief'
    ) -> Dict:
        """Generate an article from source content."""
        
        if article_type not in ARTICLE_TYPES:
            article_type = 'technical_brief'
        
        template = ARTICLE_TYPES[article_type]
        
        # Build prompt
        prompt = f"""You are a technical writer creating a {article_type} article.

SOURCE CONTENT:
Title: {source_info.get('title', 'Technical Documentation')}
Type: {source_info.get('type', 'documentation')}
Path: {source_info.get('path', 'unknown')}

CONTENT:
{source_content[:8000]}

INSTRUCTIONS:
1. Create a {article_type} article based on this technical content
2. Use these sections: {', '.join(template['sections'])}
3. Target length: {template.get('min_words', 500)} words minimum
4. Be specific and technical - this is for a technical audience
5. Highlight innovations, novel approaches, and unique solutions
6. Format as {template['format']}

Write the complete article now:"""

        # Generate article
        article_content = self._call_llm(prompt, max_tokens=3000)
        
        # Create article record
        article = {
            'id': f"article_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{self.published_count}",
            'type': article_type,
            'title': source_info.get('title', 'Technical Article'),
            'source_path': source_info.get('path', ''),
            'source_type': source_info.get('type', ''),
            'generated_at': datetime.utcnow().isoformat(),
            'content': article_content,
            'word_count': len(article_content.split()),
            'status': 'draft',
        }
        
        # Save draft
        draft_file = DRAFTS_DIR / f"{article['id']}.md"
        with open(draft_file, 'w') as f:
            f.write(f"# {article['title']}\n\n")
            f.write(f"*Generated: {article['generated_at']}*\n")
            f.write(f"*Source: {article['source_path']}*\n")
            f.write(f"*Type: {article_type}*\n\n")
            f.write("---\n\n")
            f.write(article_content)
        
        article['draft_path'] = str(draft_file)
        self.published_count += 1
        
        logger.info(f"📝 Generated {article_type}: {article['title']} ({article['word_count']} words)")
        
        return article
    
    def process_queue(self, max_items: int = 5) -> List[Dict]:
        """Process pending items from content queue."""
        if not CONTENT_QUEUE.exists():
            return []
        
        processed = []
        remaining = []
        
        with open(CONTENT_QUEUE, 'r') as f:
            items = [json.loads(line) for line in f if line.strip()]
        
        for i, item in enumerate(items):
            if item.get('status') == 'pending' and len(processed) < max_items:
                # Generate article
                article = self.generate_article(
                    source_content=item.get('content', ''),
                    source_info=item.get('file_info', {}),
                    article_type='technical_brief'
                )
                
                item['status'] = 'processed'
                item['article_id'] = article['id']
                processed.append(article)
            
            remaining.append(item)
        
        # Update queue
        with open(CONTENT_QUEUE, 'w') as f:
            for item in remaining:
                f.write(json.dumps(item) + '\n')
        
        return processed
    
    def get_drafts(self) -> List[Dict]:
        """Get list of draft articles."""
        drafts = []
        for draft_file in DRAFTS_DIR.glob('*.md'):
            drafts.append({
                'filename': draft_file.name,
                'path': str(draft_file),
                'size': draft_file.stat().st_size,
                'modified': datetime.fromtimestamp(
                    draft_file.stat().st_mtime
                ).isoformat(),
            })
        return sorted(drafts, key=lambda x: x['modified'], reverse=True)
    
    def generate_from_whitepaper(self, whitepaper_path: str) -> Dict:
        """Generate multiple article types from a whitepaper."""
        if not Path(whitepaper_path).exists():
            return {'error': f'File not found: {whitepaper_path}'}
        
        content = Path(whitepaper_path).read_text()
        file_info = {
            'path': whitepaper_path,
            'type': 'whitepaper',
            'title': self._extract_title(content),
        }
        
        articles = []
        for article_type in ['academic', 'blog', 'linkedin', 'technical_brief']:
            article = self.generate_article(content, file_info, article_type)
            articles.append(article)
        
        return {
            'source': whitepaper_path,
            'articles_generated': len(articles),
            'articles': articles,
        }
    
    def _extract_title(self, content: str) -> str:
        """Extract title from content."""
        lines = content.split('\n')
        for line in lines[:10]:
            if line.startswith('# '):
                return line[2:].strip()
        return "Technical Document"


# Initialize publisher
publisher = ArticlePublisher()


@app.task(name='articles.generate')
def generate_article(source_content: str, source_info: Dict, article_type: str = 'technical_brief'):
    """Celery task: Generate a single article."""
    logger.info(f"📝 Generating {article_type} article...")
    return publisher.generate_article(source_content, source_info, article_type)


@app.task(name='articles.process_queue')
def process_queue(max_items: int = 5):
    """Celery task: Process pending content queue."""
    logger.info(f"📝 Processing content queue (max {max_items})...")
    return publisher.process_queue(max_items)


@app.task(name='articles.from_whitepaper')
def generate_from_whitepaper(whitepaper_path: str):
    """Celery task: Generate all article types from whitepaper."""
    logger.info(f"📝 Generating articles from: {whitepaper_path}")
    return publisher.generate_from_whitepaper(whitepaper_path)


@app.task(name='articles.list_drafts')
def list_drafts():
    """Celery task: List all draft articles."""
    return publisher.get_drafts()


@app.task(name='articles.publish_cycle')
def publish_cycle():
    """Celery task: Full publish cycle - scrub then generate."""
    from workers.github_scrubber_tasks import scrub_all_repos
    
    # First scrub
    scrub_results = scrub_all_repos()
    
    # Then process queue
    articles = process_queue(max_items=3)
    
    return {
        'scrub_results': scrub_results,
        'articles_generated': len(articles),
        'articles': articles,
    }
