"""DiagnoseSkill — the core value: PLC tags + fault rules + KB + LLM = actionable answer."""

from __future__ import annotations

import logging

from openclaw.diagnosis.faults import build_diagnosis_prompt, detect_faults
from openclaw.llm.prompts import SYSTEM_PROMPT
from openclaw.messages.models import InboundMessage, OutboundMessage
from openclaw.skills.base import Skill, SkillContext
from openclaw.types import Intent

logger = logging.getLogger(__name__)

# Fault codes eligible for Layer 0 (KB-only) responses
_LAYER0_FAULT_CODES = {"E001", "M001", "M002", "T001", "C001"}

# KB atom types considered actionable enough for Layer 0
_ACTIONABLE_TYPES = {"procedure", "fault_code", "checklist", "troubleshooting"}


class DiagnoseSkill(Skill):
    async def handle(self, message: InboundMessage, context: SkillContext) -> OutboundMessage:
        # 1. Pull live tags from Matrix API
        matrix = context.connectors.get("matrix")
        tags: dict = {}
        if matrix:
            try:
                tag_rows = await matrix.get_latest_tags(limit=1)  # type: ignore[attr-defined]
                if tag_rows:
                    tags = tag_rows[0] if isinstance(tag_rows, list) else tag_rows
            except Exception:
                logger.warning("Matrix API call failed — will attempt KB-only diagnosis")

        if not tags:
            # Attempt KB-only diagnosis instead of dead-end error
            return await self._kb_only_fallback(message, context)

        # 2. Rule-based fault detection (zero latency)
        faults = detect_faults(tags)

        # 3. Query Knowledge Base for matching solutions + sources
        kb_results = await self._query_kb_with_sources(context, faults)
        kb_context = kb_results["context"]
        kb_sources = kb_results["sources"]

        # 4. Layer 0 short-circuit: if KB has actionable steps for a known
        #    fault code, return directly without burning LLM tokens
        if kb_results["layer0_hit"]:
            fault_summary = self._format_fault_summary(faults)
            response_text = fault_summary + "\n\n" + kb_results["layer0_answer"]
            if kb_sources:
                response_text += "\n\n**Sources:**\n" + "\n".join(f"- {s}" for s in kb_sources)
            response_text += "\n\n_Layer 0 (KB direct) | 0ms_"
            response_text = self._maybe_offer_troubleshoot(faults, response_text)
            return OutboundMessage(
                channel=message.channel, user_id=message.user_id,
                text=response_text,
            )

        # 5. Build structured prompt (with KB context if available)
        question = message.text or "Why is this equipment stopped?"
        prompt = build_diagnosis_prompt(question, tags, faults)

        if kb_context:
            prompt += (
                "\n\nKNOWN SOLUTIONS FROM KNOWLEDGE BASE:\n"
                + kb_context
                + "\n\nUse these known solutions to inform your response when relevant."
            )

        # 6. Build messages with conversation history
        history = message.metadata.get("history", [])
        messages = []
        for h in history:
            messages.append({"role": h["role"], "content": h["content"]})
        messages.append({"role": "user", "content": prompt})

        # 7. Route to LLM
        response = await context.llm.route(
            Intent.DIAGNOSE,
            messages=messages,
            system_prompt=SYSTEM_PROMPT,
        )

        # 8. Format response with deterministic Sources block
        response_text = response.text
        if kb_sources:
            response_text += "\n\n**Sources:**\n" + "\n".join(f"- {s}" for s in kb_sources)
        response_text += f"\n\n_Model: {response.model} | {response.latency_ms}ms_"

        # 9. Offer guided troubleshooting if a tree exists for this fault
        response_text = self._maybe_offer_troubleshoot(faults, response_text)

        return OutboundMessage(
            channel=message.channel, user_id=message.user_id,
            text=response_text,
        )

    async def _kb_only_fallback(self, message: InboundMessage, context: SkillContext) -> OutboundMessage:
        """Attempt KB-only diagnosis when PLC/Matrix data is unavailable."""
        question = message.text or ""
        if not question.strip():
            return OutboundMessage(
                channel=message.channel, user_id=message.user_id,
                text="Cannot reach PLC data and no question provided. Is the Matrix API running?",
            )

        # Search KB using the user's question text
        kb = context.connectors.get("knowledge")
        kb_context = ""
        kb_sources: list[str] = []
        if kb:
            try:
                atoms = await kb.search(question, limit=5)  # type: ignore[attr-defined]
                for atom in (atoms or []):
                    title = atom.get("title", "")
                    summary = atom.get("summary", "")[:300]
                    source_url = atom.get("source_url", "")
                    kb_context += f"\n- {title}: {summary}"
                    if source_url:
                        kb_sources.append(f"[{title}]({source_url})")
                    elif title:
                        kb_sources.append(title)
            except Exception:
                logger.exception("KB search failed during KB-only fallback")

        # Build prompt without live tags
        prompt = (
            f"A technician is asking about their equipment but live PLC data is unavailable.\n"
            f"Answer based on your knowledge and any KB context provided.\n\n"
            f"QUESTION: {question}"
        )
        if kb_context:
            prompt += f"\n\nKNOWLEDGE BASE CONTEXT:{kb_context}"

        # Route to LLM with conversation history
        history = message.metadata.get("history", [])
        messages = []
        for h in history:
            messages.append({"role": h["role"], "content": h["content"]})
        messages.append({"role": "user", "content": prompt})

        try:
            response = await context.llm.route(
                Intent.DIAGNOSE,
                messages=messages,
                system_prompt=SYSTEM_PROMPT,
            )
            response_text = response.text
            if kb_sources:
                response_text += "\n\n**Sources:**\n" + "\n".join(f"- {s}" for s in kb_sources)
            response_text += (
                f"\n\n_PLC data unavailable — diagnosis based on KB + your description only_"
                f"\n_Model: {response.model} | {response.latency_ms}ms_"
            )
            return OutboundMessage(
                channel=message.channel, user_id=message.user_id,
                text=response_text,
            )
        except Exception:
            logger.exception("LLM call failed during KB-only fallback")
            return OutboundMessage(
                channel=message.channel, user_id=message.user_id,
                text="Cannot reach PLC data or AI providers. Is the Matrix API running?",
            )

    def _format_fault_summary(self, faults: list) -> str:
        """Format detected faults into a readable summary for Layer 0 responses."""
        lines = []
        for f in faults:
            if f.fault_code in ("OK", "IDLE"):
                continue
            severity_icon = {"emergency": "!!!", "critical": "[!]", "warning": "[~]"}.get(
                f.severity.value, "[i]"
            )
            lines.append(f"{severity_icon} **{f.fault_code}: {f.title}**")
            lines.append(f"  {f.description}")
        return "\n".join(lines) if lines else ""

    async def _query_kb_with_sources(self, context: SkillContext, faults: list) -> dict:
        """Search KB for solutions, extract sources, and check for Layer 0 hits."""
        result = {
            "context": "",
            "sources": [],
            "layer0_hit": False,
            "layer0_answer": "",
        }

        kb = context.connectors.get("knowledge")
        if not kb:
            return result

        kb_lines: list[str] = []
        sources: list[str] = []
        layer0_parts: list[str] = []

        try:
            for fault in faults:
                if fault.fault_code in ("OK", "IDLE"):
                    continue

                # Search by fault code first
                atoms = await kb.search_by_fault_code(fault.fault_code, limit=2)  # type: ignore[attr-defined]

                # Fall back to full-text search on fault description
                if not atoms:
                    atoms = await kb.search(fault.description, limit=3)  # type: ignore[attr-defined]

                if not atoms:
                    continue

                kb_lines.append(f"\n[{fault.fault_code}] {fault.title}:")

                for atom in atoms[:3]:
                    title = atom.get("title", "")
                    atom_type = atom.get("atom_type", "")
                    summary = atom.get("summary", "")[:300]
                    fixes = atom.get("fixes") or []
                    steps = atom.get("steps") or []
                    source_url = atom.get("source_url", "")
                    score = atom.get("score", atom.get("similarity", 0))

                    kb_lines.append(f"  - {title}: {summary}")
                    if fixes:
                        kb_lines.append(f"    Fixes: {'; '.join(fixes[:3])}")
                    if steps:
                        kb_lines.append(f"    Steps: {'; '.join(steps[:3])}")
                    if source_url:
                        kb_lines.append(f"    Source: {source_url}")
                        sources.append(f"[{title}]({source_url})")
                    elif title:
                        sources.append(title)

                    # Check Layer 0 eligibility
                    if (fault.fault_code in _LAYER0_FAULT_CODES
                            and atom_type in _ACTIONABLE_TYPES
                            and (steps or fixes)
                            and (score > 0.85 if score else True)):
                        parts = [f"**{title}** (KB match for {fault.fault_code})", ""]
                        if summary:
                            parts.append(summary)
                            parts.append("")
                        if steps:
                            parts.append("**Steps:**")
                            for i, step in enumerate(steps, 1):
                                parts.append(f"{i}. {step}")
                            parts.append("")
                        if fixes:
                            parts.append("**Known fixes:**")
                            for fix in fixes:
                                parts.append(f"- {fix}")
                        layer0_parts.append("\n".join(parts))

        except Exception:
            logger.exception("KB query failed during diagnosis")

        result["context"] = "\n".join(kb_lines)
        result["sources"] = sources

        if layer0_parts:
            result["layer0_hit"] = True
            result["layer0_answer"] = "\n\n---\n\n".join(layer0_parts)

        return result

    def _maybe_offer_troubleshoot(self, faults: list, response_text: str) -> str:
        """Append troubleshoot offer if a guided tree exists for any detected fault."""
        try:
            from openclaw.troubleshoot.engine import TreeRunner

            # Try to get the shared runner instance from the skill registry
            runner = getattr(self, "_troubleshoot_runner", None)
            if runner is None:
                return response_text

            for fault in faults:
                if fault.fault_code in ("OK", "IDLE"):
                    continue
                tree = runner.find_tree_by_fault(fault.fault_code)
                if tree:
                    response_text += (
                        f"\n\nWant me to walk you through it step by step? "
                        f"Type /troubleshoot or just say \"yes\"."
                    )
                    break
        except Exception:
            pass  # Don't break diagnosis if troubleshoot import fails
        return response_text

    def intents(self) -> list[Intent]:
        return [Intent.DIAGNOSE]

    def name(self) -> str:
        return "diagnose"

    def description(self) -> str:
        return "Diagnose equipment faults using live PLC data and AI"
