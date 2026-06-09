# part of the "brain" of the AI

# takes the response text along with the catalog data and user facts
# and scores the reply to make sure it is accurate and truthful

# Response Auditor: using OpenAI Structured Outputs to enforce JSON schemas.

import os
from openai import OpenAI
from app.models.schemas import EvaluationBlock

class ResponseEvaluator:
    """
    Talks directly to OpenAI using Structured Outputs to score the agent's answer.
    """
    def __init__(self):
        # Initialize client with environment API key credentials
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    def score_response(self, user_message: str, agent_response: str, catalog_context: str, memory_context: str) -> EvaluationBlock:
        # Define strict quality assessment definitions for the LLM audit
        system_instruction = (
            "You are an objective AI quality auditing system. Your task is to evaluate a sales assistant's response "
            "against the provided product catalog context and known user facts. You must assign strict numerical scores "
            "between 0.0 and 1.0 and provide rigorous reasoning.\n\n"
            "Evaluation Items:\n"
            "1. groundedness: Is the response supported by the catalog? Drop scores if info is made up.\n"
            "2. relevance: Does it answer the user's question and apply their past facts?\n"
            "3. confidence: How certain are you about the accuracy of the answer?\n"
            "4. flagged: Set to true if confidence drops below 0.70.\n"
            "5. reasoning: A short technical sentence explaining the scores."
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
            # force the model to output valid JSON matching Pydantic schema structure
            completion = self.client.beta.chat.completions.parse(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": user_content}
                ],
                response_format=EvaluationBlock,
                temperature=0.0 # to givethe most obvious answer
                # temperature=1 # this is done to get more diverse/creative answers
            )
            return completion.choices[0].message.parsed
        except Exception as e:
            return EvaluationBlock(
                groundedness=0.5, relevance=0.5, confidence=0.5, flagged=True,
                reasoning=f"Error running evaluator: {str(e)}"
            )