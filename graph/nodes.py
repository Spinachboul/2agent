from datetime import datetime, timezone

from agents.json_generator import JSONGeneratorAgent
from agents.validator import ValidatorAgent
from agents.reasoning_agent import ReasoningAgent
from agents.workflow_planner import WorkflowPlannerAgent
from agents.agent_identifier import AgentIdentifier

from services.token_tracker import token_tracker
from services.persistence import repository


generator = JSONGeneratorAgent()
validator = ValidatorAgent()
reasoner = ReasoningAgent()
planner = WorkflowPlannerAgent()
identifier = AgentIdentifier()


def record_transition(state, agent, stage, updates=None):
    event = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "agent": agent,
        "action": stage,
        "session_id": state["session_id"],
        "document_id": state["document_id"],
    }

    log = [*state.get("audit_log", []), event]

    result = {
        **(updates or {}),
        "current_stage": stage,
        "current_agent": agent,
        "audit_log": log,
    }

    repository.save(
        "audit_logs",
        state["session_id"],
        log,
    )

    return result


def json_generator_node(state):
    generated_json = generator.run(
        state["session_id"],
        state["document_state"],
    )

    return record_transition(
        state,
        "json_generator",
        "json_generated",
        {
            "generated_json": generated_json,
            "agent_outputs": {
                **state.get("agent_outputs", {}),
                "json_generator": generated_json,
            },
        },
    )


def validator_node(state):
    validated_json, validation_report = validator.run(
        # state["genreated_json"] is not None
        state["generated_json"]
    )
    
    updates = {
        "validation_report": validation_report,
    }

    if not validation_report.get("is_valid", False):
        return record_transition(
            state,
            "validator",
            "validation_failed",
            updates,
        )

    updates["validated_json"] = validated_json
    updates["agent_outputs"] = {
        **state.get("agent_outputs", {}),
        "validator": validation_report,
    }

    return record_transition(
        state,
        "validator",
        "validation_passed",
        updates,
    )


def reasoning_node(state):
    reasoning_analysis = reasoner.run(
        state["session_id"],
        state["validated_json"],
    )

    return record_transition(
        state,
        "reasoning_agent",
        "reasoning_completed",
        {
            "reasoning_analysis": reasoning_analysis,
            "agent_outputs": {
                **state.get("agent_outputs", {}),
                "reasoning": reasoning_analysis,
            },
        },
    )


def workflow_planner_node(state):
    try:
        workflow_plan = planner.run(
            state["session_id"],
            state["reasoning_analysis"],
        )

        return record_transition(
            state,
            "workflow_planner",
            "workflow_planned",
            {
                "workflow_plan": workflow_plan,
                "workflow_status": "SUCCESS",
                "agent_outputs": {
                    **state.get("agent_outputs", {}),
                    "workflow_planner": workflow_plan,
                },
            },
        )
    except Exception as e:
        return record_transition(
            state,
            "workflow_planner",
            "workflow_failed",
            {
                "workflow_status": "FAILED",
                "workflow_error": str(e),
                "workflow_plan": None
            }
        )



def agent_identifier_node(state):
    identified_agents = identifier.run(
        state["workflow_plan"]
    )

    return record_transition(
        state,
        "agent_identifier",
        "agents_identified",
        {
            "identified_agents": identified_agents,
            "agent_outputs": {
                **state.get("agent_outputs", {}),
                "agent_identifier": identified_agents,
            },
        },
    )


def refresh_usage_node(state):
    usage = token_tracker.get(state["session_id"])

    return {
        "token_usage": usage,
        "cost_usage": {
            "total_cost": usage["total_cost"],
            "currency": "USD",
            "is_estimate": True,
        },
    }


def after_validation(state):
    report = state.get("validation_report", {})

    if not report.get("is_valid", False):
        return "stop"

    return "continue"