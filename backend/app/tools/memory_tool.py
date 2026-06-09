# calls sqlite_impl.py memory layer to retrieve stored facts about the user

from sqlalchemy.orm import Session
from app.memory.base import BaseMemory

def get_user_memory(user_id: str, db: Session, memory_backend: BaseMemory) -> str:
    """
    Queries the database using the abstracted memory backend to retrieve 
    long-term extracted profile facts about a specific user.

    Args:
        user_id: The unique identifier string of the client.
        db: The active SQLAlchemy transaction session.
        memory_backend: An instance conforming to the BaseMemory interface contract.
    Returns:
        A formatted clear-text string layout listing known atomic user profile attributes.
    """
    try:
        # Utilize the abstracted contract layer directly (swappable implementation)
        facts = memory_backend.get_user_facts(db, user_id)
        
        if not facts:
            return f"No long-term memory facts are currently recorded for User ID: {user_id}."
        
        # Build a structured text list for clean LLM prompt context ingestion
        fact_lines = [f"- {item.fact}" for item in facts]
        return f"Known factual profile attributes for User ID {user_id}:\n" + "\n".join(fact_lines)
        
    except Exception as e:
        return f"Error retrieving long-term user memory tracking attributes: {str(e)}"