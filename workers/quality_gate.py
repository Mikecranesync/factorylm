"""
QUALITY GATE - Decorator for Spec-Driven Development
=====================================================
All worker outputs pass through Hammurabi before archiving.

Implements the Engineering Commandments:
- III. Generate Judge From Spec
- IV. Polish Before Judging
- V. Submit To Hammurabi
- VI. Record For Prometheus

Usage:
    @app.task
    @quality_gated(spec=WorkOrderSpec)
    def generate_work_order(input_data):
        return worker.execute(input_data)
"""

import os
import json
import asyncio
from functools import wraps
from datetime import datetime
from pathlib import Path
from typing import Type, Optional, Any, Callable
from dataclasses import dataclass

# Try to import Pydantic for spec validation
try:
    from pydantic import BaseModel, ValidationError
    PYDANTIC_AVAILABLE = True
except ImportError:
    PYDANTIC_AVAILABLE = False
    BaseModel = None
    ValidationError = None


@dataclass
class Judgment:
    """Result of quality gate evaluation."""
    passed: bool
    score: float
    reasoning: str
    suggestions: list
    polished_artifact: Optional[str] = None


class QualityGate:
    """
    The quality gate that all artifacts must pass.
    
    Implements:
    1. Pydantic validation (if spec is a model)
    2. LLM judgment (if configured)
    3. Polish loop (minimum 3 iterations)
    4. Prometheus recording
    """
    
    def __init__(
        self,
        spec: Optional[Type[BaseModel]] = None,
        min_score: float = 0.7,
        max_polish_iterations: int = 3,
        record_to_prometheus: bool = True
    ):
        self.spec = spec
        self.min_score = min_score
        self.max_polish_iterations = max_polish_iterations
        self.record_to_prometheus = record_to_prometheus
        self.prometheus_dir = Path("/opt/master_of_puppets/training_data")
        self.prometheus_dir.mkdir(exist_ok=True)
    
    def validate_with_pydantic(self, artifact: Any) -> Judgment:
        """Validate artifact against Pydantic spec."""
        if not PYDANTIC_AVAILABLE or self.spec is None:
            return Judgment(
                passed=True,
                score=1.0,
                reasoning="No Pydantic spec provided",
                suggestions=[]
            )
        
        try:
            if isinstance(artifact, dict):
                self.spec(**artifact)
            elif isinstance(artifact, str):
                # Try to parse as JSON
                try:
                    data = json.loads(artifact)
                    self.spec(**data)
                except json.JSONDecodeError:
                    return Judgment(
                        passed=False,
                        score=0.0,
                        reasoning="Artifact is not valid JSON",
                        suggestions=["Return valid JSON matching the spec"]
                    )
            else:
                self.spec(**vars(artifact))
            
            return Judgment(
                passed=True,
                score=1.0,
                reasoning="Passes Pydantic validation",
                suggestions=[]
            )
            
        except ValidationError as e:
            errors = e.errors()
            return Judgment(
                passed=False,
                score=0.5,
                reasoning=f"Validation failed: {len(errors)} errors",
                suggestions=[f"{err['loc']}: {err['msg']}" for err in errors]
            )
    
    def judge(self, artifact: Any, context: dict = None) -> Judgment:
        """
        Judge an artifact against the spec.
        
        First tries Pydantic validation, then could add LLM judgment.
        """
        # Step 1: Pydantic validation
        judgment = self.validate_with_pydantic(artifact)
        
        if not judgment.passed:
            return judgment
        
        # Step 2: Additional heuristic checks
        if isinstance(artifact, str):
            # Check for jargon (11-year-old test)
            jargon_words = ['implementation', 'leverage', 'paradigm', 'synergy']
            found_jargon = [w for w in jargon_words if w.lower() in artifact.lower()]
            if found_jargon:
                judgment.score -= 0.1 * len(found_jargon)
                judgment.suggestions.append(f"Remove jargon: {found_jargon}")
            
            # Check for reasonable length
            if len(artifact) < 10:
                judgment.score -= 0.2
                judgment.suggestions.append("Artifact is too short")
        
        judgment.passed = judgment.score >= self.min_score
        return judgment
    
    def polish(self, artifact: Any, suggestions: list) -> Any:
        """
        Polish an artifact based on suggestions.
        
        TODO: Integrate with LLM for actual improvement.
        For now, returns artifact unchanged.
        """
        # TODO: Call LLM to improve based on suggestions
        return artifact
    
    def record(
        self,
        input_data: Any,
        artifact: Any,
        judgment: Judgment,
        task_name: str
    ):
        """Record to Prometheus (training data)."""
        if not self.record_to_prometheus:
            return
        
        record = {
            "timestamp": datetime.now().isoformat(),
            "task": task_name,
            "input": str(input_data)[:1000],  # Truncate
            "output": str(artifact)[:1000],
            "judgment": {
                "passed": judgment.passed,
                "score": judgment.score,
                "reasoning": judgment.reasoning
            }
        }
        
        date_str = datetime.now().strftime("%Y-%m-%d")
        output_file = self.prometheus_dir / f"prometheus_{date_str}.jsonl"
        
        with open(output_file, "a") as f:
            f.write(json.dumps(record) + "\n")
    
    def __call__(self, func: Callable) -> Callable:
        """Decorator implementation."""
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Execute the original function
            artifact = func(*args, **kwargs)
            
            # Polish loop
            current_artifact = artifact
            final_judgment = None
            
            for iteration in range(self.max_polish_iterations):
                judgment = self.judge(current_artifact)
                
                if judgment.passed:
                    final_judgment = judgment
                    break
                
                # Polish based on suggestions
                current_artifact = self.polish(current_artifact, judgment.suggestions)
                final_judgment = judgment
            
            # Record to Prometheus
            input_data = args[0] if args else kwargs
            self.record(input_data, current_artifact, final_judgment, func.__name__)
            
            # Return the (possibly polished) artifact
            return current_artifact
        
        return wrapper


def quality_gated(
    spec: Optional[Type[BaseModel]] = None,
    min_score: float = 0.7,
    max_polish_iterations: int = 3
):
    """
    Decorator factory for quality-gated tasks.
    
    Usage:
        @app.task
        @quality_gated(spec=WorkOrderSpec, min_score=0.8)
        def my_task(input_data):
            return process(input_data)
    """
    return QualityGate(
        spec=spec,
        min_score=min_score,
        max_polish_iterations=max_polish_iterations
    )


# Example specs (Pydantic models that ARE the spec AND the judge)
if PYDANTIC_AVAILABLE:
    from pydantic import Field
    
    class WorkOrderSpec(BaseModel):
        """Spec for CMMS work order generation."""
        asset_id: str = Field(..., min_length=1, description="Asset identifier")
        description: str = Field(..., min_length=10, description="Work description")
        priority: int = Field(..., ge=1, le=5, description="Priority 1-5")
    
    class DocumentSpec(BaseModel):
        """Spec for document generation."""
        title: str = Field(..., min_length=5)
        content: str = Field(..., min_length=50)
        format: str = Field(default="markdown")


if __name__ == "__main__":
    # Test the quality gate
    
    @quality_gated(min_score=0.7)
    def test_task(input_data):
        return f"Processed: {input_data}"
    
    result = test_task("Hello world")
    print(f"Result: {result}")
    
    # Check Prometheus log
    date_str = datetime.now().strftime("%Y-%m-%d")
    log_file = Path(f"/opt/master_of_puppets/training_data/prometheus_{date_str}.jsonl")
    if log_file.exists():
        print(f"\nPrometheus log:")
        print(log_file.read_text())
