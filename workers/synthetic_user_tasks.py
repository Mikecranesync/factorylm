"""
Synthetic User Tasks - 24/7 KB Builder
=======================================
Runs synthetic users against FactoryLM services continuously to:
1. Build knowledge base from Q&A interactions
2. Generate training data for fine-tuning
3. Find edge cases and bugs
4. Stress test the system
"""

import os
import sys
import json
import random
import time
from datetime import datetime
from typing import Dict, List, Optional
import logging
import requests

sys.path.insert(0, '/opt/master_of_puppets')
from celery_app import app
from workers.base_worker import BaseAgent, with_token_tracking
from observability.metrics import write_metric

logger = logging.getLogger(__name__)

# FactoryLM Service Endpoints
SERVICES = {
    "manual_hunter": {
        "url": "http://localhost:8090/ask",
        "method": "POST",
        "description": "Industrial manual Q&A"
    },
    "rivet_kb": {
        "url": "http://localhost:8082/api/v1/kb/query",
        "method": "POST", 
        "description": "Rivet knowledge base"
    },
    "alarm_triage": {
        "url": "http://localhost:8091/analyze",
        "method": "POST",
        "description": "Alarm analysis"
    },
    "maintenance_llm": {
        "url": "http://100.72.2.99:11434/api/generate",
        "method": "POST",
        "description": "PLC laptop LLM (reserved for real-time)"
    },
    "groq": {
        "url": "https://api.groq.com/openai/v1/chat/completions",
        "method": "POST",
        "description": "Groq cloud LLM (fast, free tier)"
    }
}

# Groq API key
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

# Synthetic Personas with different expertise levels
PERSONAS = [
    {
        "id": "tech_01",
        "name": "Marcus Chen",
        "role": "Maintenance Technician",
        "experience": 5,
        "style": "direct",
        "topics": ["fault codes", "troubleshooting", "repair procedures"]
    },
    {
        "id": "eng_01",
        "name": "Sarah Rodriguez",
        "role": "Reliability Engineer",
        "experience": 12,
        "style": "technical",
        "topics": ["root cause analysis", "predictive maintenance", "MTBF"]
    },
    {
        "id": "ops_01",
        "name": "James Wilson",
        "role": "Plant Operator",
        "experience": 3,
        "style": "simple",
        "topics": ["alarms", "startup", "safety"]
    },
    {
        "id": "mgr_01",
        "name": "Patricia Kim",
        "role": "Maintenance Manager",
        "experience": 15,
        "style": "business",
        "topics": ["scheduling", "costs", "KPIs", "compliance"]
    },
    {
        "id": "plc_01",
        "name": "David Thompson",
        "role": "PLC Programmer",
        "experience": 8,
        "style": "code",
        "topics": ["ladder logic", "HMI", "communication", "programming"]
    },
    {
        "id": "newbie_01",
        "name": "Alex Martinez",
        "role": "Apprentice",
        "experience": 0,
        "style": "confused",
        "topics": ["basics", "safety", "what does this mean"]
    }
]

# Question templates by topic
QUESTION_TEMPLATES = {
    "fault codes": [
        "What does fault code {fault} mean on a {vendor} {device}?",
        "How do I clear fault {fault} on {vendor} drive?",
        "{vendor} {device} showing {fault}, what's wrong?",
        "Error {fault} keeps coming back on {device}, help"
    ],
    "troubleshooting": [
        "Motor {symptom}, what should I check first?",
        "{device} {symptom}, where do I start?",
        "How do I diagnose {symptom} on {vendor} equipment?",
        "Intermittent {symptom} on {device}, hard to catch"
    ],
    "repair procedures": [
        "How do I replace {component} on {vendor} {device}?",
        "What's the procedure for {action} on {device}?",
        "Need step-by-step to {action} {component}",
        "Tools needed for {component} replacement?"
    ],
    "alarms": [
        "Alarm {alarm} on {device}, urgent?",
        "Getting repeated {alarm} alarms, why?",
        "How do I acknowledge {alarm}?",
        "Priority of {alarm} alarm?"
    ],
    "predictive maintenance": [
        "What are early warning signs for {failure}?",
        "How often should I inspect {component}?",
        "Vibration trending up on {device}, concern?",
        "Predictive indicators for {component} failure?"
    ],
    "basics": [
        "What is a {concept}?",
        "Why do we need {concept}?",
        "How does {concept} work?",
        "Can you explain {concept} simply?"
    ]
}

# Fill-in values
VENDORS = ["Siemens", "Allen-Bradley", "ABB", "Danfoss", "Yaskawa", "Mitsubishi", "Rockwell", "Schneider"]
DEVICES = ["VFD", "drive", "PLC", "servo", "motor", "pump", "conveyor", "robot"]
FAULTS = ["F0001", "F0003", "F0021", "F0051", "OC1", "OV1", "UV1", "OH1", "EF", "GF", "SC"]
SYMPTOMS = ["overheating", "vibrating", "making noise", "tripping", "not starting", "running slow", "erratic speed"]
COMPONENTS = ["bearing", "fan", "capacitor", "contactor", "encoder", "motor", "coupling", "belt"]
ACTIONS = ["calibrate", "replace", "adjust", "clean", "lubricate", "align"]
ALARMS = ["high temp", "low pressure", "overcurrent", "ground fault", "communication loss", "emergency stop"]
CONCEPTS = ["VFD", "PID loop", "ladder logic", "MTBF", "MTTR", "OEE", "5S", "lockout tagout"]
FAILURES = ["bearing failure", "winding insulation breakdown", "seal leak", "coupling misalignment"]


class SyntheticUserRunner(BaseAgent):
    """Runs synthetic users against FactoryLM services."""
    
    def __init__(self):
        super().__init__("SyntheticUser")
        self.session = requests.Session()
        self.kb_path = "/root/jarvis-workspace/brain/synthetic-kb"
        os.makedirs(self.kb_path, exist_ok=True)
        
    def _generate_question(self, persona: Dict) -> Dict:
        """Generate a question based on persona."""
        topic = random.choice(persona["topics"])
        templates = QUESTION_TEMPLATES.get(topic, QUESTION_TEMPLATES["basics"])
        template = random.choice(templates)
        
        # Fill in template
        question = template.format(
            fault=random.choice(FAULTS),
            vendor=random.choice(VENDORS),
            device=random.choice(DEVICES),
            symptom=random.choice(SYMPTOMS),
            component=random.choice(COMPONENTS),
            action=random.choice(ACTIONS),
            alarm=random.choice(ALARMS),
            concept=random.choice(CONCEPTS),
            failure=random.choice(FAILURES)
        )
        
        # Adjust style based on persona
        if persona["style"] == "confused":
            question = question.lower() + "?"
        elif persona["style"] == "direct":
            question = question.rstrip("?") + " - need answer fast"
        elif persona["style"] == "technical":
            question = f"Technical question: {question}"
        
        return {
            "question": question,
            "topic": topic,
            "persona_id": persona["id"],
            "persona_name": persona["name"],
            "persona_role": persona["role"]
        }
    
    def _call_service(self, service_name: str, question: str) -> Dict:
        """Call a FactoryLM service."""
        service = SERVICES.get(service_name)
        if not service:
            return {"error": f"Unknown service: {service_name}"}
        
        start_time = time.time()
        
        try:
            if service_name == "manual_hunter":
                payload = {"question": question}
                headers = {}
            elif service_name == "maintenance_llm":
                payload = {
                    "model": "llama3:8b",
                    "prompt": question,
                    "stream": False
                }
                headers = {}
            elif service_name == "groq":
                # Groq API - fast and free!
                payload = {
                    "model": "llama-3.1-8b-instant",
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are an expert industrial maintenance technician with deep knowledge of PLCs, VFDs, motors, and industrial automation. Give practical, actionable advice."
                        },
                        {
                            "role": "user",
                            "content": question
                        }
                    ],
                    "max_tokens": 500,
                    "temperature": 0.3
                }
                headers = {
                    "Authorization": f"Bearer {GROQ_API_KEY}",
                    "Content-Type": "application/json"
                }
            else:
                payload = {"query": question}
                headers = {}
            
            response = self.session.post(
                service["url"],
                json=payload,
                headers=headers,
                timeout=30  # Groq is fast, 30s is plenty
            )
            
            latency_ms = (time.time() - start_time) * 1000
            
            if response.ok:
                data = response.json()
                
                # Extract response based on service
                if service_name == "groq":
                    resp_text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                else:
                    resp_text = data.get("response") or data.get("answer") or str(data)[:500]
                
                return {
                    "success": True,
                    "service": service_name,
                    "response": resp_text,
                    "latency_ms": latency_ms,
                    "status_code": response.status_code
                }
            else:
                return {
                    "success": False,
                    "service": service_name,
                    "error": f"HTTP {response.status_code}",
                    "latency_ms": latency_ms
                }
                
        except requests.exceptions.Timeout:
            return {"success": False, "service": service_name, "error": "timeout"}
        except requests.exceptions.ConnectionError:
            return {"success": False, "service": service_name, "error": "connection_failed"}
        except Exception as e:
            return {"success": False, "service": service_name, "error": str(e)}
    
    def _save_interaction(self, interaction: Dict):
        """Save interaction to KB for training."""
        date_str = datetime.utcnow().strftime("%Y-%m-%d")
        kb_file = f"{self.kb_path}/{date_str}.jsonl"
        
        with open(kb_file, "a") as f:
            f.write(json.dumps(interaction) + "\n")
    
    def run_session(self, num_questions: int = 5) -> Dict:
        """Run a synthetic user session."""
        persona = random.choice(PERSONAS)
        self.logger.info(f"Starting session as {persona['name']} ({persona['role']})")
        
        results = []
        successful = 0
        total_latency = 0
        
        for i in range(num_questions):
            # Generate question
            q_data = self._generate_question(persona)
            question = q_data["question"]
            
            # Pick a service - Groq is primary (fast + free), others for variety
            if GROQ_API_KEY:
                service = "groq"  # Fast cloud LLM
            else:
                # Fallback to local if no Groq key
                service = "maintenance_llm"
            
            # Call service
            response = self._call_service(service, question)
            
            # Build interaction record
            interaction = {
                "timestamp": datetime.utcnow().isoformat(),
                "persona": persona,
                "question": question,
                "topic": q_data["topic"],
                "service": service,
                "response": response.get("response", ""),
                "success": response.get("success", False),
                "latency_ms": response.get("latency_ms", 0),
                "error": response.get("error")
            }
            
            # Save to KB
            self._save_interaction(interaction)
            
            results.append(interaction)
            
            if response.get("success"):
                successful += 1
                total_latency += response.get("latency_ms", 0)
            
            # Small delay between questions
            time.sleep(random.uniform(0.5, 2.0))
        
        # Write metrics
        try:
            write_metric(
                measurement="synthetic_user_session",
                tags={
                    "persona_id": persona["id"],
                    "persona_role": persona["role"]
                },
                fields={
                    "questions": num_questions,
                    "successful": successful,
                    "failed": num_questions - successful,
                    "avg_latency_ms": total_latency / max(successful, 1)
                }
            )
        except Exception as e:
            self.logger.warning(f"Metrics write failed: {e}")
        
        return {
            "persona": persona["name"],
            "role": persona["role"],
            "questions_asked": num_questions,
            "successful_responses": successful,
            "avg_latency_ms": round(total_latency / max(successful, 1), 2),
            "kb_file": f"{self.kb_path}/{datetime.utcnow().strftime('%Y-%m-%d')}.jsonl"
        }
    
    def get_kb_stats(self) -> Dict:
        """Get KB statistics."""
        import glob
        
        kb_files = glob.glob(f"{self.kb_path}/*.jsonl")
        total_interactions = 0
        
        for f in kb_files:
            with open(f) as file:
                total_interactions += sum(1 for _ in file)
        
        return {
            "kb_path": self.kb_path,
            "files": len(kb_files),
            "total_interactions": total_interactions
        }


runner = SyntheticUserRunner()


@app.task(bind=True, name='synth.run_session')
@with_token_tracking('synth')
def run_session(self, num_questions: int = 5) -> Dict:
    """Run a synthetic user session."""
    runner.log_start('run_session', questions=num_questions)
    result = runner.run_session(num_questions)
    runner.log_complete('run_session', result)
    return result


@app.task(bind=True, name='synth.continuous')
@with_token_tracking('synth')
def continuous_run(self, sessions: int = 10, questions_per: int = 5) -> Dict:
    """Run multiple synthetic sessions continuously."""
    runner.log_start('continuous', sessions=sessions)
    
    all_results = []
    for i in range(sessions):
        result = runner.run_session(questions_per)
        all_results.append(result)
        
        # Brief pause between sessions
        time.sleep(random.uniform(5, 15))
    
    total_questions = sum(r["questions_asked"] for r in all_results)
    total_successful = sum(r["successful_responses"] for r in all_results)
    
    summary = {
        "sessions": sessions,
        "total_questions": total_questions,
        "total_successful": total_successful,
        "success_rate": f"{(total_successful/total_questions)*100:.1f}%",
        "results": all_results
    }
    
    runner.log_complete('continuous', summary)
    return summary


@app.task(bind=True, name='synth.kb_stats')
def kb_stats(self) -> Dict:
    """Get KB statistics."""
    return runner.get_kb_stats()


@app.task(bind=True, name='synth.health')
def health(self) -> Dict:
    """Health check."""
    stats = runner.get_kb_stats()
    return {
        "status": "ok",
        "agent": "SyntheticUser",
        "kb_interactions": stats.get("total_interactions", 0),
        "kb_files": stats.get("files", 0)
    }
