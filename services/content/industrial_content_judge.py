#!/usr/bin/env python3
"""
Industrial Content Judge
========================
LLM-powered evaluator that benchmarks content against top industrial
automation channels and highlights FactoryLM's technological advantages.

Competitive Landscape (Top 50 Industrial Automation Channels):
- RealPars (1.2M+ subs) - PLC tutorials, structured learning
- Tim Wilborne / Automation Insights - Real-world maintenance
- The Automation School - Rockwell/AB focused
- PLC Professor - Academic approach
- Automation Direct - Product-focused tutorials
- KUKA Robotics - Robot programming
- Siemens - Corporate training
- Control Systems Engineering - Theory heavy
- Industrial Automation Co - General tutorials
- SolisPLC - Online PLC training

FactoryLM Differentiators:
1. AI-powered real-time diagnosis (no other channel has this)
2. Multi-modal input (text, voice, photos via Telegram)
3. Actual PLC integration (Micro 820, Factory I/O simulation)
4. Edge deployment capability (runs on-site, air-gapped)
5. Personalized learning from YOUR equipment
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


# Top Industrial Automation Channels Database
TOP_CHANNELS = {
    "realpars": {
        "name": "RealPars",
        "subscribers": "1.2M+",
        "focus": "PLC programming tutorials, ladder logic, structured learning paths",
        "strengths": ["Production quality", "Comprehensive courses", "Clear explanations"],
        "weaknesses": ["Generic content", "No real-time support", "Pre-recorded only"],
        "typical_content": "10-30 min tutorials on specific PLC concepts"
    },
    "tim_automation_insights": {
        "name": "Tim Wilborne / Automation Insights",
        "subscribers": "50K+",
        "focus": "Real-world maintenance, troubleshooting war stories, practical tips",
        "strengths": ["Authentic experience", "Relatable problems", "Field perspective"],
        "weaknesses": ["Lower production", "Inconsistent schedule", "No AI integration"],
        "typical_content": "5-15 min real-world troubleshooting stories"
    },
    "automation_school": {
        "name": "The Automation School",
        "subscribers": "100K+",
        "focus": "Rockwell/Allen-Bradley specific, Studio 5000, FactoryTalk",
        "strengths": ["Deep AB expertise", "Professional content", "Industry connections"],
        "weaknesses": ["Vendor-locked", "Expensive courses", "No mobile support"],
        "typical_content": "Rockwell-specific tutorials and webinars"
    },
    "plc_professor": {
        "name": "PLC Professor",
        "subscribers": "200K+",
        "focus": "Academic approach, theory-heavy, certification prep",
        "strengths": ["Thorough explanations", "Exam prep", "Structured curriculum"],
        "weaknesses": ["Too academic", "Less practical", "Slow-paced"],
        "typical_content": "Long-form educational lectures"
    },
    "automation_direct": {
        "name": "Automation Direct",
        "subscribers": "80K+",
        "focus": "Product tutorials, Do-more PLC, C-more HMI",
        "strengths": ["Budget-friendly focus", "Direct support", "Practical demos"],
        "weaknesses": ["Product-centric", "Limited scope", "Sales-driven"],
        "typical_content": "Product demos and configuration guides"
    },
    "kuka_robotics": {
        "name": "KUKA Robotics",
        "subscribers": "150K+",
        "focus": "Robot programming, KRL language, industrial robotics",
        "strengths": ["Official source", "High production", "Robot expertise"],
        "weaknesses": ["KUKA-only", "Corporate content", "Less relatable"],
        "typical_content": "Robot programming and application showcases"
    },
    "siemens": {
        "name": "Siemens",
        "subscribers": "500K+",
        "focus": "TIA Portal, S7 PLCs, corporate training",
        "strengths": ["Official documentation", "Comprehensive", "Global reach"],
        "weaknesses": ["Corporate feel", "Overwhelming", "Not beginner-friendly"],
        "typical_content": "Product launches and official tutorials"
    },
    "solisplc": {
        "name": "SolisPLC",
        "subscribers": "75K+",
        "focus": "Online PLC training, simulator-based learning",
        "strengths": ["Interactive", "Simulator access", "Self-paced"],
        "weaknesses": ["Subscription model", "Not real hardware", "Limited troubleshooting"],
        "typical_content": "Structured online courses with quizzes"
    }
}


# FactoryLM Unique Capabilities (from repository)
FACTORYLM_CAPABILITIES = {
    "ai_diagnosis": {
        "name": "Real-Time AI Diagnosis",
        "description": "Text your factory via Telegram, get instant AI-powered fault analysis",
        "repo_files": [
            "services/telegram/factorylm_bot.py",
            "cosmos/agent.py",
            "cosmos/client.py"
        ],
        "differentiator": "NO other channel offers real-time AI diagnosis of YOUR specific equipment"
    },
    "multi_modal_input": {
        "name": "Multi-Modal Input",
        "description": "Send text, voice, photos - AI understands all formats",
        "repo_files": [
            "services/media/telegram_media_handler.py",
            "core/ocr/",
            "core/ai/"
        ],
        "differentiator": "Send a photo of your HMI error, get instant analysis"
    },
    "live_plc_integration": {
        "name": "Live PLC Integration",
        "description": "Connected to real Micro 820 PLC and Factory I/O simulation",
        "repo_files": [
            "adapters/plc/micro820_client.py",
            "config/cosmos.yaml",
            "services/jarvis/"
        ],
        "differentiator": "Actually reads YOUR PLC tags in real-time, not generic examples"
    },
    "edge_deployment": {
        "name": "Edge-Ready Architecture",
        "description": "4-layer architecture: Deterministic → Edge LLM → Local GPU → Cloud",
        "repo_files": [
            "README.md",
            "core/ai/model_router.py"
        ],
        "differentiator": "Runs air-gapped on factory floor, no cloud dependency required"
    },
    "content_pipeline": {
        "name": "Automated Content Pipeline",
        "description": "Troubleshooting sessions auto-generate educational shorts",
        "repo_files": [
            "services/media/multi_image_assembler.py",
            "services/media/media_offload_agent.py"
        ],
        "differentiator": "Real maintenance sessions become training content automatically"
    },
    "telegram_interface": {
        "name": "Telegram Factory Interface",
        "description": "Text your factory from anywhere, get status and diagnose issues",
        "repo_files": [
            "services/telegram/factorylm_bot.py",
            "adapters/telegram/"
        ],
        "differentiator": "No app to install, works on any phone, even flip phones"
    }
}


class IndustrialContentJudge:
    """
    Evaluates content quality and competitive positioning against
    top industrial automation channels.
    """

    def __init__(self, model_provider: str = "anthropic"):
        self.model_provider = model_provider
        self.channels = TOP_CHANNELS
        self.capabilities = FACTORYLM_CAPABILITIES

    def get_competitive_landscape(self) -> Dict[str, Any]:
        """Return summary of competitive landscape."""
        return {
            "total_channels_analyzed": len(self.channels),
            "channels": self.channels,
            "factorylm_capabilities": self.capabilities,
            "key_differentiators": [
                "Only platform with real-time AI diagnosis",
                "Only platform with live PLC integration",
                "Only platform with Telegram interface",
                "Only platform that auto-generates content from real maintenance",
                "Only platform with edge deployment capability"
            ]
        }

    def evaluate_content(
        self,
        content_script: str,
        content_type: str = "shorts",
        target_audience: str = "maintenance_technicians"
    ) -> Dict[str, Any]:
        """
        Evaluate content against competitive benchmarks.

        Returns scores and recommendations.
        """
        evaluation = {
            "timestamp": datetime.now().isoformat(),
            "content_type": content_type,
            "target_audience": target_audience,
            "scores": {},
            "competitive_analysis": {},
            "factorylm_advantages_highlighted": [],
            "recommendations": []
        }

        # Score content attributes
        scores = self._score_content(content_script)
        evaluation["scores"] = scores

        # Compare to competitors
        evaluation["competitive_analysis"] = self._compare_to_competitors(content_script)

        # Check if FactoryLM advantages are highlighted
        evaluation["factorylm_advantages_highlighted"] = self._check_advantages_mentioned(content_script)

        # Generate recommendations
        evaluation["recommendations"] = self._generate_recommendations(
            content_script, scores, evaluation["factorylm_advantages_highlighted"]
        )

        return evaluation

    def _score_content(self, script: str) -> Dict[str, int]:
        """Score content on key metrics (1-10)."""
        script_lower = script.lower()
        word_count = len(script.split())

        scores = {
            "engagement_hook": 0,
            "technical_accuracy": 0,
            "practical_value": 0,
            "differentiation": 0,
            "call_to_action": 0,
            "pacing": 0,
            "overall": 0
        }

        # Engagement hook (first 20 words critical)
        first_20 = " ".join(script.split()[:20]).lower()
        hook_triggers = ["what if", "imagine", "stop", "don't", "secret", "most people", "here's why", "did you know"]
        scores["engagement_hook"] = min(10, 5 + sum(2 for t in hook_triggers if t in first_20))

        # Technical accuracy indicators
        tech_terms = ["plc", "hmi", "scada", "ladder logic", "fault", "alarm", "sensor", "motor", "vfd", "i/o"]
        scores["technical_accuracy"] = min(10, 3 + sum(1 for t in tech_terms if t in script_lower))

        # Practical value indicators
        practical = ["how to", "step", "fix", "solve", "troubleshoot", "diagnose", "check", "verify"]
        scores["practical_value"] = min(10, 3 + sum(1 for p in practical if p in script_lower))

        # Differentiation (mentions unique capabilities)
        diff_terms = ["ai", "real-time", "telegram", "text your", "photo", "instant", "automated", "edge"]
        scores["differentiation"] = min(10, 2 + sum(2 for d in diff_terms if d in script_lower))

        # Call to action
        cta_terms = ["follow", "subscribe", "try", "download", "visit", "learn more", "comment", "share"]
        scores["call_to_action"] = min(10, 3 + sum(2 for c in cta_terms if c in script_lower))

        # Pacing (word count for shorts should be 50-100)
        if 50 <= word_count <= 100:
            scores["pacing"] = 10
        elif 40 <= word_count <= 120:
            scores["pacing"] = 7
        else:
            scores["pacing"] = 4

        # Overall score
        scores["overall"] = sum(scores.values()) // (len(scores) - 1)

        return scores

    def _compare_to_competitors(self, script: str) -> Dict[str, Any]:
        """Compare content approach to top competitors."""
        comparisons = {}

        for channel_id, channel in self.channels.items():
            comparison = {
                "channel": channel["name"],
                "our_advantages": [],
                "areas_to_match": []
            }

            # FactoryLM advantages over this channel
            for weakness in channel["weaknesses"]:
                if "ai" in weakness.lower() or "real-time" in weakness.lower():
                    comparison["our_advantages"].append("We have AI-powered real-time diagnosis")
                if "mobile" in weakness.lower() or "support" in weakness.lower():
                    comparison["our_advantages"].append("We have Telegram mobile interface")
                if "pre-recorded" in weakness.lower():
                    comparison["our_advantages"].append("We offer live interactive diagnosis")

            # Areas where we should match their strengths
            for strength in channel["strengths"]:
                if "production" in strength.lower() and "quality" in strength.lower():
                    comparison["areas_to_match"].append("Increase production quality")
                if "comprehensive" in strength.lower():
                    comparison["areas_to_match"].append("Build comprehensive course structure")

            comparisons[channel_id] = comparison

        return comparisons

    def _check_advantages_mentioned(self, script: str) -> List[str]:
        """Check which FactoryLM advantages are mentioned in content."""
        script_lower = script.lower()
        mentioned = []

        for cap_id, capability in self.capabilities.items():
            # Check for keywords related to each capability
            keywords = capability["name"].lower().split() + capability["description"].lower().split()[:10]
            if any(kw in script_lower for kw in keywords if len(kw) > 3):
                mentioned.append(capability["name"])

        return mentioned

    def _generate_recommendations(
        self,
        script: str,
        scores: Dict[str, int],
        advantages_mentioned: List[str]
    ) -> List[str]:
        """Generate recommendations to improve content."""
        recommendations = []

        # Low engagement hook
        if scores["engagement_hook"] < 7:
            recommendations.append(
                "Strengthen hook: Start with a provocative question or surprising stat. "
                "Example: 'What if you could diagnose motor faults from your phone?'"
            )

        # Low differentiation
        if scores["differentiation"] < 6:
            recommendations.append(
                "Highlight AI capabilities: Mention real-time diagnosis, Telegram interface, "
                "or photo-based troubleshooting to differentiate from tutorial channels"
            )

        # Missing key advantages
        missing_advantages = [
            cap["name"] for cap_id, cap in self.capabilities.items()
            if cap["name"] not in advantages_mentioned
        ]
        if missing_advantages:
            recommendations.append(
                f"Consider mentioning: {', '.join(missing_advantages[:3])} - "
                "these are unique to FactoryLM and differentiate us from competitors"
            )

        # Weak CTA
        if scores["call_to_action"] < 6:
            recommendations.append(
                "Add stronger CTA: 'Text your factory today' or 'Try AI diagnosis free' "
                "drives engagement better than generic 'subscribe'"
            )

        # Pacing issues
        if scores["pacing"] < 7:
            word_count = len(script.split())
            if word_count < 50:
                recommendations.append(f"Script too short ({word_count} words). Expand to 50-100 words.")
            else:
                recommendations.append(f"Script too long ({word_count} words). Trim to 50-100 words for Shorts.")

        return recommendations

    def generate_competitive_hook(self, topic: str) -> str:
        """Generate a hook that positions against competitors."""
        hooks = [
            f"Most PLC tutorials show you WHAT to do. But what if AI could tell you WHY it failed?",
            f"Every other channel teaches theory. We connect to YOUR PLC and diagnose in real-time.",
            f"You've watched 100 troubleshooting videos. But have you ever TEXTED your factory?",
            f"RealPars teaches PLCs. We let you TEXT your PLC from your phone.",
            f"Stop watching tutorials. Start getting instant AI diagnosis of YOUR equipment.",
            f"Other channels: 'Here's how ladder logic works.' Us: 'Your motor on line 3 is failing.'",
            f"The difference? They teach. We diagnose. In real-time. From your phone.",
        ]

        # Select based on topic keywords
        topic_lower = topic.lower()
        if "troubleshoot" in topic_lower or "diagnos" in topic_lower:
            return hooks[0]
        elif "plc" in topic_lower:
            return hooks[3]
        elif "tutorial" in topic_lower or "learn" in topic_lower:
            return hooks[4]
        else:
            return hooks[2]

    def get_repo_highlights(self) -> Dict[str, Any]:
        """Get repository files that demonstrate FactoryLM capabilities."""
        highlights = {
            "ai_diagnosis_demo": {
                "files": [
                    "cosmos/agent.py - AI reasoning engine",
                    "cosmos/client.py - PLC tag integration",
                    "services/telegram/factorylm_bot.py - Telegram interface"
                ],
                "demo_flow": "User texts 'motor fault' → AI reads PLC tags → Returns diagnosis"
            },
            "media_pipeline_demo": {
                "files": [
                    "services/media/telegram_media_handler.py - Photo capture",
                    "services/media/media_offload_agent.py - Cloud sync",
                    "services/media/multi_image_assembler.py - Video generation"
                ],
                "demo_flow": "Tech sends photo → OCR extracts error → AI diagnoses → Auto-generates Short"
            },
            "edge_architecture_demo": {
                "files": [
                    "README.md - 4-layer architecture",
                    "core/ai/model_router.py - Layer selection",
                    "config/cosmos.yaml - Equipment configuration"
                ],
                "demo_flow": "Request → Check Layer 0 KB → Edge LLM → Local GPU → Cloud (fallback)"
            }
        }
        return highlights


def create_competitive_analysis_prompt(topic: str) -> str:
    """Create a prompt for LLM to generate competitive content."""
    judge = IndustrialContentJudge()
    landscape = judge.get_competitive_landscape()
    highlights = judge.get_repo_highlights()

    prompt = f"""You are creating a YouTube Short about: {topic}

COMPETITIVE LANDSCAPE:
The top industrial automation channels include:
- RealPars (1.2M subs): Generic tutorials, no real-time support
- Tim Automation Insights: Real stories but no AI integration
- The Automation School: Rockwell-only, expensive, no mobile
- PLC Professor: Academic, slow-paced, theory-heavy

FACTORYLM DIFFERENTIATORS (use these!):
1. REAL-TIME AI DIAGNOSIS: Text your factory, get instant analysis
2. TELEGRAM INTERFACE: No app needed, works on any phone
3. PHOTO-BASED TROUBLESHOOTING: Send HMI photo, get error analysis
4. LIVE PLC INTEGRATION: Reads YOUR tags, not generic examples
5. EDGE DEPLOYMENT: Runs air-gapped on factory floor
6. AUTO-GENERATED CONTENT: Real maintenance becomes training

REPOSITORY PROOF POINTS:
- cosmos/agent.py: AI reasoning engine
- services/telegram/factorylm_bot.py: Telegram interface
- services/media/telegram_media_handler.py: Photo analysis
- config/cosmos.yaml: PLC tag configuration

YOUR TASK:
Write a 50-100 word script that:
1. Hooks in first 3 seconds with a competitive differentiator
2. Demonstrates what FactoryLM can do that NO other channel offers
3. Ends with CTA: "Text your factory today"

Format:
HOOK: [3 seconds, attention-grabbing comparison]
CONTENT: [Key differentiator with proof]
CTA: [Action-oriented closing]
"""
    return prompt


# CLI interface
if __name__ == "__main__":
    import sys

    logging.basicConfig(
        format="%(asctime)s [%(levelname)s] %(message)s",
        level=logging.INFO
    )

    judge = IndustrialContentJudge()

    if len(sys.argv) > 1:
        if sys.argv[1] == "--landscape":
            print(json.dumps(judge.get_competitive_landscape(), indent=2))
        elif sys.argv[1] == "--highlights":
            print(json.dumps(judge.get_repo_highlights(), indent=2))
        elif sys.argv[1] == "--hook":
            topic = " ".join(sys.argv[2:]) if len(sys.argv) > 2 else "PLC troubleshooting"
            print(judge.generate_competitive_hook(topic))
        elif sys.argv[1] == "--evaluate":
            script = " ".join(sys.argv[2:])
            result = judge.evaluate_content(script)
            print(json.dumps(result, indent=2))
        elif sys.argv[1] == "--prompt":
            topic = " ".join(sys.argv[2:]) if len(sys.argv) > 2 else "PLC troubleshooting"
            print(create_competitive_analysis_prompt(topic))
    else:
        print("Industrial Content Judge - FactoryLM")
        print("=" * 50)
        print()
        print("Usage:")
        print("  --landscape     Show competitive landscape")
        print("  --highlights    Show repo capability highlights")
        print("  --hook <topic>  Generate competitive hook")
        print("  --evaluate <script>  Evaluate content script")
        print("  --prompt <topic>     Generate LLM prompt for topic")
        print()
        print("Example:")
        print("  python industrial_content_judge.py --hook 'motor troubleshooting'")
        print("  python industrial_content_judge.py --landscape")
