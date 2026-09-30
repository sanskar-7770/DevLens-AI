"""Bounded process-local sessions: no database or long-term memory."""
import json
import time
from dataclasses import dataclass, field
from threading import Lock
from uuid import uuid4
from fastapi import HTTPException

MAX_SESSIONS = 100
MAX_TURNS = 3
TTL_SECONDS = 3600

@dataclass
class Conversation:
    dataset_id: str
    turns: list = field(default_factory=list)
    touched: float = field(default_factory=time.monotonic)
    busy: bool = False

class ConversationStore:
    def __init__(self):
        self.sessions = {}
        self.lock = Lock()

    def acquire(self, dataset_id, session_id=None):
        with self.lock:
            now = time.monotonic()
            for key in list(self.sessions):
                session = self.sessions[key]
                if not session.busy and now-session.touched > TTL_SECONDS:
                    del self.sessions[key]
            if session_id:
                session = self.sessions.get(session_id)
                if not session or session.dataset_id != dataset_id:
                    raise HTTPException(409, "Conversation expired or belongs to another dataset. Start a new conversation.")
                if session.busy:
                    raise HTTPException(409, "This conversation is already analyzing a question.")
            else:
                if len(self.sessions) >= MAX_SESSIONS:
                    idle = [k for k, v in self.sessions.items() if not v.busy]
                    if not idle:
                        raise HTTPException(429, "All analysis sessions are busy. Try again shortly.")
                    del self.sessions[min(idle, key=lambda k: self.sessions[k].touched)]
                session_id = str(uuid4())
                session = Conversation(dataset_id)
                self.sessions[session_id] = session
            session.busy = True
            session.touched = now
            return session_id, list(session.turns)

    def release(self, session_id, turn=None):
        with self.lock:
            session = self.sessions.get(session_id)
            if session is None:
                return
            if turn:
                session.turns.append(turn)
                session.turns = session.turns[-MAX_TURNS:]
                while len(json.dumps(session.turns)) > 24_000:
                    session.turns.pop(0)
            session.busy = False
            session.touched = time.monotonic()

conversations = ConversationStore()
