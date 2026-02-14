"""
LLM Prompt Templates for Fault Diagnosis
========================================
Structured prompts that produce technician-friendly explanations.
"""

from typing import Dict, Any, List
from .conveyor_faults import FaultDiagnosis, FaultSeverity


def build_diagnosis_prompt(
    question: str,
    tags: Dict[str, Any],
    faults: List[FaultDiagnosis],
    include_history: bool = False
) -> str:
    """
    Build a structured prompt for the LLM to answer a technician's question.

    Args:
        question: The technician's question (e.g., "Why is the conveyor stopped?")
        tags: Current PLC tag values
        faults: List of detected faults from rule-based analysis
        include_history: Whether to include tag history (future feature)

    Returns:
        Formatted prompt string for the LLM
    """

    # Format current tag state
    tag_lines = []
    for key, value in sorted(tags.items()):
        if key.startswith("_") or key in ("id", "timestamp", "node_id"):
            continue
        if isinstance(value, bool) or value in (0, 1):
            display = "ON" if value else "OFF"
        elif isinstance(value, float):
            display = f"{value:.2f}"
        else:
            display = str(value)
        tag_lines.append(f"  {key}: {display}")

    tag_state = "\n".join(tag_lines)

    # Format detected faults
    if faults:
        fault_lines = []
        for f in faults:
            if f.severity == FaultSeverity.INFO:
                continue  # Skip info-level in prompt
            fault_lines.append(f"  [{f.severity.value.upper()}] {f.fault_code}: {f.title}")
            fault_lines.append(f"    {f.description}")
            if f.likely_causes:
                fault_lines.append(f"    Causes: {', '.join(f.likely_causes[:3])}")
        fault_state = "\n".join(fault_lines) if fault_lines else "  No active faults detected"
    else:
        fault_state = "  No active faults detected"

    prompt = f"""You are an expert industrial maintenance technician assistant for a conveyor system controlled by an Allen-Bradley Micro820 PLC.

CURRENT EQUIPMENT STATE:
{tag_state}

DETECTED FAULTS:
{fault_state}

TECHNICIAN'S QUESTION:
{question}

INSTRUCTIONS:
1. Answer the technician's question directly and concisely
2. Reference specific tag values when relevant
3. Provide 2-4 actionable troubleshooting steps
4. Use plain language - avoid jargon
5. If safety is a concern, mention it first
6. Keep response under 200 words

RESPONSE:"""

    return prompt


def build_why_stopped_prompt(tags: Dict[str, Any], faults: List[FaultDiagnosis]) -> str:
    """Specialized prompt for 'Why is this stopped?' queries."""
    return build_diagnosis_prompt(
        question="Why is this equipment stopped? What should I check first?",
        tags=tags,
        faults=faults
    )


def build_status_summary_prompt(tags: Dict[str, Any], faults: List[FaultDiagnosis]) -> str:
    """Prompt for generating a quick status summary."""
    return build_diagnosis_prompt(
        question="Give me a one-sentence status summary of this equipment.",
        tags=tags,
        faults=faults
    )


SYSTEM_PROMPT = """You are FactoryLM, an AI assistant for industrial maintenance technicians.

Your role:
- Help diagnose equipment faults quickly
- Provide clear, actionable guidance
- Prioritize safety
- Reference real data from PLC tags
- Keep explanations concise

Equipment context:
- Allen-Bradley Micro820 PLC
- Conveyor system with motor, sensors, and pneumatics
- Standard industrial safety interlocks

Communication style:
- Direct and professional
- Use bullet points for steps
- Bold safety warnings
- Reference specific tag names and values"""
