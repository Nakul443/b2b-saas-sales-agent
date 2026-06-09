# fetches previous context from the database with the help of memory tools
# then calls the eval service to get a self-evaluation score for the assistant's response

import os
import json
from typing import List, Dict, Any, Optional
from openai import OpenAI
from sqlalchemy.orm import Session

from app.memory.interface import BaseMemory
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
        self.eval_service = EvalService()
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    def process_chat(self, db: Session, user_id: str, session_id: str, message_content: str) -> Dict[str, Any]:
        """
        Main orchestration execution loop processing a singular user conversational turn.
        """
        # 1. Store the incoming message directly in the persistent chat history log
        self.memory.add_chat_message(db, user_id=user_id, session_id=session_id, role="user", content=message_content)

        # 2. Extract stateful contexts from backends to supply to the prompt layer
        historical_messages = self.memory.get_chat_history(db, user_id=user_id)
        current_long_term_memory = get_user_memory(user_id=user_id, db=db, memory_backend=self.memory)

        # 3. Construct the comprehensive conversational context array
        system_instruction = (
            "You are an expert enterprise B2B sales representative for SaaSify Metrics OS. "
            "Your objective is to qualify leads, guide them through our product tiers, and gracefully close sales.\n\n"
            "CRITICAL OPERATIONAL RULES:\n"
            "1. ALWAYS query the product catalog using the `search_catalog` tool when asked about features, pricing, limits, or plans. Do NOT guess or extrapolate.\n"
            "2. Review the known user facts context provided. Use this to remember details across sessions without asking the user to repeat themselves.\n"
            "3. If you learn something brand new and structurally important about the user (e.g., their team size, budget constraints, specific technical needs like SSO), explicitly summarize it as a single clear sentence starting exactly with '[EXTRACTED_FACT]: ' at the absolute end of your response text so our systems can capture it.\n"
            "4. Maintain a highly professional, consultative tone at all times."
        )

        messages = [{"role": "system", "content": system_instruction}]
        
        # Append all true historical context turns to prevent state amnesia
        for msg in historical_messages:
            messages.append({"role": msg.role, "content": msg.content})

        # Define the exact tool configuration list the OpenAI engine can select from
        tools_configuration = [
            {
                "type": "function",
                "function": {
                    "name": "search_catalog",
                    "description": "Performs a real keyword search over the product pricing and feature rules catalog configuration file.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "The specific feature or plan name string to scan for."}
                        },
                        "required": ["query"]
                    }
                }
            }
        ]

        # 4. Initiate the primary OpenAI Call loop
        response = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            tools=tools_configuration,
            tool_choice="auto"
        )

        assistant_message = response.choices[0].message
        tools_called_tracking = []

        # 5. Handle automated tool execution if called by the LLM
        if assistant_message.tool_calls:
            messages.append(assistant_message)
            
            for tool_call in assistant_message.tool_calls:
                function_name = tool_call.function.name
                function_args = json.loads(tool_call.function.arguments)
                tools_called_tracking.append(function_name)

                if function_name == "search_catalog":
                    # Execute real tool computation
                    tool_output = search_catalog(query=function_args.get("query"))
                    
                    messages.append({
                        "tool_call_id": tool_call.id,
                        "role": "tool",
                        "name": function_name,
                        "content": tool_output
                    })

            # Run a second secondary call to allow the LLM to absorb the tool data and speak
            second_response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages
            )
            raw_response_text = second_response.choices[0].message.content
        else:
            raw_response_text = assistant_message.content

        # 6. Post-processing: Isolate any background profile facts to update long-term storage
        cleaned_response_text = raw_response_text
        if "[EXTRACTED_FACT]:" in raw_response_text:
            parts = raw_response_text.split("[EXTRACTED_FACT]:")
            cleaned_response_text = parts[0].strip()
            new_fact = parts[1].strip()
            if new_fact:
                # Commit fact to persistent db layer separate from history text stream
                self.memory.add_user_fact(db, user_id=user_id, fact=new_fact)
                # Track that memory tool logic was implicitly applied
                if "get_user_memory" not in tools_called_tracking:
                    tools_called_tracking.append("get_user_memory")

        # 7. Commit the cleaned assistant chat text turn to persistent logs
        db_message = self.memory.add_chat_message(
            db, user_id=user_id, session_id=session_id, role="assistant", content=cleaned_response_text
        )

        # 8. Execute the self-evaluation scoring run against the context state metrics
        eval_metrics = self.eval_service.evaluate_response(
            user_message=message_content,
            agent_response=cleaned_response_text,
            catalog_context=search_catalog(query=""),  # Fetches the structural context block
            memory_context=current_long_term_memory
        )

        # 9. Store evaluation properties to the relational persistence layer
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

        # Bonus constraint handler: Log a distinct system tracking alert if flagged for review
        if eval_metrics.flagged:
            print(f"[ALERT - AUDIT COMPLIANCE] Message ID {db_message.id} flagged. Reasoning: {eval_metrics.reasoning}")

        # 10. Output the perfect structural payload layout required by the client models
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