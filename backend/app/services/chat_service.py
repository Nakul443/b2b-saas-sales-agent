# fetches previous context from the database with the help of memory tools
# then calls the eval service to get a self-evaluation score for the assistant's response

# Chat Workflow Manager: Coordinates database logging, context assembly, 
# and links the web api routes to the isolated agent loop brain.

import os
from sqlalchemy.orm import Session
from typing import Dict, Any

from app.memory.base import BaseMemory
from app.agents.agent_loop import SalesAgentLoop
from app.services.eval_service import EvalService
from app.tools.catalog_tool import search_catalog
from app.tools.memory_tool import get_user_memory
from app.db.models import ResponseEvaluation

class ChatService:
    """
    Orchestrates the multi-turn agent conversation loop: fetches context,
    manages tool calling side-effects, handles fact extraction, and saves logs.
    """

    def __init__(self, memory_backend: BaseMemory):
        self.memory = memory_backend
        self.agent = SalesAgentLoop()
        self.eval_service = EvalService()

    def process_chat(self, db: Session, user_id: str, session_id: str, message_content: str) -> Dict[str, Any]:
        """
        Main orchestration execution loop processing a singular user conversational turn.
        """
        # Commit raw incoming user query to history table
        self.memory.add_chat_message(db, user_id=user_id, session_id=session_id, role="user", content=message_content)

        # Pull historical messages and profile traits from storage
        historical_messages = self.memory.get_chat_history(db, user_id=user_id)
        current_long_term_memory = get_user_memory(user_id=user_id, db=db, memory_backend=self.memory)

        # Convert database records into a simple format the agent expects
        formatted_history = [{"role": msg.role, "content": msg.content} for msg in historical_messages]

        system_instruction = (
            "You are an expert enterprise B2B sales representative for SaaSify Metrics OS. "
            "Your objective is to qualify leads, guide them through our product tiers, and gracefully close sales.\n\n"
            "CRITICAL OPERATIONAL RULES:\n"
            "1. ALWAYS query the product catalog using the `search_catalog` tool when asked about features, pricing, limits, or plans. Do NOT guess or extrapolate.\n"
            "2. Review the known user facts context provided. Use this to remember details across sessions without asking the user to repeat themselves.\n"
            "3. If you learn something brand new and structurally important about the user (e.g., their team size, budget constraints, specific technical needs like SSO), explicitly summarize it as a single clear sentence starting exactly with '[EXTRACTED_FACT]: ' at the absolute end of your response text so our systems can capture it.\n"
            "4. Maintain a highly professional, consultative tone at all times."
        )

        cleaned_response_text, tools_called_tracking, new_fact = self.agent.run(
            system_instruction=system_instruction,
            history_messages=formatted_history,
            user_id=user_id,
            db=db,
            memory_backend=self.memory
        )

        if new_fact:
            self.memory.add_user_fact(db, user_id=user_id, fact=new_fact)
            if "get_user_memory" not in tools_called_tracking:
                tools_called_tracking.append("get_user_memory")

        db_message = self.memory.add_chat_message(
            db, user_id=user_id, session_id=session_id, role="assistant", content=cleaned_response_text
        )

        # Pull full pricing file text to feed into accuracy auditing evaluation service
        full_catalog_context = search_catalog(query="")
        eval_metrics = self.eval_service.evaluate_response(
            user_message=message_content,
            agent_response=cleaned_response_text,
            catalog_context=full_catalog_context,
            memory_context=current_long_term_memory
        )

        # Record structured quality scoring data directly to relational table records
        db_eval = ResponseEvaluation(
            chat_history_id=db_message.id,
            groundedness=eval_metrics.groundedness,
            relevance=eval_metrics.relevance,
            confidence=eval_metrics.confidence,
            flagged=eval_metrics.flagged,
            reasoning=eval_metrics.reasoning,
            tools_called=",".join(tools_called_tracking) if tools_called_tracking else ""
        )
        db.add(db_eval)
        db.commit()

        # Emit audit warning log entry if confidence criteria fails parameter limits
        if eval_metrics.flagged:
            print(f"[ALERT - AUDIT COMPLIANCE] Message ID {db_message.id} flagged. Reasoning: {eval_metrics.reasoning}")

        # Assemble and output matching endpoint response block payload schema
        return {
            "response": cleaned_response_text,
            "eval": {
                "groundedness": eval_metrics.groundedness,
                "relevance": eval_metrics.relevance,
                "confidence": eval_metrics.confidence,
                "flagged": eval_metrics.flagged,
                "reasoning": eval_metrics.reasoning
            },
            "tools_called": tools_called_tracking,
            "session_id": session_id
        }