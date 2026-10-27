import json
import logging

from prompts.planner_prompt import PLANNER_SYSTEM_PROMPT
from services.azure_openai_service import azure_service
from services.workflow_service import validate_and_order

logger = logging.getLogger(__name__)


class WorkflowPlannerAgent:
    MAX_RETRIES = 3

    def run(self, session_id: str, reasoning: dict) -> dict:
        validation_error = None

        for attempt in range(1, self.MAX_RETRIES + 1):

            user_content = json.dumps(reasoning)

            if validation_error:
                user_content += f"""

Previous workflow generation failed validation.

Validation Error:
{validation_error}

Regenerate the workflow ensuring:
1. No circular dependencies exist.
2. The dependency graph is a valid DAG.
3. Tasks only depend on predecessors.
4. Return valid JSON only.
"""

            try:
                raw = azure_service.invoke(
                    agent_name="workflow_planner",
                    session_id=session_id,
                    messages=[
                        {
                            "role": "system",
                            "content": PLANNER_SYSTEM_PROMPT,
                        },
                        {
                            "role": "user",
                            "content": user_content,
                        },
                    ],
                    response_format={"type": "json_object"},
                )

                workflow = json.loads(raw)

                # validates schema + performs topological ordering
                validated_workflow = validate_and_order(workflow)

                logger.info(
                    "Workflow planning succeeded on attempt %s",
                    attempt,
                )

                return validated_workflow

            except json.JSONDecodeError as e:
                validation_error = (
                    f"Invalid JSON returned by model: {str(e)}"
                )

                logger.warning(
                    "Workflow planner JSON error on attempt %s: %s",
                    attempt,
                    validation_error,
                )

            except ValueError as e:
                validation_error = str(e)

                logger.warning(
                    "Workflow planner validation error on attempt %s: %s",
                    attempt,
                    validation_error,
                )

            except Exception as e:
                validation_error = str(e)

                logger.exception(
                    "Workflow planner unexpected error on attempt %s",
                    attempt,
                )

        raise ValueError(
            f"Workflow planning failed after "
            f"{self.MAX_RETRIES} attempts. "
            f"Last error: {validation_error}"
        )