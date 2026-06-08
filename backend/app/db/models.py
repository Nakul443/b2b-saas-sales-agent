# to convert database design into python classes
# four classes will be created
    # they will inherit from the Base class
    
import datetime
from sqlalchemy import Column, String, Integer, Float, Boolean, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.db.database import Base

# User model
class User(Base):
    __tablename__ = "users"

    # String/Text ID because it's passed from the URL path parameter (e.g., /chat/user_123)
    id = Column(String, primary_key=True, index=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

# cascade="all, delete-orphan" ensures that when DELETE /chat/{user_id}/memory is called,
# dropping this user row will automatically purge all the messages and memory facts instantly
    chat_history = relationship("ChatHistory", back_populates="user", cascade="all, delete-orphan")
    facts = relationship("UserFact", back_populates="user", cascade="all, delete-orphan")


# ChatHistory model
class ChatHistory(Base):
    __tablename__ = "chat_history"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    session_id = Column(String, nullable=False, index=True)
    
    # "role" tracks who is speaking ("user", "assistant", or "system")
    role = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


    user = relationship("User", back_populates="chat_history")
    # One-to-one relationship linking an assistant message directly to its validation
    evaluation = relationship("ResponseEvaluation", back_populates="chat_message", uselist=False, cascade="all, delete-orphan")

# UserFact Model
# basically "sticky notes" about a user that the agent can refer to
class UserFact(Base):
    __tablename__ = "user_facts"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    # facts (e.g., "Interested in Starter plan")
    fact = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    user = relationship("User", back_populates="facts")


# ResponseEvaluation Model
class ResponseEvaluation(Base):
    __tablename__ = "response_evaluations"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    # linked directly to the specific assistant message row in chat_history
    chat_history_id = Column(Integer, ForeignKey("chat_history.id", ondelete="CASCADE"), nullable=False, unique=True)
    
    # Specific metric slots required by the assignment evaluation matrix
    groundedness = Column(Float, nullable=False)
    relevance = Column(Float, nullable=False)
    confidence = Column(Float, nullable=False)
    flagged = Column(Boolean, default=False)
    reasoning = Column(Text, nullable=True)
    
    # Storing which tools were called as a plain comma-separated text string
    # (e.g., "search_catalog,get_user_memory")
    tools_called = Column(String, nullable=True)

    chat_message = relationship("ChatHistory", back_populates="evaluation")