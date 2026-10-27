import hashlib
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from api.dependencies import get_supervisor, get_copilot
from config import get_settings
from services.persistence import repository
from services.token_tracker import token_tracker
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["BRD Copilot"])


class ChatRequest(BaseModel):
    session_id: str
    question: str = Field(min_length=1, max_length=10000)

@router.post("/documents")
async def upload_document(
    file: UploadFile = File(...),
    supervisor=Depends(get_supervisor),
):
    cfg = get_settings()
    allowed = {".pdf", ".docx", ".xlsx", ".pptx", ".png",
                ".jpg", ".jpeg", ".tif", ".tiff"}

    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in allowed:
        raise HTTPException(415, "Unsupported file extension")

    content = await file.read(cfg.max_upload_mb * 1024 * 1024 + 1)
    if len(content) > cfg.max_upload_mb * 1024 * 1024:
        raise HTTPException(413, "File exceeds configured size limit")

    digest = hashlib.sha256(content).hexdigest()
    upload_path = cfg.storage_root / "documents" / f"{digest}{suffix}"
    upload_path.parent.mkdir(parents=True, exist_ok=True)

    if not upload_path.exists():
        upload_path.write_bytes(content)

    session_id = str(uuid.uuid4())

    # Prototype: synchronous processing.
    # Production: enqueue a job and return 202 with session_id.
    try:
        result = supervisor.process(upload_path, session_id)
    except Exception as exc:
        logger.exception(
            "Document processing failed: session_id=%s, file=%s",
            session_id,
            file.filename,
        )
        # Log the full exception internally; avoid returning secrets.
        raise HTTPException(
            500, "Document processing failed"
        ) from exc

    return {
        "session_id": session_id,
        "document_id": result["document_id"],
        "status": result.get("current_stage", "completed"),
        "validation_report": result.get("validation_report", {}),
    }


@router.get("/sessions/{session_id}")
def get_session(session_id: str):
    state = repository.load("sessions", session_id)
    if not state:
        raise HTTPException(404, "Session not found")

    # Do not return extracted document content by default.
    return {
        "session_id": session_id,
        "document_id": state.get("document_id"),
        "current_stage": state.get("current_stage"),
        "validation_report": state.get("validation_report", {}),
        "workflow_plan": state.get("workflow_plan", {}),
        "identified_agents": state.get("identified_agents", []),
        "token_usage": state.get("token_usage", {}),
        "cost_usage": state.get("cost_usage", {}),
        "audit_log": state.get("audit_log", []),
    }


@router.get("/sessions/{session_id}/knowledge")
def get_knowledge(session_id: str):
    state = repository.load("sessions", session_id)
    if not state:
        raise HTTPException(404, "Session not found")

    return repository.load(
        "generated_json", state["document_id"]
    ) or {}


@router.post("/chat")
def chat(
    request: ChatRequest,
    copilot=Depends(get_copilot),
):
    try:
        return copilot.ask(request.session_id, request.question)
    except KeyError:
        raise HTTPException(404, "Session not found")
    except Exception as exc:
        raise HTTPException(500, "Copilot request failed") from exc


@router.get("/sessions/{session_id}/usage")
def get_usage(session_id: str):
    state = repository.load("sessions", session_id)
    if not state:
        raise HTTPException(404, "Session not found")
    return token_tracker.get(session_id)