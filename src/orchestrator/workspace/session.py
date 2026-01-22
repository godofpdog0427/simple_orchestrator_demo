"""Session management for workspace continuity.

This module provides session metadata management, allowing users to:
- Create named sessions
- Resume previous sessions
- List and manage sessions

Phase 8: Session Memory
"""

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class SessionInfo:
    """Session metadata for registry."""

    id: str                                          # UUID
    name: str                                        # User-friendly name
    description: str = ""                            # Optional description
    created_at: datetime = field(default_factory=datetime.now)
    last_accessed: datetime = field(default_factory=datetime.now)
    message_count: int = 0                           # Cached for display
    task_count: int = 0                              # Cached for display

    def to_dict(self) -> dict:
        """Convert to JSON-serializable dict."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "created_at": self.created_at.isoformat(),
            "last_accessed": self.last_accessed.isoformat(),
            "message_count": self.message_count,
            "task_count": self.task_count,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SessionInfo":
        """Create from dict."""
        return cls(
            id=data["id"],
            name=data["name"],
            description=data.get("description", ""),
            created_at=datetime.fromisoformat(data["created_at"]),
            last_accessed=datetime.fromisoformat(data["last_accessed"]),
            message_count=data.get("message_count", 0),
            task_count=data.get("task_count", 0),
        )


class SessionRegistry:
    """Manages session metadata and lookup.

    The registry stores lightweight metadata about sessions, while
    the actual conversation data is stored in WorkspaceState files.
    """

    def __init__(self, registry_file: str = ".orchestrator/sessions.json"):
        """
        Initialize session registry.

        Args:
            registry_file: Path to registry JSON file
        """
        self.registry_file = Path(registry_file)
        self._sessions: dict[str, SessionInfo] = {}  # id -> SessionInfo
        self._active_session_id: Optional[str] = None
        self._load()

    def _load(self) -> None:
        """Load registry from disk."""
        if self.registry_file.exists():
            try:
                with open(self.registry_file) as f:
                    data = json.load(f)

                self._sessions = {
                    sid: SessionInfo.from_dict(info)
                    for sid, info in data.get("sessions", {}).items()
                }
                self._active_session_id = data.get("active_session_id")
                logger.debug(f"Loaded {len(self._sessions)} sessions from registry")
            except Exception as e:
                logger.warning(f"Failed to load session registry: {e}")
                self._sessions = {}
                self._active_session_id = None
        else:
            logger.debug("No existing session registry found")

    def _save(self) -> None:
        """Persist registry to disk."""
        # Ensure directory exists
        self.registry_file.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "sessions": {sid: info.to_dict() for sid, info in self._sessions.items()},
            "active_session_id": self._active_session_id,
        }

        with open(self.registry_file, "w") as f:
            json.dump(data, f, indent=2)

        logger.debug(f"Saved {len(self._sessions)} sessions to registry")

    def create_session(
        self,
        name: str,
        description: str = "",
        session_id: Optional[str] = None,
    ) -> SessionInfo:
        """
        Create new session with unique ID.

        Args:
            name: User-friendly session name
            description: Optional description
            session_id: Optional specific ID (for backward compatibility)

        Returns:
            Created SessionInfo
        """
        if session_id is None:
            session_id = str(uuid.uuid4())

        session = SessionInfo(
            id=session_id,
            name=name,
            description=description,
            created_at=datetime.now(),
            last_accessed=datetime.now(),
        )

        self._sessions[session.id] = session
        self._active_session_id = session.id
        self._save()

        logger.info(f"Created new session: {session.name} ({session.id[:8]}...)")
        return session

    def get_session(self, session_id: str) -> Optional[SessionInfo]:
        """
        Get session by ID.

        Args:
            session_id: Session UUID

        Returns:
            SessionInfo if found, None otherwise
        """
        return self._sessions.get(session_id)

    def get_session_by_name(self, name: str) -> Optional[SessionInfo]:
        """
        Get session by name (case-insensitive).

        Args:
            name: Session name

        Returns:
            SessionInfo if found, None otherwise
        """
        name_lower = name.lower()
        for session in self._sessions.values():
            if session.name.lower() == name_lower:
                return session
        return None

    def get_active_session(self) -> Optional[SessionInfo]:
        """
        Get the most recently active session.

        Returns:
            SessionInfo if exists, None otherwise
        """
        if self._active_session_id:
            return self._sessions.get(self._active_session_id)
        return None

    def list_sessions(self, limit: int = 20) -> list[SessionInfo]:
        """
        List sessions sorted by last_accessed (most recent first).

        Args:
            limit: Maximum number of sessions to return

        Returns:
            List of SessionInfo
        """
        return sorted(
            self._sessions.values(),
            key=lambda s: s.last_accessed,
            reverse=True
        )[:limit]

    def update_session_stats(
        self,
        session_id: str,
        message_count: int,
        task_count: int,
    ) -> None:
        """
        Update session statistics from workspace.

        Args:
            session_id: Session UUID
            message_count: Number of messages in workspace
            task_count: Number of task summaries
        """
        if session := self._sessions.get(session_id):
            session.last_accessed = datetime.now()
            session.message_count = message_count
            session.task_count = task_count
            self._active_session_id = session_id
            self._save()
            logger.debug(f"Updated session stats: {session_id[:8]}... (msgs={message_count}, tasks={task_count})")

    def touch_session(self, session_id: str) -> None:
        """
        Update last_accessed time for session.

        Args:
            session_id: Session UUID
        """
        if session := self._sessions.get(session_id):
            session.last_accessed = datetime.now()
            self._active_session_id = session_id
            self._save()

    def delete_session(self, session_id: str) -> bool:
        """
        Delete session from registry.

        Note: This only removes the registry entry. The workspace file
        should be deleted separately by WorkspaceManager.

        Args:
            session_id: Session UUID

        Returns:
            True if deleted, False if not found
        """
        if session_id in self._sessions:
            session_name = self._sessions[session_id].name
            del self._sessions[session_id]

            # Clear active session if it was deleted
            if self._active_session_id == session_id:
                self._active_session_id = None

            self._save()
            logger.info(f"Deleted session: {session_name} ({session_id[:8]}...)")
            return True
        return False

    def rename_session(self, session_id: str, new_name: str) -> bool:
        """
        Rename existing session.

        Args:
            session_id: Session UUID
            new_name: New session name

        Returns:
            True if renamed, False if not found
        """
        if session := self._sessions.get(session_id):
            old_name = session.name
            session.name = new_name
            self._save()
            logger.info(f"Renamed session: '{old_name}' -> '{new_name}'")
            return True
        return False

    def session_exists(self, session_id: str) -> bool:
        """
        Check if session exists.

        Args:
            session_id: Session UUID

        Returns:
            True if exists
        """
        return session_id in self._sessions

    @property
    def count(self) -> int:
        """Number of sessions in registry."""
        return len(self._sessions)
