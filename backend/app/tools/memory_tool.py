# calls sqlite_impl.py memory layer to retrieve stored facts about the user

# Memory Tool Handler: Interface layer executing relational database scans
# to format historic profile characteristics into strings for the model.

from sqlalchemy.orm import Session
from app.memory.base import BaseMemory

def get_user_memory(user_id: str, db: Session, memory_backend: BaseMemory) -> str:
    """
    Queries the database using the abstracted memory backend to retrieve 
    long-term extracted profile facts about a specific user.
    """
    try:
        facts = memory_backend.get_user_facts(db, user_id)
        
        if not facts:
            return f"No long-term memory facts are currently recorded for User ID: {user_id}."
        
        fact_lines = [f"- {item.fact}" for item in facts]
        return f"Known factual profile attributes for User ID {user_id}:\n" + "\n".join(fact_lines)
        
    except Exception as e:
        return f"Error retrieving long-term user memory tracking attributes: {str(e)}"