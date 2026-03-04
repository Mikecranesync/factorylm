"""YAML workflow loader and node interpreter for all 6 node types."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .llm import LLMProvider
from .session import EngineResponse, SessionState

logger = logging.getLogger(__name__)


@dataclass
class WorkflowNode:
    id: str
    type: str  # question | advice | await_photo | vision_classify | redirect | escalate_llm
    config: dict = field(default_factory=dict)


@dataclass
class Workflow:
    id: str
    title: str
    start_node: str
    nodes: dict[str, WorkflowNode] = field(default_factory=dict)


def load_workflows(directory: Path) -> dict[str, Workflow]:
    """Load all .yaml files from a directory into Workflow objects."""
    workflows: dict[str, Workflow] = {}
    if not directory.exists():
        logger.warning("Workflows directory does not exist: %s", directory)
        return workflows

    for yaml_file in sorted(directory.glob("*.yaml")):
        try:
            raw = yaml.safe_load(yaml_file.read_text(encoding="utf-8"))
            if not raw or "id" not in raw:
                continue
            wf = Workflow(
                id=raw["id"],
                title=raw.get("title", raw["id"]),
                start_node=raw["start_node"],
            )
            for node_id, node_data in raw.get("nodes", {}).items():
                node_type = node_data.pop("type")
                wf.nodes[node_id] = WorkflowNode(
                    id=node_id, type=node_type, config=node_data
                )
            workflows[wf.id] = wf
            logger.info("Loaded workflow: %s (%d nodes)", wf.id, len(wf.nodes))
        except Exception:
            logger.exception("Failed to load workflow from %s", yaml_file)
    return workflows


def _set_node(session: SessionState, workflow_id: str, node_id: str) -> None:
    """Move session to a new node, recording the path."""
    session.workflow_id = workflow_id
    session.node_id = node_id
    session.path.append(node_id)
    session.add_event("node_reached", node_id=node_id, workflow_id=workflow_id)


def interpret_node(
    session: SessionState, node: WorkflowNode
) -> EngineResponse:
    """Interpret a node and produce an EngineResponse (sync nodes only)."""

    if node.type == "question":
        options = node.config.get("options", [])
        buttons = [
            {"id": opt.get("id", opt["label"]), "label": opt["label"]}
            for opt in options
        ]
        return EngineResponse(
            message_text=node.config.get("text", ""),
            buttons=buttons,
            expecting="button",
        )

    if node.type == "advice":
        has_next = "next" in node.config
        return EngineResponse(
            message_text=node.config.get("text", ""),
            expecting="button" if has_next else "done",
            buttons=[{"id": "__continue__", "label": "Continue"}] if has_next else [],
        )

    if node.type == "await_photo":
        buttons = []
        if node.config.get("on_text_received"):
            buttons.append({"id": "__skip_photo__", "label": "Skip"})
        return EngineResponse(
            message_text=node.config.get("text", "Please send a photo."),
            buttons=buttons,
            expecting="photo",
        )

    if node.type == "redirect":
        # Redirect is handled by the engine's advance loop, not here.
        # Return a placeholder that the engine replaces.
        return EngineResponse(
            message_text="Redirecting...",
            expecting="done",
            metadata={"_redirect": True},
        )

    if node.type in ("vision_classify", "escalate_llm"):
        # These are async — the engine handles them specially.
        return EngineResponse(
            message_text="Processing...",
            expecting="done",
            metadata={"_async_node": node.type},
        )

    logger.warning("Unknown node type: %s", node.type)
    return EngineResponse(message_text=f"Unknown node type: {node.type}", expecting="done")


def advance_choice(
    session: SessionState,
    workflow: Workflow,
    choice: str,
) -> WorkflowNode | None:
    """Given a user choice, find the next node in the workflow."""
    current = workflow.nodes.get(session.node_id or "")
    if not current:
        return None

    if current.type == "question":
        for opt in current.config.get("options", []):
            opt_id = opt.get("id", opt["label"])
            if opt_id == choice or opt["label"] == choice:
                next_id = opt.get("next")
                if next_id and next_id in workflow.nodes:
                    return workflow.nodes[next_id]
        return None

    if current.type == "advice" and choice == "__continue__":
        next_id = current.config.get("next")
        if next_id and next_id in workflow.nodes:
            return workflow.nodes[next_id]

    if current.type == "await_photo" and choice == "__skip_photo__":
        next_id = current.config.get("on_text_received")
        if next_id and next_id in workflow.nodes:
            return workflow.nodes[next_id]

    return None


async def run_vision_classify(
    session: SessionState,
    node: WorkflowNode,
    workflow: Workflow,
    llm: LLMProvider,
) -> tuple[WorkflowNode | None, EngineResponse | None]:
    """Execute a vision_classify node: call LLM, parse category, route."""
    photo_field = node.config.get("photo_field", "photo")
    photo_path = session.data.get(photo_field)
    if not photo_path:
        return None, EngineResponse(
            message_text="No photo available for classification.",
            expecting="done",
        )

    prompt = node.config.get("prompt", "Classify this image. Return JSON with a 'category' key.")
    result = await llm.vision_classify(photo_path, prompt)

    store_as = node.config.get("store_result_as", "vision_result")
    session.data[store_as] = result
    session.add_event("vision_result", **result)

    category = result.get("category", "unknown")
    routes = node.config.get("routes", {})
    next_id = routes.get(category, routes.get("unknown"))
    if next_id and next_id in workflow.nodes:
        return workflow.nodes[next_id], None

    return None, EngineResponse(
        message_text=f"Vision classified as: {category}",
        expecting="done",
        metadata={"vision_result": result},
    )


async def run_escalate_llm(
    session: SessionState,
    node: WorkflowNode,
    llm: LLMProvider,
) -> EngineResponse:
    """Execute an escalate_llm node: call text LLM with session context."""
    system_prompt = (
        "You are a factory troubleshooting assistant. "
        "The user is going through a guided diagnosis workflow. "
        "Based on the session context below, provide actionable advice.\n\n"
        f"Workflow: {session.workflow_id}\n"
        f"Path taken: {' → '.join(session.path)}\n"
        f"Session data: {session.data}\n"
    )
    user_text = node.config.get("text", "Please analyze the situation and provide guidance.")
    messages = [{"role": "user", "content": user_text}]

    answer = await llm.text_complete(system_prompt, messages)
    session.add_event("llm_escalation", response_preview=answer[:200])

    return EngineResponse(
        message_text=answer,
        expecting="done",
        metadata={"escalation": True},
    )
