"""
Factory Capability - PLC Diagnosis
==================================
Diagnose factory equipment issues using AI.
"""

import os
import logging
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)

# AI providers for diagnosis
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")


class FactoryCapability:
    """PLC and factory equipment diagnosis."""

    def __init__(
        self,
        groq_api_key: str = None,
        anthropic_api_key: str = None,
        openai_api_key: str = None
    ):
        self.groq_api_key = groq_api_key or GROQ_API_KEY
        self.anthropic_api_key = anthropic_api_key or ANTHROPIC_API_KEY
        self.openai_api_key = openai_api_key or OPENAI_API_KEY

        # Standard diagnosis context
        self.system_prompt = """You are a factory automation expert specializing in:
- Allen-Bradley Micro 820/850 PLCs
- Factory I/O simulation software
- Industrial sensors and actuators
- Conveyor systems and sorting equipment
- VFD drives and motor control

When diagnosing issues:
1. Ask clarifying questions if needed
2. Check the most common causes first
3. Provide step-by-step troubleshooting
4. Explain in clear, practical terms
5. Reference specific IO points when possible

Be concise but thorough. Factory workers need clear answers quickly."""

    async def health(self) -> dict:
        """Check factory capability health."""
        has_ai = bool(self.groq_api_key or self.anthropic_api_key or self.openai_api_key)
        return {
            "status": "ok" if has_ai else "degraded",
            "ai_available": has_ai,
        }

    async def diagnose(
        self,
        problem: str,
        context: str = "",
        io_state: Dict[str, Any] = None
    ) -> str:
        """
        Diagnose a factory problem.

        Args:
            problem: Description of the issue
            context: Additional context (equipment model, recent changes)
            io_state: Current PLC IO state if available

        Returns:
            Diagnosis and recommendations
        """
        # Build the prompt
        prompt_parts = [f"Problem: {problem}"]

        if context:
            prompt_parts.append(f"\nContext: {context}")

        if io_state:
            io_summary = "\n".join(f"  {k}: {v}" for k, v in io_state.items())
            prompt_parts.append(f"\nCurrent IO State:\n{io_summary}")

        prompt = "\n".join(prompt_parts)

        # Try AI providers in order: Groq (fast) -> Anthropic (smart) -> OpenAI
        response = None

        if self.groq_api_key:
            response = await self._call_groq(prompt)
            if response:
                return response

        if self.anthropic_api_key:
            response = await self._call_anthropic(prompt)
            if response:
                return response

        if self.openai_api_key:
            response = await self._call_openai(prompt)
            if response:
                return response

        return "[Diagnosis unavailable - no AI API keys configured]"

    async def _call_groq(self, prompt: str) -> Optional[str]:
        """Call Groq API."""
        try:
            import httpx

            payload = {
                "model": "llama-3.1-70b-versatile",
                "messages": [
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": 1024,
                "temperature": 0.3
            }

            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    json=payload,
                    headers={"Authorization": f"Bearer {self.groq_api_key}"}
                )

                if resp.status_code == 200:
                    data = resp.json()
                    return data["choices"][0]["message"]["content"]
                else:
                    logger.error(f"Groq error: {resp.status_code}")
                    return None

        except Exception as e:
            logger.error(f"Groq failed: {e}")
            return None

    async def _call_anthropic(self, prompt: str) -> Optional[str]:
        """Call Anthropic API."""
        try:
            import httpx

            payload = {
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 1024,
                "system": self.system_prompt,
                "messages": [
                    {"role": "user", "content": prompt}
                ]
            }

            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    json=payload,
                    headers={
                        "x-api-key": self.anthropic_api_key,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json"
                    }
                )

                if resp.status_code == 200:
                    data = resp.json()
                    return data["content"][0]["text"]
                else:
                    logger.error(f"Anthropic error: {resp.status_code}")
                    return None

        except Exception as e:
            logger.error(f"Anthropic failed: {e}")
            return None

    async def _call_openai(self, prompt: str) -> Optional[str]:
        """Call OpenAI API."""
        try:
            import httpx

            payload = {
                "model": "gpt-4o",
                "messages": [
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": 1024,
                "temperature": 0.3
            }

            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    json=payload,
                    headers={"Authorization": f"Bearer {self.openai_api_key}"}
                )

                if resp.status_code == 200:
                    data = resp.json()
                    return data["choices"][0]["message"]["content"]
                else:
                    logger.error(f"OpenAI error: {resp.status_code}")
                    return None

        except Exception as e:
            logger.error(f"OpenAI failed: {e}")
            return None

    async def analyze_io(self, io_state: Dict[str, Any]) -> str:
        """Analyze IO state and identify potential issues."""
        return await self.diagnose(
            "Analyze this IO state for any abnormalities or issues",
            io_state=io_state
        )

    async def explain_fault(
        self,
        fault_code: str,
        equipment: str = "Micro 820"
    ) -> str:
        """Explain a PLC fault code."""
        return await self.diagnose(
            f"Explain fault code {fault_code} on {equipment} and how to resolve it"
        )

    async def check_sequence(
        self,
        expected: List[str],
        actual: List[str]
    ) -> str:
        """Compare expected vs actual sequence and diagnose differences."""
        prompt = (
            f"Expected sequence: {', '.join(expected)}\n"
            f"Actual sequence: {', '.join(actual)}\n\n"
            "Analyze the difference and diagnose what went wrong."
        )
        return await self.diagnose(prompt)

    async def maintenance_check(self, equipment: str, runtime_hours: int) -> str:
        """Get maintenance recommendations."""
        return await self.diagnose(
            f"What maintenance should be performed on {equipment} after {runtime_hours} hours?"
        )

    def common_faults(self) -> Dict[str, str]:
        """Return common fault codes and their meanings."""
        return {
            "E01": "Emergency stop activated",
            "E02": "Motor overload",
            "E03": "Sensor timeout",
            "E04": "Communication loss",
            "E05": "Position error",
            "E06": "Jam detected",
            "E07": "Low air pressure",
            "E08": "Temperature alarm",
            "E09": "Safety circuit open",
            "E10": "Encoder fault",
        }
