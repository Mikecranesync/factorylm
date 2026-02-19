"""TreeRunner — session management and node traversal for troubleshoot trees."""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Optional

from openclaw.troubleshoot.models import (
    TreeNode,
    TreeResponse,
    TroubleshootSession,
    TroubleshootTree,
)

logger = logging.getLogger(__name__)

SESSION_TTL = 1800  # 30 minutes
SESSION_FILE = Path("/tmp/openclaw_troubleshoot_sessions.json")


class TreeRunner:
    """Manages troubleshoot sessions and walks users through decision trees."""

    def __init__(self, trees: dict[str, TroubleshootTree] | None = None) -> None:
        self._trees: dict[str, TroubleshootTree] = trees or {}
        self._sessions: dict[str, TroubleshootSession] = {}
        self._load_sessions()

    # ------------------------------------------------------------------
    # Tree management
    # ------------------------------------------------------------------

    def load_trees(self, trees: list[TroubleshootTree]) -> None:
        """Load trees into memory, keyed by slug."""
        for tree in trees:
            self._trees[tree.slug] = tree
        logger.info("Loaded %d troubleshoot trees: %s", len(trees), list(self._trees.keys()))

    def find_tree_by_fault(self, fault_code: str) -> Optional[TroubleshootTree]:
        """Find a tree that handles the given fault code."""
        for tree in self._trees.values():
            if fault_code in tree.fault_codes and tree.is_active:
                return tree
        return None

    def find_tree_by_trigger(self, text: str) -> Optional[TroubleshootTree]:
        """Find a tree whose trigger words match the user's text."""
        text_lower = text.lower()
        best: Optional[TroubleshootTree] = None
        best_score = 0
        for tree in self._trees.values():
            if not tree.is_active:
                continue
            score = sum(1 for tw in tree.trigger_words if tw in text_lower)
            if score > best_score:
                best = tree
                best_score = score
        return best

    def list_trees(self) -> list[TroubleshootTree]:
        """Return all active trees."""
        return [t for t in self._trees.values() if t.is_active]

    # ------------------------------------------------------------------
    # Session management
    # ------------------------------------------------------------------

    def get_session(self, user_id: str) -> Optional[TroubleshootSession]:
        """Get active session for a user, or None if expired/missing."""
        session = self._sessions.get(user_id)
        if not session:
            return None
        if time.time() - session.last_activity > SESSION_TTL:
            self._end_session(user_id)
            return None
        return session

    def has_active_session(self, user_id: str) -> bool:
        return self.get_session(user_id) is not None

    def _end_session(self, user_id: str) -> None:
        self._sessions.pop(user_id, None)
        self._save_sessions()

    # ------------------------------------------------------------------
    # Core: start, advance, answer
    # ------------------------------------------------------------------

    def start(
        self,
        user_id: str,
        tree_slug: str,
        fault_code: str | None = None,
        plc_snapshot: dict | None = None,
    ) -> TreeResponse:
        """Start a new troubleshoot session and return the first question."""
        tree = self._trees.get(tree_slug)
        if not tree:
            return TreeResponse(type="not_found", text=f"No troubleshoot tree found: {tree_slug}")

        now = time.time()
        session = TroubleshootSession(
            user_id=user_id,
            tree_slug=tree_slug,
            current_node=tree.root,
            started_at=now,
            last_activity=now,
            fault_code=fault_code,
            plc_snapshot=plc_snapshot or {},
        )
        self._sessions[user_id] = session
        self._save_sessions()

        return self._present_node(session, tree)

    def answer(self, user_id: str, user_input: str) -> TreeResponse:
        """Process a user's answer and advance the session."""
        session = self.get_session(user_id)
        if not session:
            return TreeResponse(type="expired", text="Your troubleshooting session has expired. Type /troubleshoot to start a new one.")

        tree = self._trees.get(session.tree_slug)
        if not tree:
            self._end_session(user_id)
            return TreeResponse(type="not_found", text="Troubleshoot tree no longer available.")

        node = tree.nodes.get(session.current_node)
        if not node:
            self._end_session(user_id)
            return TreeResponse(type="not_found", text="Session state error. Starting over.")

        if node.type == "resolution":
            # Already at a resolution — session is done
            self._end_session(user_id)
            return TreeResponse(type="expired", text="That troubleshooting session is complete. Type /troubleshoot to start a new one.")

        # Match the user's input to an option
        chosen = self._match_option(node, user_input)
        if not chosen:
            # No match — offer LLM handoff
            return TreeResponse(
                type="llm_handoff",
                text=user_input,
                node=node,
                session=session,
                context_for_llm=self._build_llm_context(session, tree, user_input),
            )

        # Record the answer
        session.answers.append({
            "node_id": node.id,
            "question": node.text,
            "answer": chosen.label,
            "ts": time.time(),
        })
        session.last_transition = chosen.transition
        session.current_node = chosen.next
        session.last_activity = time.time()
        self._save_sessions()

        return self._present_node(session, tree)

    def cancel(self, user_id: str) -> None:
        """Cancel an active session."""
        self._end_session(user_id)

    # ------------------------------------------------------------------
    # Node presentation
    # ------------------------------------------------------------------

    def _present_node(self, session: TroubleshootSession, tree: TroubleshootTree) -> TreeResponse:
        """Build a TreeResponse for the current node."""
        node = tree.nodes.get(session.current_node)
        if not node:
            self._end_session(session.user_id)
            return TreeResponse(type="not_found", text="Tree node missing — ending session.")

        # Auto-answer from PLC data if plc_tag is set
        if node.type == "question" and node.plc_tag and session.plc_snapshot:
            auto_val = session.plc_snapshot.get(node.plc_tag)
            if auto_val is not None:
                auto_answer = self._auto_answer_from_plc(node, auto_val)
                if auto_answer:
                    session.answers.append({
                        "node_id": node.id,
                        "question": node.text,
                        "answer": f"[Auto: {auto_answer.label}]",
                        "ts": time.time(),
                    })
                    session.last_transition = auto_answer.transition
                    session.current_node = auto_answer.next
                    session.last_activity = time.time()
                    self._save_sessions()
                    return self._present_node(session, tree)

        if node.type == "resolution":
            # End the session on resolution
            self._end_session(session.user_id)
            if node.llm_handoff:
                return TreeResponse(
                    type="llm_handoff",
                    text=node.text,
                    node=node,
                    session=session,
                    context_for_llm=self._build_llm_context(session, tree),
                )

        return TreeResponse(
            type=node.type,
            text=node.text,
            node=node,
            session=session,
        )

    def _auto_answer_from_plc(self, node: TreeNode, plc_value) -> Optional:
        """Try to auto-select an option based on a PLC tag value."""
        # Boolean PLC tags: True → "Yes", False → "No"
        if isinstance(plc_value, bool):
            target = "yes" if plc_value else "no"
            for opt in node.options:
                if opt.label.lower().startswith(target):
                    return opt
        return None

    # ------------------------------------------------------------------
    # Answer matching
    # ------------------------------------------------------------------

    def _match_option(self, node: TreeNode, user_input: str):
        """Match user input to one of the node's options.

        Accepts: option number ("1", "2"), label text, or partial match.
        Returns the matched TreeOption or None.
        """
        text = user_input.strip()

        # Try numeric match first (most common on Telegram)
        if text.isdigit():
            idx = int(text) - 1
            if 0 <= idx < len(node.options):
                return node.options[idx]

        # Try exact label match (case-insensitive)
        text_lower = text.lower()
        for opt in node.options:
            if opt.label.lower() == text_lower:
                return opt

        # Try partial/fuzzy match — label starts with input or input starts with label
        for opt in node.options:
            label_lower = opt.label.lower()
            if label_lower.startswith(text_lower) or text_lower.startswith(label_lower):
                return opt

        # "yes"/"no" shortcuts
        if text_lower in ("yes", "y", "yeah", "yep", "yup"):
            for opt in node.options:
                if opt.label.lower().startswith("yes"):
                    return opt
        if text_lower in ("no", "n", "nope", "nah"):
            for opt in node.options:
                if opt.label.lower().startswith("no"):
                    return opt

        return None

    # ------------------------------------------------------------------
    # LLM handoff context
    # ------------------------------------------------------------------

    def _build_llm_context(
        self,
        session: TroubleshootSession,
        tree: TroubleshootTree,
        unmatched_input: str = "",
    ) -> dict:
        """Build structured context for LLM handoff."""
        return {
            "tree_title": tree.title,
            "tree_slug": tree.slug,
            "fault_code": session.fault_code,
            "plc_snapshot": session.plc_snapshot,
            "steps_completed": session.answers,
            "current_question": tree.nodes.get(session.current_node, None),
            "unmatched_input": unmatched_input,
            "session_duration_s": time.time() - session.started_at,
        }

    # ------------------------------------------------------------------
    # Session persistence (JSON file)
    # ------------------------------------------------------------------

    def _save_sessions(self) -> None:
        """Persist sessions to JSON file."""
        try:
            data = {}
            for uid, s in self._sessions.items():
                data[uid] = {
                    "user_id": s.user_id,
                    "tree_slug": s.tree_slug,
                    "current_node": s.current_node,
                    "started_at": s.started_at,
                    "last_activity": s.last_activity,
                    "answers": s.answers,
                    "plc_snapshot": s.plc_snapshot,
                    "fault_code": s.fault_code,
                    "last_transition": s.last_transition,
                }
            SESSION_FILE.write_text(json.dumps(data, indent=2))
        except Exception:
            logger.warning("Failed to save troubleshoot sessions", exc_info=True)

    def _load_sessions(self) -> None:
        """Load sessions from JSON file, discarding expired ones."""
        try:
            if not SESSION_FILE.exists():
                return
            data = json.loads(SESSION_FILE.read_text())
            now = time.time()
            for uid, s in data.items():
                if now - s.get("last_activity", 0) < SESSION_TTL:
                    self._sessions[uid] = TroubleshootSession(
                        user_id=s["user_id"],
                        tree_slug=s["tree_slug"],
                        current_node=s["current_node"],
                        started_at=s["started_at"],
                        last_activity=s["last_activity"],
                        answers=s.get("answers", []),
                        plc_snapshot=s.get("plc_snapshot", {}),
                        fault_code=s.get("fault_code"),
                        last_transition=s.get("last_transition", ""),
                    )
            if self._sessions:
                logger.info("Restored %d troubleshoot sessions from disk", len(self._sessions))
        except Exception:
            logger.warning("Failed to load troubleshoot sessions", exc_info=True)
