
from __future__ import annotations

from collections import defaultdict, deque
from pathlib import Path
from typing import Any
import hashlib
import json


def normalize_path(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return str(Path(value).expanduser().resolve())
    except (OSError, ValueError):
        return str(value)


def source_id(value: str) -> str:
    """Stable ID for a canonical source path."""
    canonical = normalize_path(value) or value
    return "src_" + hashlib.sha256(
        canonical.encode("utf-8")
    ).hexdigest()[:20]


def classify_item(item: dict[str, Any]) -> str:
    kind = item.get("kind", "")
    path = item.get("saved_path") or ""
    suffix = Path(path).suffix.lower()

    if kind == "external_link":
        return "external_link"
    if kind == "image_ocr" or suffix in {
        ".png", ".jpg", ".jpeg", ".bmp", ".tif",
        ".tiff", ".gif", ".webp",
    }:
        return "image"
    if kind == "container_error":
        return "container"
    if kind == "limit":
        return "processing_limit"
    return "document"


def build_lineage(
    extractor_result: dict[str, Any],
    document_id: str,
) -> dict[str, Any]:
    """
    Build a source graph from extractor.py's RESULT.items.

    Edges point parent -> child. The root is identified from
    RESULT.input_file and the extracted copy under output_folder.
    """
    items = extractor_result.get("items", [])
    output_folder = normalize_path(
        extractor_result.get("output_folder")
    )
    input_file = normalize_path(
        extractor_result.get("input_file")
    )

    nodes: dict[str, dict[str, Any]] = {}
    edges: list[dict[str, str]] = []
    edge_keys: set[tuple[str, str]] = set()
    path_to_id: dict[str, str] = {}

    def ensure_node(
        path: str,
        kind: str = "document",
        **metadata: Any,
    ) -> str:
        canonical = normalize_path(path) or path
        node_id = source_id(canonical)
        path_to_id[canonical] = node_id

        node = nodes.setdefault(node_id, {
            "source_id": node_id,
            "path": canonical,
            "name": Path(canonical).name,
            "kind": kind,
            "document_id": document_id,
            "metadata": {},
        })
        if kind != "document" or node["kind"] == "document":
            node["kind"] = kind
        node["metadata"].update(metadata)
        return node_id

    # Use the extractor's copied original as the graph root.
    root_path = None
    if output_folder and input_file:
        candidate = normalize_path(
            str(Path(output_folder) / "original_document"
                / Path(input_file).name)
        )
        if candidate and Path(candidate).is_file():
            root_path = candidate

    root_path = root_path or input_file
    if root_path:
        root_id = ensure_node(
            root_path,
            "root_document",
            original_input=input_file,
        )
    else:
        root_id = None

    # Register each item as a source node.
    for item in items:
        saved = normalize_path(item.get("saved_path"))
        if not saved:
            continue

        kind = classify_item(item)
        ensure_node(
            saved,
            kind,
            extracted_kind=item.get("kind"),
            content_type=item.get("content_type"),
            error=item.get("error"),
            link=item.get("link"),
            access_status=item.get("access_status"),
        )

    # Connect child items to their source document.
    for item in items:
        saved = normalize_path(item.get("saved_path"))
        parent_path = normalize_path(item.get("source"))

        if not saved or not parent_path or parent_path == "input":
            continue

        # The extractor records the path of the document that contained
        # the child. Register the parent even if its text extraction failed.
        parent_id = ensure_node(parent_path)
        child_id = ensure_node(
            saved,
            classify_item(item),
            extracted_kind=item.get("kind"),
        )

        edge_key = (parent_id, child_id)
        if parent_id != child_id and edge_key not in edge_keys:
            edge_keys.add(edge_key)
            edges.append({
                "parent_id": parent_id,
                "child_id": child_id,
                "relationship": (
                    "external_link"
                    if item.get("kind") == "external_link"
                    else "contains"
                ),
                "link": item.get("link"),
            })

    # Ensure root-to-original relationships remain explicit.
    # The copied original is already the root; embedded content is
    # connected to it through the extractor's source paths.
    children: dict[str, list[str]] = defaultdict(list)
    parents: dict[str, list[str]] = defaultdict(list)

    for edge in edges:
        children[edge["parent_id"]].append(edge["child_id"])
        parents[edge["child_id"]].append(edge["parent_id"])

    return {
        "root_id": root_id,
        "nodes": nodes,
        "edges": edges,
        "children": dict(children),
        "parents": dict(parents),
        "path_index": path_to_id,
    }


def find_source(
    lineage_graph: dict[str, Any],
    query: str,
) -> list[dict[str, Any]]:
    """Find source nodes by ID, filename, or path."""
    query = query.strip().lower()
    results = []

    for node in lineage_graph.get("nodes", {}).values():
        if (
            query in node.get("source_id", "").lower()
            or query in node.get("name", "").lower()
            or query in node.get("path", "").lower()
        ):
            results.append(node)

    return results


def ancestors(
    lineage_graph: dict[str, Any],
    node_id: str,
) -> list[dict[str, Any]]:
    """Return all ancestors, nearest first."""
    nodes = lineage_graph.get("nodes", {})
    parents = lineage_graph.get("parents", {})
    found: list[dict[str, Any]] = []
    visited: set[str] = set()
    queue = deque(parents.get(node_id, []))

    while queue:
        current = queue.popleft()
        if current in visited:
            continue
        visited.add(current)

        if current in nodes:
            found.append(nodes[current])

        queue.extend(parents.get(current, []))

    return found


def save_lineage(
    lineage_graph: dict[str, Any],
    output_path: str | Path,
) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(lineage_graph, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
