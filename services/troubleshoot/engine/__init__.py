"""Troubleshooting Engine — public API."""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

from .llm import LLMProvider
from .session import EngineResponse, SessionState
from .workflows import (
    Workflow,
    _set_node,
    advance_choice,
    interpret_node,
    load_workflows,
    run_escalate_llm,
    run_vision_classify,
)

__all__ = [
    "TroubleshootEngine",
    "SessionState",
    "EngineResponse",
    "LLMProvider",
]

logger = logging.getLogger(__name__)

DEFAULT_WORKFLOW = "photo_triage"


class TroubleshootEngine:
    def __init__(self, workflows_dir: Path, llm: LLMProvider, work_orders_dir: Path | None = None):
        self._workflows = load_workflows(workflows_dir)
        self._llm = llm
        self._sessions: dict[str, SessionState] = {}
        self._work_orders_dir = work_orders_dir or workflows_dir.parent / "work_orders"
        self._work_orders_dir.mkdir(parents=True, exist_ok=True)
        logger.info(
            "Engine initialized with %d workflows: %s",
            len(self._workflows),
            list(self._workflows.keys()),
        )

    def start_session(
        self, user_id: str, equipment_hint: str | None = None
    ) -> tuple[SessionState, EngineResponse]:
        session = SessionState(user_id=user_id)
        if equipment_hint:
            session.data["equipment_hint"] = equipment_hint
        session.add_event("session_start")

        # Pick starting workflow
        wf_id = DEFAULT_WORKFLOW if DEFAULT_WORKFLOW in self._workflows else next(iter(self._workflows), None)
        if not wf_id:
            return session, EngineResponse(
                message_text="No workflows available. Please contact support.",
                expecting="done",
            )

        workflow = self._workflows[wf_id]
        _set_node(session, wf_id, workflow.start_node)

        start_node = workflow.nodes.get(workflow.start_node)
        if not start_node:
            return session, EngineResponse(
                message_text="Workflow configuration error.",
                expecting="done",
            )

        self._sessions[session.session_id] = session
        response = interpret_node(session, start_node)
        self._persist_work_order(session)
        return session, response

    async def handle_text(self, session: SessionState, text: str) -> EngineResponse:
        session.add_event("text_received", text=text)
        workflow, node = self._current(session)
        if not workflow or not node:
            return EngineResponse(message_text="Session not active.", expecting="done")

        # If awaiting photo and text received, check on_text_received
        if node.type == "await_photo":
            next_id = node.config.get("on_text_received")
            if next_id and next_id in workflow.nodes:
                next_node = workflow.nodes[next_id]
                _set_node(session, workflow.id, next_id)
                return await self._resolve_node(session, next_node, workflow)

        # For question nodes, try matching text to an option label
        if node.type == "question":
            next_node = advance_choice(session, workflow, text)
            if next_node:
                _set_node(session, workflow.id, next_node.id)
                return await self._resolve_node(session, next_node, workflow)

        return EngineResponse(
            message_text="Please use the buttons to respond, or send a photo if requested.",
            buttons=interpret_node(session, node).buttons,
            expecting=interpret_node(session, node).expecting,
        )

    async def handle_button(self, session: SessionState, button_id: str) -> EngineResponse:
        session.add_event("button_pressed", button_id=button_id)
        workflow, node = self._current(session)
        if not workflow or not node:
            return EngineResponse(message_text="Session not active.", expecting="done")

        next_node = advance_choice(session, workflow, button_id)
        if not next_node:
            return EngineResponse(
                message_text="Invalid selection. Please try again.",
                buttons=interpret_node(session, node).buttons,
                expecting="button",
            )

        _set_node(session, workflow.id, next_node.id)
        return await self._resolve_node(session, next_node, workflow)

    async def handle_photo(self, session: SessionState, photo_path: str) -> EngineResponse:
        session.photos.append(photo_path)
        session.add_event("photo_received", path=photo_path)

        workflow, node = self._current(session)
        if not workflow or not node:
            return EngineResponse(message_text="Session not active.", expecting="done")

        if node.type == "await_photo":
            store_as = node.config.get("store_as", "photo")
            if node.config.get("append"):
                existing = session.data.get(store_as, [])
                if not isinstance(existing, list):
                    existing = [existing]
                existing.append(photo_path)
                session.data[store_as] = existing
            else:
                session.data[store_as] = photo_path

            next_id = node.config.get("on_photo_received")
            if next_id and next_id in workflow.nodes:
                next_node = workflow.nodes[next_id]
                _set_node(session, workflow.id, next_id)
                return await self._resolve_node(session, next_node, workflow)

        response = interpret_node(session, node)
        response.message_text = "\U0001f4f7 Photo saved. " + response.message_text
        return response

    def get_session_summary(self, session: SessionState) -> dict:
        """Export session as work-order JSON."""
        return {
            "session_id": session.session_id,
            "user_id": session.user_id,
            "created_at": datetime.fromtimestamp(session.created_at, tz=timezone.utc).isoformat(),
            "completed_at": datetime.fromtimestamp(session.updated_at, tz=timezone.utc).isoformat(),
            "workflow_id": session.workflow_id,
            "path_taken": session.path,
            "data": session.data,
            "evidence_photos": session.photos,
            "events": session.events,
        }

    # --- Internal helpers ---

    def _current(self, session: SessionState) -> tuple[Workflow | None, object | None]:
        wf = self._workflows.get(session.workflow_id or "")
        if not wf:
            return None, None
        node = wf.nodes.get(session.node_id or "")
        return wf, node

    async def _resolve_node(
        self, session: SessionState, node, workflow: Workflow
    ) -> EngineResponse:
        """Resolve a node, handling async types and redirects in a loop."""
        max_hops = 20  # Guard against infinite redirect loops
        for _ in range(max_hops):
            if node.type == "redirect":
                target_wf_id = node.config.get("target_workflow")
                target_node_id = node.config.get("target_start_node")
                target_wf = self._workflows.get(target_wf_id or "")
                if not target_wf:
                    return EngineResponse(
                        message_text=f"Workflow '{target_wf_id}' not found.",
                        expecting="done",
                    )
                target_node = target_wf.nodes.get(
                    target_node_id or target_wf.start_node
                )
                if not target_node:
                    return EngineResponse(
                        message_text="Target node not found.",
                        expecting="done",
                    )
                _set_node(session, target_wf.id, target_node.id)
                workflow = target_wf
                node = target_node
                continue

            if node.type == "vision_classify":
                next_node, fallback = await run_vision_classify(
                    session, node, workflow, self._llm
                )
                if next_node:
                    _set_node(session, workflow.id, next_node.id)
                    node = next_node
                    continue
                self._persist_work_order(session)
                return fallback

            if node.type == "escalate_llm":
                response = await run_escalate_llm(session, node, self._llm)
                self._persist_work_order(session)
                return response

            # Sync node types
            response = interpret_node(session, node)
            self._persist_work_order(session)
            return response

        return EngineResponse(message_text="Workflow loop detected.", expecting="done")

    def _persist_work_order(self, session: SessionState) -> None:
        try:
            path = self._work_orders_dir / f"{session.session_id}.json"
            path.write_text(
                json.dumps(self.get_session_summary(session), indent=2, default=str),
                encoding="utf-8",
            )
        except Exception:
            logger.exception("Failed to persist work order for %s", session.session_id)
