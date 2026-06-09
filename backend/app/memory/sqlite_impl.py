# class that hooks up the SQLAlchemy models to save and retrieve data
# from the SQLite database file (sales_agent.db in this case)

from typing import List, Optional
from sqlalchemy.orm import Session
from app.memory.interface import BaseMemory
from app.db.models import User, ChatHistory, UserFact

class SQLiteMemory(BaseMemory):
    """
    Concrete implementation of the BaseMemory interface 
    handling persistence inside a local SQLite file via SQLAlchemy.
    """

    # these are the actual worker for the functions mentioned in the app/memory/base.py file

    def get_chat_history(self, db: Session, user_id: str, session_id: Optional[str] = None) -> List[ChatHistory]:
        """Queries the database for historical conversation turns."""
        query = db.query(ChatHistory).filter(ChatHistory.user_id == user_id)
        if session_id:
            query = query.filter(ChatHistory.session_id == session_id)
        return query.order_by(ChatHistory.created_at.asc()).all()

    def add_chat_message(self, db: Session, user_id: str, session_id: str, role: str, content: str) -> ChatHistory:
        """Appends a new conversation message log entry to the DB."""
        # Ensure the parent User entity exists first due to foreign key constraints
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            user = User(id=user_id)
            db.add(user)
            db.flush()  # Places user in transaction state without a full commit yet

        db_message = ChatHistory(
            user_id=user_id,
            session_id=session_id,
            role=role,
            content=content
        )
        db.add(db_message)
        db.commit()
        db.refresh(db_message)
        return db_message

    def get_user_facts(self, db: Session, user_id: str) -> List[UserFact]:
        """Fetches stored profile summary facts (long-term memory insights)."""
        return db.query(UserFact).filter(UserFact.user_id == user_id).all()

    def add_user_fact(self, db: Session, user_id: str, fact: str) -> UserFact:
        """Saves a newly extracted key profile attribute about the user."""
        db_fact = UserFact(user_id=user_id, fact=fact)
        db.add(db_fact)
        db.commit()
        db.refresh(db_fact)
        return db_fact

    def wipe_user_memory(self, db: Session, user_id: str) -> bool:
        """Performs a cascading delete of the user record and its associated data."""
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            db.delete(user)
            db.commit()
            return True
        return False
