"""TroubleshootSkill — coaching-style guided diagnosis via decision trees."""

from __future__ import annotations

import logging

from openclaw.messages.models import InboundMessage, OutboundMessage
from openclaw.skills.base import Skill, SkillContext
from openclaw.troubleshoot.engine import TreeRunner
from openclaw.troubleshoot.models import TreeNode, TreeResponse, TroubleshootSession
from openclaw.types import Intent

logger = logging.getLogger(__name__)

# System prompt for LLM handoff — continue the coaching tone
LLM_HANDOFF_PROMPT = (
    "You are continuing a troubleshooting session that a guided system started. "
    "A senior technician was coaching the user through step-by-step checks. "
    "Continue in the same conversational, coaching tone — direct, encouraging, practical. "
    "Use 'let's', 'go ahead and', 'alright' — not 'Step 1 of 7:'. "
    "The user is on their phone at the equipment. Keep it brief and actionable."
)


class TroubleshootSkill(Skill):
    """Walks technicians through deterministic troubleshooting trees."""

    def __init__(self, runner: TreeRunner) -> None:
        self._runner = runner

    async def handle(self, message: InboundMessage, context: SkillContext) -> OutboundMessage:
        user_id = message.user_id
        text = (message.text or "").strip()

        # Check for active session — user is answering a question
        if self._runner.has_active_session(user_id):
            # "cancel" / "quit" / "exit" ends the session
            if text.lower() in ("cancel", "quit", "exit", "stop"):
                self._runner.cancel(user_id)
                return OutboundMessage(
                    channel=message.channel,
                    user_id=user_id,
                    text="Troubleshooting cancelled. Ask anytime to start again.",
                )

            response = self._runner.answer(user_id, text)
            return await self._format_response(response, message, context)

        # No active session — start a new one
        # Try to find a tree: by fault code in metadata, then by trigger words
        fault_code = message.metadata.get("fault_code")
        tree = None

        if fault_code:
            tree = self._runner.find_tree_by_fault(fault_code)

        if not tree:
            tree = self._runner.find_tree_by_trigger(text)

        if not tree:
            # List available trees
            available = self._runner.list_trees()
            if not available:
                return OutboundMessage(
                    channel=message.channel,
                    user_id=user_id,
                    text="No troubleshooting guides loaded yet. Try /diagnose first.",
                )
            lines = ["Which issue are you dealing with?\n"]
            for i, t in enumerate(available, 1):
                codes = ", ".join(t.fault_codes) if t.fault_codes else ""
                codes_str = f" ({codes})" if codes else ""
                lines.append(f"{i}) {t.title}{codes_str}")
            lines.append("\nReply with the number, or describe the problem.")
            return OutboundMessage(
                channel=message.channel,
                user_id=user_id,
                text="\n".join(lines),
            )

        # Start the session
        plc_snapshot = message.metadata.get("plc_snapshot", {})
        response = self._runner.start(user_id, tree.slug, fault_code=fault_code, plc_snapshot=plc_snapshot)
        return await self._format_response(response, message, context, is_first=True)

    async def _format_response(
        self,
        response: TreeResponse,
        message: InboundMessage,
        context: SkillContext,
        is_first: bool = False,
    ) -> OutboundMessage:
        """Format a TreeResponse into a coaching-style Telegram message."""

        if response.type == "question":
            text = self._format_question(response, is_first)
        elif response.type == "resolution":
            text = self._format_resolution(response)
        elif response.type == "llm_handoff":
            return await self._handle_llm_handoff(response, message, context)
        elif response.type == "expired":
            text = response.text
        elif response.type == "not_found":
            text = response.text
        else:
            text = response.text

        return OutboundMessage(
            channel=message.channel,
            user_id=message.user_id,
            text=text,
        )

    def _format_question(self, response: TreeResponse, is_first: bool = False) -> str:
        """Format a question node in coaching tone."""
        node = response.node
        session = response.session
        if not node or not session:
            return response.text

        parts: list[str] = []

        # Add transition from previous answer (coaching continuity)
        if session.last_transition and not is_first:
            parts.append(session.last_transition)
            parts.append("")

        # The question itself (already authored in coaching tone in the JSON)
        parts.append(node.text)

        # Optional hint
        if node.hint:
            parts.append(node.hint)

        # Numbered options
        parts.append("")
        for i, opt in enumerate(node.options, 1):
            parts.append(f"{i}) {opt.label}")

        return "\n".join(parts)

    def _format_resolution(self, response: TreeResponse) -> str:
        """Format a resolution node — actionable steps in natural language."""
        node = response.node
        session = response.session
        if not node:
            return response.text

        parts: list[str] = []

        # Transition from the last answer
        if session and session.last_transition:
            parts.append(session.last_transition)
            parts.append("")

        # Resolution text (the "diagnosis")
        parts.append(node.text)

        # Action steps
        if node.steps:
            parts.append("")
            parts.append("Here's what to do:")
            for i, step in enumerate(node.steps, 1):
                parts.append(f"{i}. {step}")

        # Maintenance callout
        if node.requires_maintenance:
            parts.append("")
            parts.append("This needs a maintenance work order — want me to create one?")

        # Footer
        parts.append("")
        parts.append("_Resolved via troubleshooting guide | 0ms_")

        return "\n".join(parts)

    async def _handle_llm_handoff(
        self,
        response: TreeResponse,
        message: InboundMessage,
        context: SkillContext,
    ) -> OutboundMessage:
        """Hand off to LLM with accumulated troubleshooting context."""
        ctx = response.context_for_llm

        # Build a structured prompt with all the context
        prompt_parts = [
            f"TROUBLESHOOTING CONTEXT:",
            f"Issue: {ctx.get('tree_title', 'Unknown')}",
            f"Fault code: {ctx.get('fault_code', 'N/A')}",
        ]

        steps = ctx.get("steps_completed", [])
        if steps:
            prompt_parts.append("\nChecks already performed:")
            for step in steps:
                prompt_parts.append(f"  Q: {step.get('question', '')}")
                prompt_parts.append(f"  A: {step.get('answer', '')}")

        plc = ctx.get("plc_snapshot", {})
        if plc:
            prompt_parts.append(f"\nLive PLC data: {plc}")

        unmatched = ctx.get("unmatched_input", "")
        if unmatched:
            prompt_parts.append(f"\nTechnician's input (didn't match guided options): {unmatched}")

        if response.node and response.node.text:
            prompt_parts.append(f"\nThe guided system reached this point: {response.node.text}")

        prompt_parts.append("\nContinue helping the technician from here.")

        prompt = "\n".join(prompt_parts)

        # Build messages with history
        history = message.metadata.get("history", [])
        messages = [{"role": h["role"], "content": h["content"]} for h in history]
        messages.append({"role": "user", "content": prompt})

        try:
            llm_response = await context.llm.route(
                Intent.TROUBLESHOOT,
                messages=messages,
                system_prompt=LLM_HANDOFF_PROMPT,
            )
            text = llm_response.text
            text += f"\n\n_LLM handoff from troubleshoot guide | {llm_response.model} | {llm_response.latency_ms}ms_"
        except Exception:
            logger.exception("LLM handoff failed")
            text = (
                "I've run out of guided steps for this one, and couldn't reach the AI backend. "
                "Based on what we've checked so far, I'd recommend calling in a senior tech. "
                "Here's what we know:\n\n"
            )
            steps = ctx.get("steps_completed", [])
            for step in steps:
                text += f"- {step.get('question', '')}: {step.get('answer', '')}\n"

        return OutboundMessage(
            channel=message.channel,
            user_id=message.user_id,
            text=text,
        )

    def intents(self) -> list[Intent]:
        return [Intent.TROUBLESHOOT]

    def name(self) -> str:
        return "troubleshoot"

    def description(self) -> str:
        return "Step-by-step guided troubleshooting for equipment faults"
