"""
HAMMURABI - The Judge
Named after the Babylonian king who created one of the earliest written legal codes (c. 1792-1750 BC)

Role: Quality gates and judgment for all content entering or leaving Mike's Brain.
- Evaluates entity quality (0-10)
- Determines actionability
- Provides feedback for rejection
- Ensures no garbage in, no garbage out

"If anyone bring an accusation against a man, and the accused go to the river 
and leap into the river, if he sink in the river his accuser shall take 
possession of his house." - Code of Hammurabi (Trial by ordeal - we use LLMs instead)
"""

import os
from typing import Dict, Any, Tuple, Optional
from dataclasses import dataclass
from enum import Enum


class JudgmentType(Enum):
    QUALITY = "quality"      # Is this content high quality?
    NOVELTY = "novelty"      # Is this new information or ChatGPT regurgitation?
    ACTIONABLE = "actionable" # Should this trigger real-world action?
    CONSISTENCY = "consistency" # Does this match Mike's style/preferences?


@dataclass
class Verdict:
    """A judgment rendered by Hammurabi."""
    passed: bool
    score: float  # 0-10
    reasoning: str
    judgment_type: JudgmentType
    threshold: float
    suggestions: Optional[str] = None  # Improvement suggestions if failed


class Hammurabi:
    """
    The Judge - evaluates all content for quality and actionability.
    
    Judgment Process:
    1. Receive entity from Herodotus
    2. Apply relevant judgment types
    3. Score each dimension (0-10)
    4. Compare against thresholds
    5. Pass → Archive to brain
    6. Fail → Generate feedback → Return to source for improvement
    """
    
    # Default thresholds for each judgment type
    THRESHOLDS = {
        JudgmentType.QUALITY: 6.0,
        JudgmentType.NOVELTY: 5.0,
        JudgmentType.ACTIONABLE: 7.0,
        JudgmentType.CONSISTENCY: 5.0
    }
    
    def __init__(self, llm_model: str = "claude-sonnet-4-20250514"):
        self.llm_model = llm_model
        self.judgments_rendered = 0
        self.passed_count = 0
        self.failed_count = 0
        
    async def judge_quality(self, content: str, content_type: str) -> Verdict:
        """
        Evaluate content quality.
        
        Criteria:
        - Clarity: Is the content clear and understandable?
        - Completeness: Does it contain necessary context?
        - Accuracy: Is the information likely accurate?
        - Usefulness: Will this be useful in the future?
        """
        # TODO: Implement LLM-based quality judgment
        # For now, use heuristics
        
        score = 5.0
        reasoning = []
        
        # Length check
        if len(content) < 100:
            score -= 1.0
            reasoning.append("Content is very short")
        elif len(content) > 500:
            score += 0.5
            reasoning.append("Content has good depth")
            
        # Structure check
        if '\n' in content or '•' in content or '-' in content:
            score += 0.5
            reasoning.append("Content is well-structured")
            
        # Specificity check
        specific_indicators = ['specifically', 'exactly', 'for example', 'such as', 'because']
        if any(ind in content.lower() for ind in specific_indicators):
            score += 1.0
            reasoning.append("Content contains specific details")
            
        threshold = self.THRESHOLDS[JudgmentType.QUALITY]
        passed = score >= threshold
        
        self.judgments_rendered += 1
        if passed:
            self.passed_count += 1
        else:
            self.failed_count += 1
            
        return Verdict(
            passed=passed,
            score=min(10.0, max(0.0, score)),
            reasoning="; ".join(reasoning) if reasoning else "Standard evaluation",
            judgment_type=JudgmentType.QUALITY,
            threshold=threshold,
            suggestions="Add more specific details and context" if not passed else None
        )
    
    async def judge_novelty(self, content: str, existing_embeddings=None) -> Verdict:
        """
        Evaluate content novelty.
        
        Criteria:
        - Not duplicate of existing content
        - Not generic ChatGPT-style output
        - Contains unique insights or information
        """
        # TODO: Implement semantic similarity check against existing content
        # TODO: Implement "ChatGPT detector" for generic responses
        
        score = 7.0  # Default to novel until we have comparison data
        reasoning = "No existing content to compare against"
        threshold = self.THRESHOLDS[JudgmentType.NOVELTY]
        
        return Verdict(
            passed=score >= threshold,
            score=score,
            reasoning=reasoning,
            judgment_type=JudgmentType.NOVELTY,
            threshold=threshold
        )
    
    async def judge_actionable(self, content: str, content_type: str) -> Verdict:
        """
        Determine if content should trigger real-world action.
        
        Action types:
        - Send notification
        - Create task
        - Execute code
        - Send email
        - Update external system
        """
        score = 0.0
        reasoning = []
        
        # Check for action indicators
        action_words = ['urgent', 'asap', 'immediately', 'critical', 'important', 
                       'need to', 'must', 'should', 'deadline', 'by tomorrow']
        
        content_lower = content.lower()
        found_actions = [word for word in action_words if word in content_lower]
        
        if found_actions:
            score = 5.0 + len(found_actions)
            reasoning.append(f"Contains action indicators: {', '.join(found_actions)}")
        
        # Task type gets higher score
        if content_type == 'task':
            score += 2.0
            reasoning.append("Content is classified as task")
            
        # Decision type might need follow-up
        if content_type == 'decision':
            score += 1.0
            reasoning.append("Decision may require implementation")
            
        threshold = self.THRESHOLDS[JudgmentType.ACTIONABLE]
        
        return Verdict(
            passed=score >= threshold,
            score=min(10.0, score),
            reasoning="; ".join(reasoning) if reasoning else "No clear action required",
            judgment_type=JudgmentType.ACTIONABLE,
            threshold=threshold
        )
    
    async def full_judgment(self, content: str, content_type: str) -> Dict[str, Verdict]:
        """
        Render full judgment across all dimensions.
        
        Returns dict of JudgmentType -> Verdict
        """
        return {
            "quality": await self.judge_quality(content, content_type),
            "novelty": await self.judge_novelty(content),
            "actionable": await self.judge_actionable(content, content_type)
        }
    
    def get_stats(self) -> Dict[str, Any]:
        """Return judgment statistics."""
        return {
            "total_judgments": self.judgments_rendered,
            "passed": self.passed_count,
            "failed": self.failed_count,
            "pass_rate": self.passed_count / self.judgments_rendered if self.judgments_rendered > 0 else 0
        }


if __name__ == "__main__":
    import asyncio
    
    hammurabi = Hammurabi()
    
    # Test judgment
    test_content = """
    I've decided to use Neon database for Mike's Brain because it offers:
    - Serverless Postgres with scale-to-zero
    - Native pgvector support for embeddings
    - Branch capability for experimentation
    This will save costs and allow rapid iteration.
    """
    
    async def test():
        verdicts = await hammurabi.full_judgment(test_content, "decision")
        for name, verdict in verdicts.items():
            print(f"\n{name.upper()}: {'✅ PASSED' if verdict.passed else '❌ FAILED'}")
            print(f"  Score: {verdict.score}/10 (threshold: {verdict.threshold})")
            print(f"  Reasoning: {verdict.reasoning}")
            
    asyncio.run(test())
