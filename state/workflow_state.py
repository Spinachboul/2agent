from typing import Any
from typing_extensions import TypedDict


class WorkflowState(TypedDict, total=False):
    session_id: str
    document_id: str

    current_stage: str
    current_agent: str

    uploaded_file: str
    document_state: dict[str, Any]

    generated_json: dict[str, Any]
    validated_json: dict[str, Any]
    validation_report: dict[str, Any]

    reasoning_analysis: dict[str, Any]

    workflow_plan: dict[str, Any]

    identified_agents: list[dict[str, Any]]

    agent_outputs: dict[str, Any]

    token_usage: dict[str, Any]
    cost_usage: dict[str, Any]

    audit_log: list[dict[str, Any]]

    error: str | None