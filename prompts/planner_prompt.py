PLANNER_SYSTEM_PROMPT = """
Generate an implementation workflow DAG from the supplied reasoning.

Return JSON containing:

- nodes
- dependencies
- execution_order
- success_criteria
- agents_to_build

For each agent return:
- name
- purpose
- inputs
- outputs
- tools
- dependencies_on_other_agents

Additionally return:

- agents_to_build
    - name
    - responsibility
    - inputs
    - outputs
    - tools_required

The graph must be acyclic.
Do not claim that execution has occurred.
"""