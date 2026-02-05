"""
Content Capture Agent - YouTube Automation Pipeline
====================================================
Watches everything and logs for automatic content generation:
1. Milestones from git commits, Trello, Telegram
2. Screen recordings / screenshots
3. Auto-generates video ideas and scripts
4. Creates Shorts from high-value events
"""

import os
import sys
import json
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from pathlib import Path
import logging
import requests

sys.path.insert(0, '/opt/master_of_puppets')
from celery_app import app
from workers.base_worker import BaseAgent, with_token_tracking

logger = logging.getLogger(__name__)

# Content workspace
CONTENT_DIR = "/root/jarvis-workspace/content"
EVENTS_LOG = f"{CONTENT_DIR}/events.jsonl"
IDEAS_LOG = f"{CONTENT_DIR}/video_ideas.jsonl"
SCRIPTS_DIR = f"{CONTENT_DIR}/scripts"
SHORTS_DIR = f"{CONTENT_DIR}/shorts"

# Ensure directories exist
for d in [CONTENT_DIR, SCRIPTS_DIR, SHORTS_DIR]:
    os.makedirs(d, exist_ok=True)

# Content value scores
CONTENT_SCORES = {
    "first_successful_deployment": 10,
    "bug_fixed_by_ai": 9,
    "plc_first_inference": 9,
    "new_agent_deployed": 8,
    "grafana_dashboard_created": 7,
    "customer_feedback": 8,
    "milestone_reached": 8,
    "trello_sprint_complete": 7,
    "interesting_error_fixed": 6,
    "routine_code_commit": 3,
    "config_change": 2,
}

# Groq for fast content generation
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")


class ContentCaptureAgent(BaseAgent):
    """Captures milestones and generates content ideas."""
    
    def __init__(self):
        super().__init__("ContentCapture")
        self.day_count = self._get_day_count()
    
    def _get_day_count(self) -> int:
        """Get the day count since project start."""
        start_date = datetime(2026, 1, 29)  # Project start
        return (datetime.utcnow() - start_date).days + 1
    
    def _call_groq(self, prompt: str, max_tokens: int = 500) -> str:
        """Call Groq for fast content generation."""
        if not GROQ_API_KEY:
            return "Error: No Groq API key"
        
        try:
            resp = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
                json={
                    "model": "llama-3.1-8b-instant",
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": max_tokens,
                    "temperature": 0.7
                },
                timeout=30
            )
            if resp.ok:
                return resp.json()["choices"][0]["message"]["content"]
            return f"Error: {resp.status_code}"
        except Exception as e:
            return f"Error: {e}"
    
    def score_content_value(self, event_type: str) -> int:
        """Rate 1-10 how interesting this is for video."""
        return CONTENT_SCORES.get(event_type, 5)
    
    def log_milestone(self, event_type: str, data: Dict) -> Dict:
        """Log a milestone event for potential content."""
        event = {
            "timestamp": datetime.utcnow().isoformat(),
            "day": self.day_count,
            "type": event_type,
            "data": data,
            "content_score": self.score_content_value(event_type)
        }
        
        # Save to events log
        with open(EVENTS_LOG, "a") as f:
            f.write(json.dumps(event) + "\n")
        
        # Auto-generate video idea if high value
        if event["content_score"] >= 7:
            idea = self.generate_video_idea(event)
            event["video_idea"] = idea
            
            with open(IDEAS_LOG, "a") as f:
                f.write(json.dumps({"event": event, "idea": idea}) + "\n")
        
        return event
    
    def generate_video_idea(self, event: Dict) -> Dict:
        """Generate a video concept from a milestone."""
        prompt = f"""Generate a YouTube video idea for an industrial AI startup channel called "Master of Puppets".

Milestone: Day {event['day']} - {event['type']}
Details: {json.dumps(event['data'], indent=2)}

Output as JSON:
{{
  "title": "Catchy, SEO-friendly title (include Day X)",
  "hook": "First 10 seconds to grab viewer attention",
  "format": "short" or "standard" or "deep_dive",
  "length_seconds": 60 for short, 300-600 for standard,
  "key_points": ["point 1", "point 2", "point 3"],
  "thumbnail_concept": "Visual description for thumbnail",
  "hashtags": ["#tag1", "#tag2"]
}}

Be specific to industrial AI, PLCs, maintenance, automation."""

        response = self._call_groq(prompt, max_tokens=400)
        
        try:
            # Extract JSON from response
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                return json.loads(json_match.group())
        except:
            pass
        
        return {"raw_response": response}
    
    def generate_short_script(self, event: Dict) -> str:
        """Generate a 60-second Short script."""
        prompt = f"""Write a 60-second YouTube Short script for "Master of Puppets" channel.

Topic: Day {event['day']} - {event['type']}
Details: {json.dumps(event['data'], indent=2)}

Format:
[HOOK - 3 seconds]
(Attention-grabbing opening)

[PROBLEM - 10 seconds]
(What issue this solves)

[SOLUTION - 30 seconds]
(What we built/did)

[RESULT - 12 seconds]
(What happened, show the win)

[CTA - 5 seconds]
(Follow for more industrial AI content)

Make it punchy, visual, and exciting. Industrial AI is the future!"""

        return self._call_groq(prompt, max_tokens=400)
    
    def generate_weekly_summary(self) -> Dict:
        """Generate a weekly build log summary."""
        # Read recent events
        events = []
        if os.path.exists(EVENTS_LOG):
            with open(EVENTS_LOG) as f:
                for line in f:
                    try:
                        e = json.loads(line)
                        event_time = datetime.fromisoformat(e["timestamp"])
                        if event_time > datetime.utcnow() - timedelta(days=7):
                            events.append(e)
                    except:
                        pass
        
        # Get high-value events
        high_value = [e for e in events if e.get("content_score", 0) >= 6]
        
        prompt = f"""Generate a weekly YouTube video script for "Master of Puppets" channel.

Week {self.day_count // 7 + 1} Summary:
- Total events: {len(events)}
- High-value milestones: {len(high_value)}

Key milestones:
{json.dumps(high_value[:5], indent=2)}

Write a 5-7 minute video script with:
1. Intro (30s) - Hook + week overview
2. Top 3 achievements (2 min each) - Show what was built
3. Metrics/Dashboard review (1 min) - Grafana screenshots
4. Next week preview (30s)
5. CTA (15s)

Make it engaging, show real progress, be authentic."""

        script = self._call_groq(prompt, max_tokens=1000)
        
        # Save script
        script_file = f"{SCRIPTS_DIR}/week_{self.day_count // 7 + 1}.md"
        with open(script_file, "w") as f:
            f.write(f"# Week {self.day_count // 7 + 1} Build Log\n\n")
            f.write(f"Generated: {datetime.utcnow().isoformat()}\n\n")
            f.write(script)
        
        return {
            "week": self.day_count // 7 + 1,
            "events_count": len(events),
            "high_value_count": len(high_value),
            "script_file": script_file,
            "script_preview": script[:500] + "..."
        }
    
    def get_recent_events(self, days: int = 7, min_score: int = 0) -> List[Dict]:
        """Get recent events above minimum score."""
        events = []
        if os.path.exists(EVENTS_LOG):
            cutoff = datetime.utcnow() - timedelta(days=days)
            with open(EVENTS_LOG) as f:
                for line in f:
                    try:
                        e = json.loads(line)
                        event_time = datetime.fromisoformat(e["timestamp"])
                        if event_time > cutoff and e.get("content_score", 0) >= min_score:
                            events.append(e)
                    except:
                        pass
        return events
    
    def get_stats(self) -> Dict:
        """Get content capture stats."""
        events = self.get_recent_events(days=30)
        ideas_count = 0
        if os.path.exists(IDEAS_LOG):
            with open(IDEAS_LOG) as f:
                ideas_count = sum(1 for _ in f)
        
        return {
            "day_count": self.day_count,
            "events_30d": len(events),
            "high_value_events": len([e for e in events if e.get("content_score", 0) >= 7]),
            "video_ideas": ideas_count,
            "scripts_generated": len(list(Path(SCRIPTS_DIR).glob("*.md")))
        }


capture = ContentCaptureAgent()


@app.task(bind=True, name='content.log_milestone')
@with_token_tracking('content')
def log_milestone(self, event_type: str, data: Dict) -> Dict:
    """Log a milestone for content generation."""
    capture.log_start('log_milestone', event_type=event_type)
    result = capture.log_milestone(event_type, data)
    capture.log_complete('log_milestone', result)
    return result


@app.task(bind=True, name='content.generate_short')
@with_token_tracking('content')
def generate_short(self, event_type: str, data: Dict) -> Dict:
    """Generate a Short script for an event."""
    event = {"type": event_type, "data": data, "day": capture.day_count}
    script = capture.generate_short_script(event)
    
    # Save script
    script_file = f"{SHORTS_DIR}/day{capture.day_count}_{event_type}.md"
    with open(script_file, "w") as f:
        f.write(f"# Day {capture.day_count}: {event_type}\n\n")
        f.write(script)
    
    return {
        "script_file": script_file,
        "script": script
    }


@app.task(bind=True, name='content.weekly_summary')
@with_token_tracking('content')
def weekly_summary(self) -> Dict:
    """Generate weekly build log."""
    return capture.generate_weekly_summary()


@app.task(bind=True, name='content.stats')
def stats(self) -> Dict:
    """Get content stats."""
    return capture.get_stats()


@app.task(bind=True, name='content.health')
def health(self) -> Dict:
    """Health check."""
    s = capture.get_stats()
    return {
        "status": "ok",
        "agent": "ContentCapture",
        "day": s["day_count"],
        "events_30d": s["events_30d"]
    }
