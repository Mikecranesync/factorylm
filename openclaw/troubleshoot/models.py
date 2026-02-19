"""Data models for the troubleshooting engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class TreeOption:
    """A single answer choice on a question node."""
    label: str
    next: str
    transition: str = ""


@dataclass
class TreeNode:
    """A node in a troubleshooting decision tree."""
    id: str
    type: str  # "question" or "resolution"
    text: str
    # Question fields
    hint: str = ""
    plc_tag: str | None = None
    options: list[TreeOption] = field(default_factory=list)
    # Resolution fields
    steps: list[str] = field(default_factory=list)
    severity: str = ""
    requires_maintenance: bool = False
    llm_handoff: bool = False

    @classmethod
    def from_dict(cls, node_id: str, data: dict) -> TreeNode:
        options = [
            TreeOption(
                label=o.get("label", ""),
                next=o.get("next", ""),
                transition=o.get("transition", ""),
            )
            for o in data.get("options", [])
        ]
        return cls(
            id=node_id,
            type=data.get("type", "question"),
            text=data.get("text", ""),
            hint=data.get("hint", ""),
            plc_tag=data.get("plc_tag"),
            options=options,
            steps=data.get("steps", []),
            severity=data.get("severity", ""),
            requires_maintenance=data.get("requires_maintenance", False),
            llm_handoff=data.get("llm_handoff", False),
        )


@dataclass
class TroubleshootTree:
    """A complete troubleshooting decision tree."""
    tree_id: int | None
    slug: str
    title: str
    description: str
    fault_codes: list[str]
    trigger_words: list[str]
    equipment: str
    root: str
    nodes: dict[str, TreeNode]
    version: int = 1
    is_active: bool = True

    @classmethod
    def from_db_row(cls, row: dict) -> TroubleshootTree:
        tree_data = row.get("tree", {})
        nodes_raw = tree_data.get("nodes", {})
        nodes = {nid: TreeNode.from_dict(nid, ndata) for nid, ndata in nodes_raw.items()}
        return cls(
            tree_id=row.get("tree_id"),
            slug=row.get("slug", ""),
            title=row.get("title", ""),
            description=row.get("description", ""),
            fault_codes=row.get("fault_codes", []),
            trigger_words=row.get("trigger_words", []),
            equipment=row.get("equipment", ""),
            root=tree_data.get("root", ""),
            nodes=nodes,
            version=row.get("version", 1),
            is_active=row.get("is_active", True),
        )

    @classmethod
    def from_json(cls, data: dict) -> TroubleshootTree:
        """Load from a JSON file (seed format)."""
        tree_data = data.get("tree", {})
        nodes_raw = tree_data.get("nodes", {})
        nodes = {nid: TreeNode.from_dict(nid, ndata) for nid, ndata in nodes_raw.items()}
        return cls(
            tree_id=None,
            slug=data.get("slug", ""),
            title=data.get("title", ""),
            description=data.get("description", ""),
            fault_codes=data.get("fault_codes", []),
            trigger_words=data.get("trigger_words", []),
            equipment=data.get("equipment", ""),
            root=tree_data.get("root", ""),
            nodes=nodes,
            version=data.get("version", 1),
            is_active=data.get("is_active", True),
        )


@dataclass
class TroubleshootSession:
    """Active troubleshooting session for a user."""
    user_id: str
    tree_slug: str
    current_node: str
    started_at: float
    last_activity: float
    answers: list[dict] = field(default_factory=list)  # [{node_id, question, answer, ts}]
    plc_snapshot: dict = field(default_factory=dict)
    fault_code: str | None = None
    last_transition: str = ""  # Transition text from the last answer chosen


@dataclass
class TreeResponse:
    """Response from the troubleshoot engine to format and send."""
    type: str  # "question", "resolution", "llm_handoff", "not_found", "expired"
    text: str
    node: TreeNode | None = None
    session: TroubleshootSession | None = None
    context_for_llm: dict[str, Any] = field(default_factory=dict)
