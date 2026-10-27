from collections import defaultdict, deque


def validate_and_order(plan: dict) -> dict:
    nodes = plan.get("nodes", [])
    edges = plan.get("dependencies", [])

    ids = [node.get("id") for node in nodes]
    if any(not node_id for node_id in ids):
        raise ValueError("Every workflow node needs an ID")
    if len(ids) != len(set(ids)):
        raise ValueError("Workflow node IDs must be unique")

    known = set(ids)
    indegree = dict.fromkeys(ids, 0)
    children = defaultdict(list)

    for edge in edges:
        source = edge["from"]
        target = edge["to"]
        if source not in known or target not in known:
            raise ValueError(f"Unknown workflow edge: {edge}")
        if source == target:
            raise ValueError("Self-dependencies are not allowed")

        children[source].append(target)
        indegree[target] += 1

    queue = deque(node_id for node_id in ids if indegree[node_id] == 0)
    order = []

    while queue:
        current = queue.popleft()
        order.append(current)
        for child in children[current]:
            indegree[child] -= 1
            if indegree[child] == 0:
                queue.append(child)

    if len(order) != len(ids):
        raise ValueError("Workflow contains a dependency cycle")

    return {
        **plan,
        "execution_order": order,
        "success_criteria": plan.get("success_criteria", []),
        "is_valid_dag": True,
    }