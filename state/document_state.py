
from typing import Any, Literal
from pydantic import BaseModel, Field


class SourceRecord(BaseModel):
    source: str | None = None
    saved_path: str | None = None
    kind: str = "document"
    content_type: str | None = None
    text: str = ""
    error: str | None = None
    link: str | None = None
    access_status: str | None = None


class DocumentState(BaseModel):
    document_id: str
    root_document: dict[str, Any]
    document_type: str
    main_content: list[SourceRecord] = Field(default_factory=list)
    embedded_documents: list[SourceRecord] = Field(default_factory=list)
    images: list[SourceRecord] = Field(default_factory=list)
    ocr_results: list[dict[str, Any]] = Field(default_factory=list)
    tables: list[dict[str, Any]] = Field(default_factory=list)
    external_links: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    source_lineage: dict[str, Any] = Field(default_factory=dict)
    hash: str
    status: Literal[
        "completed",
        "completed_with_warnings",
        "failed",
    ] = "completed"
