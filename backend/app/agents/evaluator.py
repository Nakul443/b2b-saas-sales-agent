# part of the "brain" of the AI

# takes the response text along with the catalog data and user facts
# and scores the reply to make sure it is accurate and truthful

# Response Auditor: using Gemini Structured Outputs to enforce JSON schemas via OpenAI SDK.

import os
import json
from openai import OpenAI
from app.models.schemas import EvaluationBlock

class ResponseEvaluator:
    """
    Talks directly to Gemini using Structured Outputs to score the agent's answer.
    """
    def __init__(self):
        # Point the OpenAI SDK to use Google's free API gateway endpoint
        self.client = OpenAI(
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
            api_key=os.getenv("GEMINI_API_KEY")
        )

    def score_response(self, user_message: str, agent_response: str, catalog_context: str, memory_context: str) -> EvaluationBlock:
        # Define strict quality assessment definitions for the LLM audit
        # We explicitly enforce the JSON keys directly inside the prompt block here
        system_instruction = (
            "You are an objective AI quality auditing system. Your task is to evaluate a sales assistant's response "
            "against the provided product catalog context and known user facts. You must assign strict numerical scores "
            "between 0.0 and 1.0 and provide rigorous reasoning.\n\n"
            "Evaluation Items:\n"
            "1. groundedness: Is the response supported by the catalog? Drop scores if info is made up.\n"
            "2. relevance: Does it answer the user's question and apply their past facts?\n"
            "3. confidence: How certain are you about the accuracy of the answer?\n"
            "4. flagged: Set to true if confidence drops below 0.70.\n"
            "5. reasoning: A short technical sentence explaining the scores.\n\n"
            "CRITICAL: You MUST return a valid JSON object containing exactly these five keys: "
            "\"groundedness\" (number), \"relevance\" (number), \"confidence\" (number), \"flagged\" (boolean), and \"reasoning\" (string)."
        )

        # Assemble contexts into an explicit clear-text document payload
        user_content = (
            f"--- PRODUCT CATALOG ---\n{catalog_context}\n\n"
            f"--- USER FACTS ---\n{memory_context}\n\n"
            f"--- USER INPUT ---\n{user_message}\n\n"
            f"--- ASSISTANT ANSWER ---\n{agent_response}\n\n"
            "Analyze and return the structured self-evaluation block."
        )

        try:
            # Shift response_format to the standard format accepted by Google's gateway
            completion = self.client.chat.completions.create(
                model="gemini-2.5-flash",
                messages=[
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": user_content}
                ],
                response_format={"type": "json_object"},
                temperature=0.0
            )
            
            # Parse the structured JSON back into our exact Pydantic model structure
            raw_json = json.loads(completion.choices[0].message.content.strip())
            return EvaluationBlock(**raw_json)
            
        except Exception as e:
            return EvaluationBlock(
                groundedness=0.5, relevance=0.5, confidence=0.5, flagged=True,
                reasoning=f"Error running evaluator: {str(e)}"
            )