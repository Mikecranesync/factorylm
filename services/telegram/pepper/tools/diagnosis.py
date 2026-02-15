"""
Diagnosis Tool for PEPPER

AI-powered fault diagnosis using LLM intelligence.
God Mode: Full access with extended context
Demo Mode: Limited to specific equipment
"""

from typing import Any, Dict, List, Optional
import httpx
import json

from .base import BaseTool, ToolContext, ToolResult, ToolResultStatus, UserMode


class DiagnosisTool(BaseTool):
    """AI fault diagnosis (available to both modes)"""

    name = "diagnosis"
    description = "AI-powered equipment fault diagnosis and troubleshooting"
    required_mode = UserMode.ANY

    # LLM Service endpoints
    GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
    CLAUDE_API_URL = "https://api.anthropic.com/v1/messages"

    def __init__(self, groq_api_key: Optional[str] = None, claude_api_key: Optional[str] = None):
        super().__init__()
        self.groq_api_key = groq_api_key
        self.claude_api_key = claude_api_key

    def _get_parameter_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": ["diagnose", "get_fault_history", "suggest_solution"],
                    "description": "Diagnosis operation to perform"
                },
                "question": {
                    "type": "string",
                    "description": "Natural language question for diagnosis"
                },
                "equipment_id": {
                    "type": "string",
                    "description": "Equipment identifier for context"
                },
                "fault_code": {
                    "type": "string",
                    "description": "Specific fault code to diagnose"
                },
                "context": {
                    "type": "object",
                    "description": "Additional context (equipment state, sensor data, etc.)"
                },
                "use_claude": {
                    "type": "boolean",
                    "description": "Use Claude instead of Groq (default: false)"
                }
            },
            "required": ["operation"]
        }

    async def execute(
        self,
        params: Dict[str, Any],
        context: ToolContext
    ) -> ToolResult:
        """Execute diagnosis operation"""
        operation = params.get("operation")

        if not operation:
            return ToolResult(
                status=ToolResultStatus.ERROR,
                error="Missing required parameter: operation"
            )

        # Route to specific operation
        operations = {
            "diagnose": self._diagnose,
            "get_fault_history": self._get_fault_history,
            "suggest_solution": self._suggest_solution,
        }

        handler = operations.get(operation)
        if not handler:
            return ToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Unknown operation: {operation}"
            )

        return await handler(params, context)

    async def _diagnose(
        self,
        params: Dict[str, Any],
        context: ToolContext
    ) -> ToolResult:
        """Perform AI diagnosis"""
        question = params.get("question")
        equipment_id = params.get("equipment_id")
        fault_code = params.get("fault_code")
        additional_context = params.get("context", {})
        use_claude = params.get("use_claude", False)

        if not question and not fault_code:
            return ToolResult(
                status=ToolResultStatus.ERROR,
                error="Either 'question' or 'fault_code' must be provided"
            )

        try:
            # Build diagnosis prompt
            prompt = self._build_diagnosis_prompt(
                question=question,
                equipment_id=equipment_id,
                fault_code=fault_code,
                context=additional_context,
                user_mode=context.mode
            )

            # Call LLM
            if use_claude and self.claude_api_key:
                diagnosis = await self._call_claude(prompt)
            elif self.groq_api_key:
                diagnosis = await self._call_groq(prompt)
            else:
                return ToolResult(
                    status=ToolResultStatus.ERROR,
                    error="No LLM API key configured"
                )

            return ToolResult(
                status=ToolResultStatus.SUCCESS,
                data={
                    "question": question,
                    "equipment_id": equipment_id,
                    "fault_code": fault_code,
                    "diagnosis": diagnosis,
                    "model": "claude" if use_claude else "groq"
                },
                metadata={
                    "operation": "diagnose",
                    "user_mode": context.mode.value
                }
            )

        except Exception as e:
            return ToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Diagnosis failed: {str(e)}"
            )

    def _build_diagnosis_prompt(
        self,
        question: Optional[str],
        equipment_id: Optional[str],
        fault_code: Optional[str],
        context: Dict[str, Any],
        user_mode: UserMode
    ) -> str:
        """Build diagnosis prompt for LLM"""
        parts = [
            "You are an expert industrial equipment diagnostician.",
            "Analyze the following issue and provide a clear diagnosis.\n"
        ]

        if equipment_id:
            parts.append(f"Equipment ID: {equipment_id}")

        if fault_code:
            parts.append(f"Fault Code: {fault_code}")

        if question:
            parts.append(f"Question: {question}")

        if context:
            parts.append(f"Additional Context:\n{json.dumps(context, indent=2)}")

        parts.append("\nProvide:")
        parts.append("1. Root cause analysis")
        parts.append("2. Immediate actions to take")
        parts.append("3. Long-term preventive measures")

        if user_mode == UserMode.DEMO:
            parts.append("\nNote: Response is for demo user - avoid suggesting system-level changes.")

        return "\n".join(parts)

    async def _call_groq(self, prompt: str) -> str:
        """Call Groq API for diagnosis"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.GROQ_API_URL,
                    headers={
                        "Authorization": f"Bearer {self.groq_api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": "mixtral-8x7b-32768",
                        "messages": [
                            {
                                "role": "user",
                                "content": prompt
                            }
                        ],
                        "temperature": 0.3,
                        "max_tokens": 2000
                    },
                    timeout=30
                )

                if response.status_code != 200:
                    raise Exception(f"Groq API error: {response.text}")

                data = response.json()
                return data["choices"][0]["message"]["content"]

        except Exception as e:
            raise Exception(f"Groq API call failed: {str(e)}")

    async def _call_claude(self, prompt: str) -> str:
        """Call Claude API for diagnosis"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.CLAUDE_API_URL,
                    headers={
                        "x-api-key": self.claude_api_key,
                        "anthropic-version": "2023-06-01",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": "claude-3-5-sonnet-20241022",
                        "max_tokens": 2000,
                        "messages": [
                            {
                                "role": "user",
                                "content": prompt
                            }
                        ]
                    },
                    timeout=30
                )

                if response.status_code != 200:
                    raise Exception(f"Claude API error: {response.text}")

                data = response.json()
                return data["content"][0]["text"]

        except Exception as e:
            raise Exception(f"Claude API call failed: {str(e)}")

    async def _get_fault_history(
        self,
        params: Dict[str, Any],
        context: ToolContext
    ) -> ToolResult:
        """Get historical fault data for equipment"""
        equipment_id = params.get("equipment_id")

        if not equipment_id:
            return ToolResult(
                status=ToolResultStatus.ERROR,
                error="Missing required parameter: equipment_id"
            )

        try:
            # Query fault database (placeholder - would connect to actual DB)
            # For now, return mock data structure
            return ToolResult(
                status=ToolResultStatus.SUCCESS,
                data={
                    "equipment_id": equipment_id,
                    "fault_history": [
                        {
                            "timestamp": "2024-02-10T14:30:00Z",
                            "fault_code": "E1001",
                            "description": "Motor overload",
                            "duration": 45,
                            "resolved": True
                        }
                    ],
                    "total_faults": 1,
                    "mtbf": 720  # Mean time between failures (hours)
                },
                metadata={
                    "operation": "get_fault_history",
                    "source": "fault_database"
                }
            )

        except Exception as e:
            return ToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Failed to get fault history: {str(e)}"
            )

    async def _suggest_solution(
        self,
        params: Dict[str, Any],
        context: ToolContext
    ) -> ToolResult:
        """Suggest solution for specific fault"""
        fault_code = params.get("fault_code")
        equipment_id = params.get("equipment_id")

        if not fault_code:
            return ToolResult(
                status=ToolResultStatus.ERROR,
                error="Missing required parameter: fault_code"
            )

        try:
            # Build solution prompt
            prompt = f"""
            Provide a step-by-step troubleshooting guide for fault code {fault_code}.

            Equipment ID: {equipment_id or 'Unknown'}

            Include:
            1. Safety precautions
            2. Diagnostic steps
            3. Common fixes
            4. When to escalate
            """

            # Call LLM
            if self.groq_api_key:
                solution = await self._call_groq(prompt)
            else:
                return ToolResult(
                    status=ToolResultStatus.ERROR,
                    error="No LLM API key configured"
                )

            return ToolResult(
                status=ToolResultStatus.SUCCESS,
                data={
                    "fault_code": fault_code,
                    "equipment_id": equipment_id,
                    "solution": solution
                },
                metadata={
                    "operation": "suggest_solution"
                }
            )

        except Exception as e:
            return ToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Failed to suggest solution: {str(e)}"
            )
