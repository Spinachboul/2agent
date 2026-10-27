class AgentIdentifier:
    """Deterministic capability catalog, grounded in requirements."""

    CATALOG = [
        {
            "id": "document_parser",
            "name": "Document Parser Agent",
            "capabilities": ["document ingestion", "content extraction"],
        },
        {
            "id": "json_generator",
            "name": "JSON Generator Agent",
            "capabilities": ["structured data generation"],
        },
        {
            "id": "validator",
            "name": "Validator Agent",
            "capabilities": ["schema validation", "reference validation"],
        },
        {
            "id": "workflow_orchestrator",
            "name": "Workflow Orchestrator Agent",
            "capabilities": ["workflow execution", "dependency management"],
        },
        {
            "id": "exporter",
            "name": "Exporter Agent",
            "capabilities": ["JSON export", "document export"],
        },
        {
            "id": "notification",
            "name": "Notification Agent",
            "capabilities": ["notifications", "status communication"],
        },
    ]

    def run(self, reasoning: dict) -> list[dict]:
        capabilities = {
            item.lower()
            for item in reasoning.get("required_capabilities", [])
            if isinstance(item, str)
        }

        selected = []
        for agent in self.CATALOG:
            matched = sorted(
                capability
                for capability in agent["capabilities"]
                if capability.lower() in capabilities
            )
            if matched:
                selected.append({
                    **agent,
                    "matched_capabilities": matched,
                    "requirement_ids": [],
                    "selection_reason": (
                        "Matched reasoning output capabilities"
                    ),
                })

        return selected