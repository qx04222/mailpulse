"""
In-memory chat context store for Lark Q&A conversations.
Per-chat history with auto-trim and TTL cleanup.
"""
import time
from typing import Dict, List


class ChatContextStore:
    """Stores per-chat conversation history, keyed by chat_id or open_id."""

    def __init__(self, max_turns: int = 6, ttl_seconds: int = 3600):
        self._store: Dict[str, List[dict]] = {}
        self._timestamps: Dict[str, float] = {}
        self._max_turns = max_turns
        self._ttl = ttl_seconds

    def get(self, chat_id: str) -> List[dict]:
        self._cleanup_expired()
        return self._store.get(chat_id, [])

    def append(self, chat_id: str, role: str, content: str):
        if chat_id not in self._store:
            self._store[chat_id] = []
        self._store[chat_id].append({"role": role, "content": content})
        self._store[chat_id] = self._store[chat_id][-self._max_turns:]
        self._timestamps[chat_id] = time.time()

    def _cleanup_expired(self):
        now = time.time()
        expired = [k for k, t in self._timestamps.items() if now - t > self._ttl]
        for k in expired:
            self._store.pop(k, None)
            self._timestamps.pop(k, None)


# Global singleton
chat_contexts = ChatContextStore()
