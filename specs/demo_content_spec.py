"""
DEMO CONTENT SPEC - What Makes Demo Content "Knock Their Socks Off"
===================================================================
Pydantic models that ARE the spec AND the judge criteria.

"No simple ass HTML. Go hard."
— Mike, 2026-02-05
"""

from typing import Optional, List
from pydantic import BaseModel, Field, validator
from enum import Enum


class QualityTier(Enum):
    """Quality tiers for demo content."""
    AMATEUR = "amateur"      # 0.0 - 0.4: Reject immediately
    ACCEPTABLE = "acceptable" # 0.4 - 0.6: Needs work
    GOOD = "good"            # 0.6 - 0.8: Passable
    EXCELLENT = "excellent"  # 0.8 - 0.9: Ship it
    MINDBLOWING = "mindblowing"  # 0.9 - 1.0: This is what we want


# =============================================================================
# VIDEO/VISUAL CONTENT SPECS
# =============================================================================

class VisualQualitySpec(BaseModel):
    """Spec for visual/video content quality."""
    
    # Resolution & Technical
    resolution_adequate: bool = Field(
        description="1080p minimum, 4K preferred"
    )
    framerate_smooth: bool = Field(
        description="30fps minimum, no stuttering"
    )
    audio_clear: bool = Field(
        description="Voice clearly audible, no background noise"
    )
    
    # Composition
    framing_professional: float = Field(
        ge=0, le=1,
        description="Rule of thirds, subject properly framed"
    )
    lighting_quality: float = Field(
        ge=0, le=1,
        description="Well-lit, no harsh shadows on face"
    )
    background_clean: float = Field(
        ge=0, le=1,
        description="Professional backdrop, no clutter"
    )
    
    # Motion & Transitions
    transitions_smooth: float = Field(
        ge=0, le=1,
        description="No jarring cuts, appropriate transitions"
    )
    camera_stable: bool = Field(
        description="No shaky cam (unless intentional)"
    )
    
    # Branding
    consistent_branding: float = Field(
        ge=0, le=1,
        description="Logo, colors, fonts match brand guide"
    )
    
    @property
    def overall_visual_score(self) -> float:
        """Calculate overall visual quality score."""
        technical_score = (
            (1.0 if self.resolution_adequate else 0.3) +
            (1.0 if self.framerate_smooth else 0.3) +
            (1.0 if self.audio_clear else 0.0) +  # Audio is critical
            (1.0 if self.camera_stable else 0.5)
        ) / 4
        
        composition_score = (
            self.framing_professional +
            self.lighting_quality +
            self.background_clean +
            self.transitions_smooth +
            self.consistent_branding
        ) / 5
        
        # Technical is pass/fail, composition is weighted
        return 0.4 * technical_score + 0.6 * composition_score


class DemoSceneSpec(BaseModel):
    """Spec for a single demo scene."""
    
    scene_name: str = Field(min_length=1)
    duration_seconds: int = Field(ge=5, le=300)
    
    # Content Requirements
    has_clear_purpose: bool = Field(
        description="Scene has ONE clear thing to show"
    )
    shows_real_functionality: bool = Field(
        description="Not mockup, actual working system"
    )
    demonstrates_value: bool = Field(
        description="Viewer understands why this matters"
    )
    
    # Pacing
    pacing_score: float = Field(
        ge=0, le=1,
        description="Not too fast (confusing) or slow (boring)"
    )
    
    # Engagement
    visual_interest: float = Field(
        ge=0, le=1,
        description="Something interesting to look at"
    )
    wow_moment: bool = Field(
        default=False,
        description="Scene has a 'holy shit' moment"
    )
    
    @property
    def scene_quality(self) -> float:
        """Quality score for this scene."""
        must_haves = (
            self.has_clear_purpose and 
            self.shows_real_functionality and 
            self.demonstrates_value
        )
        if not must_haves:
            return 0.3  # Fails basic requirements
        
        score = 0.6  # Base for passing requirements
        score += 0.2 * self.pacing_score
        score += 0.1 * self.visual_interest
        score += 0.1 if self.wow_moment else 0
        
        return min(1.0, score)


# =============================================================================
# NARRATIVE/SCRIPT SPECS
# =============================================================================

class NarrativeSpec(BaseModel):
    """Spec for demo narration/script quality."""
    
    # Hook
    hook_in_first_30s: bool = Field(
        description="Grabs attention within 30 seconds"
    )
    problem_clearly_stated: bool = Field(
        description="Viewer understands the problem being solved"
    )
    
    # Clarity
    jargon_free: float = Field(
        ge=0, le=1,
        description="No unnecessary technical terms"
    )
    eleven_year_old_test: float = Field(
        ge=0, le=1,
        description="A smart 11-year-old could follow along"
    )
    
    # Story Arc
    has_beginning_middle_end: bool = Field(
        description="Clear narrative structure"
    )
    builds_to_climax: bool = Field(
        description="Escalates to impressive demo moment"
    )
    memorable_takeaway: bool = Field(
        description="Viewer remembers one key thing"
    )
    
    # Emotional
    creates_urgency: float = Field(
        ge=0, le=1,
        description="Viewer feels the problem needs solving NOW"
    )
    inspires_confidence: float = Field(
        ge=0, le=1,
        description="Viewer believes team can execute"
    )
    
    @property
    def narrative_score(self) -> float:
        """Overall narrative quality."""
        structure_score = (
            (1.0 if self.hook_in_first_30s else 0.0) +
            (1.0 if self.problem_clearly_stated else 0.0) +
            (1.0 if self.has_beginning_middle_end else 0.3) +
            (1.0 if self.builds_to_climax else 0.5) +
            (1.0 if self.memorable_takeaway else 0.3)
        ) / 5
        
        clarity_score = (self.jargon_free + self.eleven_year_old_test) / 2
        emotional_score = (self.creates_urgency + self.inspires_confidence) / 2
        
        return 0.4 * structure_score + 0.3 * clarity_score + 0.3 * emotional_score


# =============================================================================
# TECHNICAL DEMO SPECS
# =============================================================================

class TechnicalDemoSpec(BaseModel):
    """Spec for the technical demonstration portion."""
    
    # Authenticity
    real_hardware_shown: bool = Field(
        description="Actual PLC, not simulation only"
    )
    real_time_interaction: bool = Field(
        description="Changes happen live, not pre-recorded"
    )
    verifiable_by_audience: bool = Field(
        description="Audience can confirm it's real (phone viewer)"
    )
    
    # Reliability
    demo_tested_3x: bool = Field(
        description="Full demo run 3+ times successfully"
    )
    fallback_ready: bool = Field(
        description="Backup plan if live demo fails"
    )
    recovery_graceful: bool = Field(
        description="Can recover from minor hiccups smoothly"
    )
    
    # Impressiveness
    shows_something_hard: bool = Field(
        description="Demonstrates technically challenging feat"
    )
    differentiated_from_alternatives: bool = Field(
        description="Clearly better than existing solutions"
    )
    scalability_implied: bool = Field(
        description="Viewer can imagine this working at scale"
    )
    
    @property
    def technical_score(self) -> float:
        """Technical demo quality score."""
        authenticity = (
            self.real_hardware_shown +
            self.real_time_interaction +
            self.verifiable_by_audience
        ) / 3
        
        reliability = (
            self.demo_tested_3x +
            self.fallback_ready +
            self.recovery_graceful
        ) / 3
        
        impressiveness = (
            self.shows_something_hard +
            self.differentiated_from_alternatives +
            self.scalability_implied
        ) / 3
        
        return 0.3 * authenticity + 0.3 * reliability + 0.4 * impressiveness


# =============================================================================
# FULL DEMO SPEC (COMBINED)
# =============================================================================

class FullDemoSpec(BaseModel):
    """
    Complete spec for the YC demo.
    
    This is THE quality gate. If it doesn't pass this, it doesn't ship.
    """
    
    visual: VisualQualitySpec
    narrative: NarrativeSpec
    technical: TechnicalDemoSpec
    scenes: List[DemoSceneSpec]
    
    # Overall Requirements
    total_runtime_seconds: int = Field(
        ge=180, le=420,  # 3-7 minutes
        description="Sweet spot: 4-5 minutes"
    )
    
    # Must-haves
    shows_live_plc: bool = Field(description="Real PLC visible and working")
    audience_can_interact: bool = Field(description="Phone viewer works")
    has_call_to_action: bool = Field(description="Clear next step for viewer")
    
    @property
    def overall_score(self) -> float:
        """
        The final score. Must be >= 0.85 to ship.
        """
        # Individual scores
        visual_score = self.visual.overall_visual_score
        narrative_score = self.narrative.narrative_score
        technical_score = self.technical.technical_score
        
        # Average scene quality
        if self.scenes:
            scene_score = sum(s.scene_quality for s in self.scenes) / len(self.scenes)
        else:
            scene_score = 0.0
        
        # Must-haves are binary gates
        must_have_gate = (
            self.shows_live_plc and
            self.audience_can_interact and
            self.has_call_to_action
        )
        
        if not must_have_gate:
            return 0.4  # Fails fundamentals
        
        # Weighted combination
        weighted = (
            0.25 * visual_score +
            0.30 * narrative_score +  # Story matters most
            0.25 * technical_score +
            0.20 * scene_score
        )
        
        return weighted
    
    @property
    def quality_tier(self) -> QualityTier:
        """Get the quality tier."""
        score = self.overall_score
        if score >= 0.9:
            return QualityTier.MINDBLOWING
        elif score >= 0.8:
            return QualityTier.EXCELLENT
        elif score >= 0.6:
            return QualityTier.GOOD
        elif score >= 0.4:
            return QualityTier.ACCEPTABLE
        else:
            return QualityTier.AMATEUR
    
    @property
    def passes_quality_gate(self) -> bool:
        """Must score 0.85+ to ship."""
        return self.overall_score >= 0.85
    
    def get_improvement_suggestions(self) -> List[str]:
        """Get specific suggestions to improve the demo."""
        suggestions = []
        
        if self.visual.overall_visual_score < 0.8:
            if not self.visual.audio_clear:
                suggestions.append("CRITICAL: Fix audio quality - get better mic")
            if self.visual.lighting_quality < 0.7:
                suggestions.append("Improve lighting on presenter")
            if not self.visual.resolution_adequate:
                suggestions.append("Record in 1080p minimum")
        
        if self.narrative.narrative_score < 0.8:
            if not self.narrative.hook_in_first_30s:
                suggestions.append("CRITICAL: Add compelling hook in first 30 seconds")
            if self.narrative.eleven_year_old_test < 0.6:
                suggestions.append("Simplify language - too much jargon")
            if not self.narrative.memorable_takeaway:
                suggestions.append("Add a clear 'remember this one thing' moment")
        
        if self.technical.technical_score < 0.8:
            if not self.technical.demo_tested_3x:
                suggestions.append("CRITICAL: Test full demo 3+ times before recording")
            if not self.technical.fallback_ready:
                suggestions.append("Prepare fallback (pre-recorded segments)")
        
        # Scene-specific
        weak_scenes = [s for s in self.scenes if s.scene_quality < 0.7]
        if weak_scenes:
            for scene in weak_scenes:
                suggestions.append(f"Improve scene '{scene.scene_name}' - score {scene.scene_quality:.2f}")
        
        return suggestions


# =============================================================================
# JUDGE FUNCTION
# =============================================================================

def judge_demo(spec: FullDemoSpec) -> dict:
    """
    Judge a demo against the spec.
    
    Returns verdict with score, tier, and suggestions.
    """
    return {
        "passed": spec.passes_quality_gate,
        "score": spec.overall_score,
        "tier": spec.quality_tier.value,
        "visual_score": spec.visual.overall_visual_score,
        "narrative_score": spec.narrative.narrative_score,
        "technical_score": spec.technical.technical_score,
        "suggestions": spec.get_improvement_suggestions(),
        "verdict": (
            "🚀 SHIP IT!" if spec.passes_quality_gate 
            else f"❌ NOT READY - needs {0.85 - spec.overall_score:.0%} improvement"
        )
    }


if __name__ == "__main__":
    # Example: Create a demo spec and judge it
    from pprint import pprint
    
    # Create example specs
    visual = VisualQualitySpec(
        resolution_adequate=True,
        framerate_smooth=True,
        audio_clear=True,
        framing_professional=0.8,
        lighting_quality=0.7,
        background_clean=0.9,
        transitions_smooth=0.8,
        camera_stable=True,
        consistent_branding=0.9
    )
    
    narrative = NarrativeSpec(
        hook_in_first_30s=True,
        problem_clearly_stated=True,
        jargon_free=0.7,
        eleven_year_old_test=0.8,
        has_beginning_middle_end=True,
        builds_to_climax=True,
        memorable_takeaway=True,
        creates_urgency=0.8,
        inspires_confidence=0.9
    )
    
    technical = TechnicalDemoSpec(
        real_hardware_shown=True,
        real_time_interaction=True,
        verifiable_by_audience=True,
        demo_tested_3x=False,  # Not yet!
        fallback_ready=True,
        recovery_graceful=True,
        shows_something_hard=True,
        differentiated_from_alternatives=True,
        scalability_implied=True
    )
    
    scenes = [
        DemoSceneSpec(
            scene_name="hook",
            duration_seconds=30,
            has_clear_purpose=True,
            shows_real_functionality=True,
            demonstrates_value=True,
            pacing_score=0.9,
            visual_interest=0.8,
            wow_moment=True
        ),
        DemoSceneSpec(
            scene_name="phone_demo",
            duration_seconds=90,
            has_clear_purpose=True,
            shows_real_functionality=True,
            demonstrates_value=True,
            pacing_score=0.8,
            visual_interest=0.9,
            wow_moment=True
        )
    ]
    
    full_demo = FullDemoSpec(
        visual=visual,
        narrative=narrative,
        technical=technical,
        scenes=scenes,
        total_runtime_seconds=330,
        shows_live_plc=True,
        audience_can_interact=True,
        has_call_to_action=True
    )
    
    verdict = judge_demo(full_demo)
    pprint(verdict)
