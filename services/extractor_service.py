
from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import sys
import uuid

from pathlib import Path
from typing import Any

from services.lineage_service import build_lineage, save_lineage


class ExtractorService:
    """
    Adapter for the existing root-level extractor.py.

    The extractor's parsing, OCR, recursion, and embedded-file
    extraction logic remain unchanged.
    """

    def __init__(
        self,
        extractor_path: str | Path | None = None,
        storage_root: str | Path = "storage/documents",
    ):
        project_root = Path(__file__).resolve().parent.parent

        self.extractor_path = Path(
            extractor_path or project_root / "extractor.py"
        ).resolve()

        self.storage_root = Path(storage_root).resolve()

        if not self.extractor_path.is_file():
            raise FileNotFoundError(
                f"Existing extractor.py was not found: "
                f"{self.extractor_path}"
            )

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as file:
            for chunk in iter(
                lambda: file.read(1024 * 1024), b""
            ):
                digest.update(chunk)
        return digest.hexdigest()

    def _load_extractor(self):
        """
        Load a fresh module instance for each invocation.

        This isolates module globals such as INPUT_PATH and RESULT
        between concurrent jobs. It does not modify extractor.py.
        """
        module_name = f"_brd_extractor_{uuid.uuid4().hex}"

        spec = importlib.util.spec_from_file_location(
            module_name, self.extractor_path
        )
        if spec is None or spec.loader is None:
            raise ImportError(
                f"Cannot load extractor: {self.extractor_path}"
            )

        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module

        try:
            spec.loader.exec_module(module)
        except Exception:
            sys.modules.pop(module_name, None)
            raise

        return module, module_name

    def extract(
        self,
        uploaded_path: str | Path,
        document_id: str,
    ) -> dict[str, Any]:
        """
        Run extraction once for this ingestion job.

        Returns normalized document state plus the original
        extractor result for diagnostics and downstream use.
        """
        uploaded_path = Path(uploaded_path).resolve()

        if not uploaded_path.is_file():
            raise FileNotFoundError(
                f"Uploaded document does not exist: {uploaded_path}"
            )

        digest = self._sha256(uploaded_path)
        job_dir = self.storage_root / document_id
        input_dir = job_dir / "input"
        output_dir = job_dir / "extraction"

        input_dir.mkdir(parents=True, exist_ok=True)

        # Preserve the original filename for extractor compatibility.
        input_copy = input_dir / uploaded_path.name
        if uploaded_path != input_copy:
            shutil.copy2(uploaded_path, input_copy)

        # A per-document output directory prevents one session's
        # extractor run from deleting another session's artifacts.
        if output_dir.exists():
            shutil.rmtree(output_dir)
        output_dir.mkdir(parents=True)

        module = None
        module_name = None

        try:
            module, module_name = self._load_extractor()

            # Configure the existing extractor at runtime.
            module.INPUT_PATH = str(input_copy)
            module.OUTPUT_FOLDER_NAME = str(output_dir)
            module.PRINT_CONTENT_TO_CONSOLE = False

            # This invokes the original extraction implementation.
            result = module.main()

            if not isinstance(result, dict):
                raise RuntimeError(
                    "extractor.main() did not return a dictionary"
                )

            normalized = self._normalize_result(
                result=result,
                document_id=document_id,
                original_name=uploaded_path.name,
                digest=digest,
            )

            # Persist raw output separately for debugging/auditing.
            raw_result_path = job_dir / "extractor_result.json"
            raw_result_path.write_text(
                json.dumps(
                    result, ensure_ascii=False, indent=2, default=str
                ),
                encoding="utf-8",
            )

            normalized["metadata"]["extractor_result_path"] = str(
                raw_result_path
            )

            lineage = build_lineage(result, document_id)
            normalized["source_lineage"] = lineage

            save_lineage(
                lineage,
                job_dir / "lineage_graph.json",
            )

            state_path = job_dir / "document_state.json"
            state_path.write_text(
                json.dumps(
                    normalized,
                    ensure_ascii=False,
                    indent=2,
                    default=str,
                ),
                encoding="utf-8",
            )

            normalized["metadata"]["document_state_path"] = str(
                state_path
            )
            return normalized

        finally:
            # Do not leave dynamic module instances accumulating.
            if module_name:
                sys.modules.pop(module_name, None)

    @staticmethod
    def _normalize_result(
        result: dict[str, Any],
        document_id: str,
        original_name: str,
        digest: str,
    ) -> dict[str, Any]:
        items = result.get("items", [])
        extracted_contents = result.get("extracted_contents", {})
        external_links = result.get("external_links", [])
        errors = result.get("errors", [])

        main_content: list[dict[str, Any]] = []
        embedded_documents: list[dict[str, Any]] = []
        images: list[dict[str, Any]] = []
        ocr_results: list[dict[str, Any]] = []
        tables: list[dict[str, Any]] = []

        for item in items:
            kind = item.get("kind")
            path = item.get("saved_path")
            text = item.get("text", "") or ""

            record = {
                "source": item.get("source"),
                "saved_path": path,
                "kind": kind,
                "content_type": item.get("content_type"),
                "text": text,
                "error": item.get("error"),
                "link": item.get("link"),
                "access_status": item.get("access_status"),
            }

            if kind == "external_link":
                continue

            if kind == "image_ocr":
                images.append(record)
                ocr_results.append({
                    "source": item.get("source"),
                    "saved_path": path,
                    "text": text,
                    "error": item.get("error"),
                })
            elif path and "/embedded_files/" in path.replace("\\", "/"):
                embedded_documents.append(record)
            elif kind == "document":
                main_content.append(record)

            # The extractor embeds table contents into document text.
            # Do not fabricate cell-level structure that it doesn't return.
            # A future adapter can add structured table parsing here.

        return {
            "document_id": document_id,
            "root_document": {
                "filename": original_name,
                "input_file": result.get("input_file"),
                "output_folder": result.get("output_folder"),
            },
            "document_type": Path(original_name).suffix.lower(),
            "main_content": main_content,
            "embedded_documents": embedded_documents,
            "images": images,
            "ocr_results": ocr_results,
            "tables": tables,
            "external_links": external_links,
            "metadata": {
                "sha256": digest,
                "extraction_error_count": len(errors),
                "extraction_errors": errors,
                "item_count": len(items),
                "extracted_content_count": len(extracted_contents),
                "combined_text": result.get("combined_text", ""),
            },
            "source_lineage": {},
            "hash": digest,
            "status": (
                "completed_with_warnings"
                if errors
                else "completed"
            ),
        }
