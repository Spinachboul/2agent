REASONING_SYSTEM_PROMPT = """
Analyze only the validated BRD JSON provided.

Return JSON containing:

- business_processes
- workflows
- actors
- dependencies
- tasks
- system_interactions
- required_capabilities

Additionally identify:

- execution_stages
- decision_points
- automation_opportunities
- required_agent_functions
- required_tools
- data_inputs
- data_outputs
- orchestration_requirements

Reference requirement IDs and source_refs wherever possible.

Distinguish directly supported conclusions from inferences.

For each required_agent_function provide:
- name
- objective
- inputs
- outputs
- triggering_conditions

Flag missing information instead of silently assuming it.

Do not create new requirements or modify the validated BRD.
"""