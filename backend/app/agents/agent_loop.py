# "brain" of the AI agent loop, responsible for managing the conversation flow and tool execution

# looks at the messaages, and takes the tools from the tools folder
# and runs them, then feeds the results back in and gets a final answer

# Core Brain Loop: handles multi-turn conversations with OpenAI
# declares available system tools and executes them when requested by the model

import os
import json
from openai import OpenAI
from app.tools.catalog_tool import search_catalog
from app.tools.memory_tool import get_user_memory

class SalesAgentLoop:
    """
    Manages the core LLM conversation choices and function tool execution runs.
    """
    def __init__(self):
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    def run(self, system_instruction: str, history_messages: list, user_id: str, db: any, memory_backend: any) -> tuple:
        """
        Runs the message loop. Returns (cleaned_response_text, tools_called_list, newly_extracted_fact_string)
        """
        messages = [{"role": "system", "content": system_instruction}] + history_messages

        tools_config = [
            {
                "type": "function",
                "function": {
                    "name": "search_catalog",
                    "description": "Searches the product pricing and feature catalog rules file.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "The plan name or feature to check."}
                        },
                        "required": ["query"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_user_memory",
                    "description": "Retrieves saved facts and profile attributes about this specific customer.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "user_id": {"type": "string", "description": "The unique identifier of the user."}
                        },
                        "required": ["user_id"]
                    }
                }
            }
        ]

        response = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            tools=tools_config,
            tool_choice="auto"
        )

        assistant_message = response.choices[0].message
        tools_called = []

        if assistant_message.tool_calls:
            messages.append(assistant_message)
            
            for tool_call in assistant_message.tool_calls:
                function_name = tool_call.function.name
                function_args = json.loads(tool_call.function.arguments)
                
                if function_name not in tools_called:
                    tools_called.append(function_name)

                if function_name == "search_catalog":
                    tool_output = search_catalog(query=function_args.get("query"))
                    messages.append({
                        "tool_call_id": tool_call.id,
                        "role": "tool",
                        "name": function_name,
                        "content": tool_output
                    })
                
                elif function_name == "get_user_memory":
                    tool_output = get_user_memory(user_id=user_id, db=db, memory_backend=memory_backend)
                    messages.append({
                        "tool_call_id": tool_call.id,
                        "role": "tool",
                        "name": function_name,
                        "content": tool_output
                    })

            second_response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages
            )
            raw_text = second_response.choices[0].message.content
        else:
            raw_text = assistant_message.content

        cleaned_text = raw_text
        extracted_fact = None
        if "[EXTRACTED_FACT]:" in raw_text:
            parts = raw_text.split("[EXTRACTED_FACT]:")
            cleaned_text = parts[0].strip()
            extracted_fact = parts[1].strip()

        return cleaned_text, tools_called, extracted_fact