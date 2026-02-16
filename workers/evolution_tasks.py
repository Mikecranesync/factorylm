"""
🧬 EVOLUTION AGENT
==================
Self-improving loop that:
1. Analyzes completed work
2. Identifies gaps and improvements
3. Creates new tasks in Trello
4. Triggers the Monkey to execute

This is the meta-learning layer that makes the swarm smarter over time.
"""

import os
import sys
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
import logging

sys.path.insert(0, '/opt/master_of_puppets')
from celery_app import app
from workers.base_worker import BaseAgent, with_celery_tracing
from observability import traced

logger = logging.getLogger(__name__)

# Paths
EVOLUTION_LOG = Path('/root/jarvis-workspace/brain/automaton/evolution-log.md')
LEARNINGS_FILE = Path('/opt/master_of_puppets/state/learnings.json')
VISION_FILE = Path('/opt/master_of_puppets/state/current_vision.json')

# Gemini for analysis
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"


class EvolutionAgent(BaseAgent):
    """
    The Evolution Agent - Meta-learning layer.
    Analyzes, plans, and spawns new work.
    """
    
    def __init__(self):
        super().__init__("EvolutionAgent")
        self._init_state()
    
    def _init_state(self):
        """Initialize state files."""
        EVOLUTION_LOG.parent.mkdir(parents=True, exist_ok=True)
        
        if not LEARNINGS_FILE.exists():
            self._save_learnings({'learnings': [], 'patterns': {}})
        
        if not VISION_FILE.exists():
            self._save_vision({
                'goal': 'Build autonomous industrial AI swarm',
                'current_phase': 1,
                'priorities': ['reliability', 'observability', 'automation']
            })
    
    def _load_learnings(self) -> Dict:
        try:
            with open(LEARNINGS_FILE) as f:
                return json.load(f)
        except:
            return {'learnings': [], 'patterns': {}}
    
    def _save_learnings(self, data: Dict):
        with open(LEARNINGS_FILE, 'w') as f:
            json.dump(data, f, indent=2, default=str)
    
    def _load_vision(self) -> Dict:
        try:
            with open(VISION_FILE) as f:
                return json.load(f)
        except:
            return {}
    
    def _save_vision(self, data: Dict):
        with open(VISION_FILE, 'w') as f:
            json.dump(data, f, indent=2, default=str)
    
    def call_gemini(self, prompt: str) -> str:
        """Call Gemini API for analysis."""
        import requests
        
        if not GEMINI_API_KEY:
            return "Error: GEMINI_API_KEY not set"
        
        try:
            response = requests.post(
                f"{GEMINI_URL}?key={GEMINI_API_KEY}",
                json={
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {
                        "temperature": 0.7,
                        "maxOutputTokens": 2000,
                    }
                },
                timeout=30
            )
            
            if response.ok:
                data = response.json()
                return data['candidates'][0]['content']['parts'][0]['text']
            else:
                return f"API error: {response.text}"
        except Exception as e:
            return f"Error: {str(e)}"
    
    def analyze_completed_work(self) -> Dict:
        """
        Analyze what was completed and extract learnings.
        """
        from integrations.trello import get_cards_in_list, LISTS
        
        # Get completed tasks
        done_cards = get_cards_in_list(LISTS['done'])
        blocked_cards = get_cards_in_list(LISTS['blocked'])
        
        # Build analysis prompt
        done_names = [c['name'] for c in done_cards[:20]]
        blocked_names = [c['name'] for c in blocked_cards[:10]]
        
        # Load current state
        from pathlib import Path
        state_file = Path('/opt/master_of_puppets/state/monkey_state.json')
        monkey_state = {}
        if state_file.exists():
            with open(state_file) as f:
                monkey_state = json.load(f)
        
        prompt = f"""Analyze this autonomous AI swarm's work and identify improvements.

COMPLETED TASKS ({len(done_cards)}):
{chr(10).join(f'- {n}' for n in done_names)}

BLOCKED TASKS ({len(blocked_cards)}):
{chr(10).join(f'- {n}' for n in blocked_names)}

MONKEY STATE:
- Tasks dispatched: {monkey_state.get('tasks_dispatched', 0)}
- Tasks completed: {monkey_state.get('tasks_completed', 0)}
- Tokens used: {monkey_state.get('tokens_used_today', 0)}

Provide analysis in this JSON format:
{{
  "summary": "Brief summary of what was accomplished",
  "patterns_noticed": ["pattern1", "pattern2"],
  "gaps_identified": ["gap1", "gap2"],
  "improvement_ideas": ["idea1", "idea2"],
  "next_priorities": ["priority1", "priority2"],
  "suggested_tasks": [
    {{"name": "🟢 Task Name", "description": "What to do", "automaton": "which_agent"}}
  ]
}}

Focus on:
1. What's working well
2. What's blocked or failing
3. What's missing
4. Next logical steps
"""
        
        analysis_text = self.call_gemini(prompt)
        
        # Try to parse JSON from response
        try:
            # Find JSON in response
            json_match = re.search(r'\{[\s\S]*\}', analysis_text)
            if json_match:
                analysis = json.loads(json_match.group())
            else:
                analysis = {"raw_response": analysis_text}
        except:
            analysis = {"raw_response": analysis_text}
        
        # Save learnings
        learnings = self._load_learnings()
        learnings['learnings'].append({
            'timestamp': datetime.now().isoformat(),
            'analysis': analysis
        })
        # Keep only last 50 learnings
        learnings['learnings'] = learnings['learnings'][-50:]
        self._save_learnings(learnings)
        
        return analysis
    
    def create_tasks_from_analysis(self, analysis: Dict) -> List[Dict]:
        """
        Create new Trello tasks based on analysis.
        """
        from integrations.trello import create_card
        
        created = []
        suggested = analysis.get('suggested_tasks', [])
        
        for task in suggested[:5]:  # Max 5 tasks per cycle
            name = task.get('name', '')
            desc = task.get('description', '')
            
            # Ensure task has autonomous marker
            if not any(marker in name for marker in ['🟢', '🤖']):
                name = f"🟢 {name}"
            
            # Create in backlog
            card = create_card('backlog', name, desc)
            if card:
                created.append({
                    'name': name,
                    'id': card.get('id'),
                    'url': card.get('url')
                })
                self.logger.info(f"Created task: {name}")
        
        return created
    
    def update_vision(self, analysis: Dict):
        """
        Update the current vision based on learnings.
        """
        vision = self._load_vision()
        
        # Update priorities based on analysis
        if 'next_priorities' in analysis:
            vision['priorities'] = analysis['next_priorities'][:5]
        
        # Track patterns
        if 'patterns_noticed' in analysis:
            vision['recent_patterns'] = analysis['patterns_noticed']
        
        # Update timestamp
        vision['last_evolution'] = datetime.now().isoformat()
        
        self._save_vision(vision)
        
        return vision
    
    def log_evolution(self, analysis: Dict, created_tasks: List[Dict]):
        """
        Log evolution cycle to markdown.
        """
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')
        
        with open(EVOLUTION_LOG, 'a') as f:
            f.write(f"\n## Evolution Cycle - {timestamp}\n\n")
            
            if 'summary' in analysis:
                f.write(f"**Summary:** {analysis['summary']}\n\n")
            
            if 'patterns_noticed' in analysis:
                f.write("**Patterns:**\n")
                for p in analysis['patterns_noticed']:
                    f.write(f"- {p}\n")
                f.write("\n")
            
            if 'gaps_identified' in analysis:
                f.write("**Gaps:**\n")
                for g in analysis['gaps_identified']:
                    f.write(f"- {g}\n")
                f.write("\n")
            
            if created_tasks:
                f.write("**New Tasks Created:**\n")
                for t in created_tasks:
                    f.write(f"- {t['name']}\n")
                f.write("\n")
            
            f.write("---\n")
    
    def run_evolution_cycle(self, auto_dispatch: bool = True) -> Dict:
        """
        Full evolution cycle:
        1. Analyze completed work
        2. Update vision
        3. Create new tasks
        4. Optionally trigger Monkey
        """
        self.log_start("evolution_cycle")
        
        # Step 1: Analyze
        self.logger.info("Step 1: Analyzing completed work...")
        analysis = self.analyze_completed_work()
        
        # Step 2: Update vision
        self.logger.info("Step 2: Updating vision...")
        vision = self.update_vision(analysis)
        
        # Step 3: Create tasks
        self.logger.info("Step 3: Creating new tasks...")
        created_tasks = self.create_tasks_from_analysis(analysis)
        
        # Step 4: Log evolution
        self.log_evolution(analysis, created_tasks)
        
        # Step 5: Trigger Monkey (optional)
        monkey_result = None
        if auto_dispatch and created_tasks:
            self.logger.info("Step 5: Triggering Monkey dispatch...")
            # Fire and forget - don't wait
            app.send_task('monkey.run_cycle', args=['trello'])
            monkey_result = "dispatched"
        
        result = {
            'status': 'completed',
            'analysis': analysis,
            'vision': vision,
            'tasks_created': len(created_tasks),
            'created_tasks': created_tasks,
            'monkey_triggered': monkey_result is not None,
        }
        
        self.log_complete("evolution_cycle", result)
        return result


evolution_agent = EvolutionAgent()


# ============== CELERY TASKS ==============

@app.task(bind=True, name='evolution.run_cycle')
@with_celery_tracing("evolution_cycle")
@traced(name="evolution_cycle", layer="meta")
def run_evolution_cycle(self, auto_dispatch: bool = True) -> Dict:
    """
    Run full evolution cycle.
    Called by Beat scheduler or manually.
    """
    return evolution_agent.run_evolution_cycle(auto_dispatch)


@app.task(bind=True, name='evolution.analyze')
@with_celery_tracing("analyze")
@traced(name="analyze", layer="meta")
def analyze_work(self) -> Dict:
    """Analyze completed work without creating tasks."""
    return evolution_agent.analyze_completed_work()


@app.task(bind=True, name='evolution.get_vision')
@with_celery_tracing("get_vision")
def get_vision(self) -> Dict:
    """Get current vision state."""
    return evolution_agent._load_vision()


@app.task(bind=True, name='evolution.health')
@with_celery_tracing("health")
def health(self) -> Dict:
    """Health check."""
    return {'status': 'ok', 'agent': 'EvolutionAgent'}
