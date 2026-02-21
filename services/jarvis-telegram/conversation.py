# Restored from: feature/factorylm-remote:infrastructure/bot/conversation_manager.py
"""
Conversation Manager for Telegram Bot

Manages multi-turn conversations with context awareness, enabling the bot to:
- Remember previous messages
- Reference past topics
- Maintain conversation state
- Track equipment mentions across messages
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict


@dataclass
class Message:
    """Single message in conversation."""
    role: str  # "user" or "assistant"
    content: str
    timestamp: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


@dataclass
class MessageHistory:
    """Collection of messages."""
    messages: List[Message]

    def __init__(self):
        self.messages = []

    def get_messages(self, limit: Optional[int] = None) -> List[Message]:
        """Get messages with optional limit."""
        if limit:
            return self.messages[-limit:]
        return self.messages


@dataclass
class Session:
    """Conversation session."""
    user_id: str
    session_id: Optional[str] = None
    history: Optional[MessageHistory] = None
    metadata: Optional[Dict[str, Any]] = None
    created_at: Optional[datetime] = None
    last_active: Optional[datetime] = None

    # Puppeteer session state
    last_diagnosis: Optional[str] = None
    last_photo: Optional[bytes] = None
    last_equipment: Optional[str] = None
    diagnosis_history: Optional[List[Dict[str, Any]]] = None

    def __post_init__(self):
        if self.session_id is None:
            self.session_id = f"session_{self.user_id}_{int(datetime.now().timestamp())}"
        if self.history is None:
            self.history = MessageHistory()
        if self.metadata is None:
            self.metadata = {}
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.last_active is None:
            self.last_active = datetime.now()
        if self.diagnosis_history is None:
            self.diagnosis_history = []

    def add_user_message(self, content: str, metadata: Optional[Dict] = None) -> Message:
        """Add user message to session."""
        msg = Message(role="user", content=content, metadata=metadata)
        self.history.messages.append(msg)
        self.last_active = datetime.now()
        return msg

    def add_assistant_message(self, content: str, metadata: Optional[Dict] = None) -> Message:
        """Add assistant message to session."""
        msg = Message(role="assistant", content=content, metadata=metadata)
        self.history.messages.append(msg)
        self.last_active = datetime.now()
        return msg

    def add_diagnosis(self, diagnosis: str) -> None:
        """Store a diagnosis result in session history."""
        self.last_diagnosis = diagnosis
        self.diagnosis_history.append({
            "type": "diagnosis",
            "timestamp": datetime.now().isoformat(),
            "result": diagnosis[:200] + "..." if len(diagnosis) > 200 else diagnosis,
        })
        # Keep history bounded
        if len(self.diagnosis_history) > 20:
            self.diagnosis_history = self.diagnosis_history[-20:]


@dataclass
class ConversationContext:
    """Extracted context from conversation history."""
    last_topic: Optional[str] = None
    last_equipment_type: Optional[str] = None
    last_intent_type: Optional[str] = None
    mentioned_equipment: Optional[List[str]] = None
    unresolved_issues: Optional[List[str]] = None
    follow_up_count: int = 0

    def __post_init__(self):
        if self.mentioned_equipment is None:
            self.mentioned_equipment = []
        if self.unresolved_issues is None:
            self.unresolved_issues = []

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ConversationContext":
        return cls(**data)


class ConversationManager:
    """
    Manages conversation sessions for Telegram users.

    Features:
    - Session persistence across bot restarts (in-memory, DB optional)
    - Conversation history with context window
    - Context extraction for intelligent responses
    - Automatic session cleanup
    """

    def __init__(self, context_window_size: int = 10):
        self.active_sessions: Dict[str, Session] = {}
        self.context_window_size = context_window_size

    def get_or_create_session(
        self, user_id: str, telegram_username: Optional[str] = None
    ) -> Session:
        """Get existing session or create new one for user."""
        if user_id in self.active_sessions:
            session = self.active_sessions[user_id]
            session.last_active = datetime.now()
            return session

        session = Session(
            user_id=user_id,
            metadata={
                "telegram_username": telegram_username,
                "created_via": "telegram_bot",
                "platform": "telegram",
            },
        )
        self.active_sessions[user_id] = session
        return session

    def add_user_message(
        self, session: Session, content: str, metadata: Optional[Dict[str, Any]] = None
    ) -> Message:
        """Add user message and update context."""
        msg = session.add_user_message(content, metadata)
        self._update_context(session)
        return msg

    def add_bot_message(
        self, session: Session, content: str, metadata: Optional[Dict[str, Any]] = None
    ) -> Message:
        """Add bot response message."""
        return session.add_assistant_message(content, metadata)

    def get_context(self, session: Session) -> ConversationContext:
        """Extract structured context from conversation history."""
        recent_messages = session.history.get_messages(limit=self.context_window_size)

        if not recent_messages:
            return ConversationContext()

        context = ConversationContext()

        equipment_keywords = [
            "motor", "vfd", "plc", "conveyor", "pump", "valve",
            "sensor", "drive", "hmi", "relay", "breaker", "transformer",
        ]

        for msg in recent_messages:
            if msg.role == "user":
                for keyword in equipment_keywords:
                    if keyword in msg.content.lower() and keyword not in context.mentioned_equipment:
                        context.mentioned_equipment.append(keyword)

                follow_up_phrases = ["what about", "tell me more", "can you explain", "how do i", "also"]
                if any(phrase in msg.content.lower() for phrase in follow_up_phrases):
                    context.follow_up_count += 1

            if msg.metadata:
                if "intent_type" in msg.metadata:
                    context.last_intent_type = msg.metadata["intent_type"]
                if "equipment_type" in msg.metadata:
                    context.last_equipment_type = msg.metadata["equipment_type"]
                if "topic" in msg.metadata:
                    context.last_topic = msg.metadata["topic"]

        last_user_msgs = [m for m in recent_messages if m.role == "user"]
        if last_user_msgs:
            words = last_user_msgs[-1].content.lower().split()[:5]
            context.last_topic = " ".join(words)

        return context

    def get_context_summary(self, session: Session) -> str:
        """Generate natural language summary for LLM context injection."""
        context = self.get_context(session)
        recent_messages = session.history.get_messages(limit=5)

        parts = []

        total = len(session.history.messages)
        if total > 0:
            parts.append(f"Conversation has {total} messages.")

        if context.last_topic:
            parts.append(f"User is asking about: {context.last_topic}")

        if context.mentioned_equipment:
            parts.append(f"Equipment mentioned: {', '.join(context.mentioned_equipment)}")

        if context.follow_up_count > 0:
            parts.append(f"This is a follow-up question (count: {context.follow_up_count})")

        if recent_messages:
            parts.append("\nRecent exchange:")
            for msg in recent_messages[-3:]:
                role = "User" if msg.role == "user" else "Bot"
                preview = msg.content[:80] + "..." if len(msg.content) > 80 else msg.content
                parts.append(f"{role}: {preview}")

        return "\n".join(parts) if parts else "No previous conversation context."

    def cleanup_old_sessions(self, hours: int = 24) -> int:
        """Remove sessions older than N hours. Returns count removed."""
        cutoff = datetime.now() - timedelta(hours=hours)
        expired = [
            uid for uid, session in self.active_sessions.items()
            if session.last_active < cutoff
        ]
        for uid in expired:
            del self.active_sessions[uid]
        return len(expired)

    def _update_context(self, session: Session) -> None:
        """Update session metadata with current context."""
        context = self.get_context(session)
        session.metadata["context"] = context.to_dict()
        session.metadata["last_update"] = datetime.now().isoformat()
