import json
import os
import tempfile
from pathlib import Path
from typing import Any

from config import get_settings


class JsonRepository:
    """Initial local-development repository.

    Atomic replacement protects readers from partially written files.
    Use per-session locking and a transactional database for multi-worker
    production deployments.
    """

    def __init__(self):
        self.root = get_settings().storage_root

    def _path(self, collection: str, key: str) -> Path:
        # Never accept path separators from user-controlled identifiers.
        if not key or any(c not in
                          "abcdefghijklmnopqrstuvwxyz"
                          "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
                          "0123456789-_" for c in key):
            raise ValueError("Invalid storage key")

        allowed = {
            "documents", "generated_json", "workflows",
            "sessions", "token_usage", "audit_logs",
        }
        if collection not in allowed:
            raise ValueError("Invalid collection")

        folder = self.root / collection
        folder.mkdir(parents=True, exist_ok=True)
        return folder / f"{key}.json"

    def save(self, collection: str, key: str,
             data: Any) -> None:
        path = self._path(collection, key)
        payload = json.dumps(
            data, ensure_ascii=False, indent=2, default=str
        )

        fd, temp_name = tempfile.mkstemp(
            dir=path.parent, suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as file:
                file.write(payload)
                file.flush()
                os.fsync(file.fileno())
            os.replace(temp_name, path)
        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)

    def load(self, collection: str, key: str) -> Any:
        path = self._path(collection, key)
        if not path.exists():
            return None
        with path.open(encoding="utf-8") as file:
            return json.load(file)

    def exists(self, collection: str, key: str) -> bool:
        return self._path(collection, key).exists()


repository = JsonRepository()