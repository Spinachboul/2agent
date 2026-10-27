import json

from prompts.generator_prompt import GENERATOR_SYSTEM_PROMPT
from schemas.brd_schema import BRD_SCHEMA
from services.azure_openai_service import azure_service


class JSONGeneratorAgent:
    def run(self, session_id: str, document_state: dict) -> dict:
        payload = {
            "schema": BRD_SCHEMA,
            "document_state": document_state,
        }

        raw = azure_service.invoke(
            agent_name="json_generator",
            session_id=session_id,
            messages=[
                {"role": "system", "content": GENERATOR_SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(
                    payload, ensure_ascii=False, default=str
                )},
            ],
            response_format={"type": "json_object"},
        )
        result = json.loads(raw)

        # Deterministic schema validation is a separate stage.
        return result