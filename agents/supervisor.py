
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from services.extractor_service import ExtractorService
from services.persistence import repository
from state.document_state import DocumentState


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class SupervisorAgent:
    def __init__(
        self,
        extractor_service: ExtractorService | None = None,
    ):
        self.extractor_service = extractor_service or ExtractorService()

    def ingest(
        self,
        uploaded_path: str | Path,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        session_id = session_id or str(uuid4())
        document_id = str(uuid4())
        uploaded_path = Path(uploaded_path).resolve()

        # Run the existing extractor exactly once.
        extracted = self.extractor_service.extract(
            uploaded_path=uploaded_path,
            document_id=document_id,
        )
        document_state = DocumentState.model_validate(extracted)

        now = utc_now()
        state = {
            "session_id": session_id,
            "document_id": document_id,
            "current_stage": "extracted",
            "current_agent": "supervisor",
            "uploaded_file": uploaded_path.name,
            "document_state": document_state.model_dump(mode="json"),
            "generated_json": {},
            "validated_json": {},
            "validation_report": {},
            "workflow_plan": {},
            "identified_agents": [],
            "knowledge_graph": {},
            "lineage_graph": document_state.source_lineage,
            "chat_history": [],
            "agent_outputs": {},
            "token_usage": {},
            "cost_usage": {},
            "audit_log": [{
                "timestamp": now,
                "agent": "supervisor",
                "action": "document_extracted",
                "document_id": document_id,
                "details": {
                    "filename": uploaded_path.name,
                    "sha256": document_state.hash,
                    "status": document_state.status,
                },
            }],
            "created_at": now,
            "updated_at": now,
        }

        return state

    def process(
        self,
        uploaded_path: str | Path,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        # Ingestion and extraction happen only once.
        state = self.ingest(uploaded_path, session_id)

        # Run the configured LangGraph pipeline.
        from graph.workflow_graph import workflow_graph

        result = workflow_graph.invoke(state)

        if hasattr(result, "model_dump"):
            result = result.model_dump(mode="json")

        if not isinstance(result, dict):
            raise TypeError(
                "LangGraph must return a dictionary-compatible workflow state"
            )

        result["updated_at"] = utc_now()

        # Persist the completed session.
        repository.save("sessions", result["session_id"], result)
        repository.save(
            "generated_json",
            result["document_id"],
            result.get("validated_json")
            or result.get("generated_json", {}),
        )

        return result
