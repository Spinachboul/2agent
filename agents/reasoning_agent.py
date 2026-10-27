import json

from prompts.reasoning_prompt import REASONING_SYSTEM_PROMPT
from services.azure_openai_service import azure_service


class ReasoningAgent:
    def run(self, session_id: str, validated_json: dict) -> dict:
        raw = azure_service.invoke(
            agent_name="reasoning_agent",
            session_id=session_id,
            messages=[
                {"role": "system", "content": REASONING_SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(
                    validated_json, ensure_ascii=False
                )},
            ],
            response_format={"type": "json_object"},
        )
        return json.loads(raw)