# basically any file that claims to be a memory database for this AI agent,
# must have these exact 5 functions below

from abc import ABC, abstractmethod
from typing import List, Optional
from sqlalchemy.orm import Session
from app.db.models import ChatHistory, UserFact

# ABS (abstract base class)
# tells python that this class cannot be instantiated directly
# the class only acts as a blueprint for other classes to follow

class BaseMemory(ABC):
    """
    Abstract Base Class acting as the mandatory structural interface 
    for all memory provider implementations (SQLite, Postgres, Mem0, etc.)
    """
    
    # the API routes and agent loop will rely on these methods below

    @abstractmethod
    def get_chat_history(self, db: Session, user_id: str, session_id: Optional[str] = None) -> List[ChatHistory]:
        """Retrieve full or session-specific message history logs for a user."""
        pass

    @abstractmethod
    def add_chat_message(self, db: Session, user_id: str, session_id: str, role: str, content: str) -> ChatHistory:
        """Append a conversational turn (user or assistant) directly to the transaction log."""
        pass

    @abstractmethod
    def get_user_facts(self, db: Session, user_id: str) -> List[UserFact]:
        """Extract condensed atomic facts (long-term memory profile) for context injection."""
        pass

    @abstractmethod
    def add_user_fact(self, db: Session, user_id: str, fact: str) -> UserFact:
        """Store a newly extracted long-term profile attribute about the user."""
        pass

    @abstractmethod
    def wipe_user_memory(self, db: Session, user_id: str) -> bool:
        """Execute a hard delete of all user records, message logs, and memory facts."""
        pass