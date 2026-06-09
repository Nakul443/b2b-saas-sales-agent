import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.db.database import get_db
from app.models.schemas import ChatMessageRequest, ChatAgentResponse, ChatHistoryItem
from app.memory.sqlite_impl import SQLiteMemory
from app.services.chat_service import ChatService
from app.tools.catalog_tool import search_catalog
import json


router = APIRouter()

memory_backend = SQLiteMemory()

chat_service = ChatService(memory_backend=memory_backend)


@router.post("/chat/{user_id}", response_model=ChatAgentResponse, status_code=status.HTTP_200_OK)
def post_chat_message(user_id: str, payload: ChatMessageRequest, db: Session = Depends(get_db)):
    """
    Primary transactional gateway endpoint processing conversational multi-turn dialogue.
    Takes a message, passes it to the AI orchestration services, and logs details.
    """
    try:
        # take from input or dynamically generate a session tracker UUID
        session_id = payload.session_id if payload.session_id else str(uuid.uuid4())
        
        # Route processing immediately to our core isolated service tier
        response_data = chat_service.process_chat(
            db=db,
            user_id=user_id,
            session_id=session_id,
            message_content=payload.message
        )
        return response_data
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred within the orchestration handler: {str(e)}"
        )


@router.get("/chat/{user_id}/history", status_code=status.HTTP_200_OK)
def get_user_chat_history(user_id: str, db: Session = Depends(get_db)):
    """
    Returns the complete message log history across all historical sessions for audit.
    """
    raw_history = memory_backend.get_chat_history(db=db, user_id=user_id)
    
    # formatting the db objects into a clean, flat list for the web payload response
    formatted_history = []
    for entry in raw_history:
        formatted_history.append({
            "session_id": entry.session_id,
            "role": entry.role,
            "content": entry.content,
            "created_at": entry.created_at.isoformat() if entry.created_at else None
        })
    return {"user_id": user_id, "history": formatted_history}


@router.delete("/chat/{user_id}/memory", status_code=status.HTTP_200_OK)
def delete_user_memory(user_id: str, db: Session = Depends(get_db)):
    """
    Executes a permanent cascade delete hard purge against all data associated with a user.
    """
    success = memory_backend.wipe_user_memory(db=db, user_id=user_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No recorded entries found on disk matching User ID: {user_id}"
        )
    return {"status": "success", "message": f"All data files and relational rows for User {user_id} purged successfully."}


@router.get("/catalog", status_code=status.HTTP_200_OK)
def get_product_catalog():
    """
    Exposes the raw foundational SaaS product pricing catalog configuration rules list.
    """
    # call the helper tool function with an empty query to dump all entries
    catalog_string = search_catalog(query="")
    return json.loads(catalog_string)


@router.get("/health", status_code=status.HTTP_200_OK)
def get_service_health():
    """
    Automated service readiness platform health monitor.
    """
    return {"status": "healthy", "environment": "production", "version": "2026.1.0"}