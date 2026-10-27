from langgraph.graph import StateGraph, START, END

from state.workflow_state import WorkflowState
from graph.nodes import (
    json_generator_node,
    validator_node,
    reasoning_node,
    workflow_planner_node,
    agent_identifier_node,
    refresh_usage_node,
    after_validation,
)


def build_workflow():
    graph = StateGraph(WorkflowState)

    graph.add_node("json_generator", json_generator_node)
    graph.add_node("validator", validator_node)
    graph.add_node("reasoning", reasoning_node)
    graph.add_node("workflow_planner", workflow_planner_node)
    graph.add_node("agent_identifier", agent_identifier_node)
    graph.add_node("refresh_usage", refresh_usage_node)

    graph.add_edge(START, "json_generator")
    graph.add_edge("json_generator", "validator")

    graph.add_conditional_edges(
        "validator",
        after_validation,
        {
            "continue": "reasoning",
            "stop": "refresh_usage",
        },
    )

    graph.add_edge("reasoning", "workflow_planner")
    graph.add_edge("workflow_planner", "agent_identifier")
    graph.add_edge("agent_identifier", "refresh_usage")
    graph.add_edge("refresh_usage", END)

    return graph


workflow_graph = build_workflow()
workflow_graph = workflow_graph.compile()