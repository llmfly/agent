from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import PurePosixPath
from typing import Any
from urllib.parse import quote


@dataclass
class ArtifactDTO:
    artifact_id: str
    conversation_id: str | None = None
    run_id: str | None = None
    filename: str | None = None
    mime_type: str | None = None
    url: str = ""
    created_at: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


def _metadata_path(item: Any) -> str | None:
    metadata = getattr(item, "metadata", None)
    if isinstance(metadata, dict):
        path = metadata.get("path")
        if isinstance(path, str):
            return path
    return None


def artifact_url(conversation_id: str, path: str) -> str:
    encoded_path = quote(path.lstrip("/"), safe="/")
    return f"/api/v1/conversations/{conversation_id}/artifacts/by-path/{encoded_path}"


def merge_conversation_artifact_items(
    *,
    conversation_id: str,
    persisted_items: list[Any],
    state_artifacts: list[Any] | None,
    dto_factory: Callable[..., Any] = ArtifactDTO,
) -> list[Any]:
    """Merge v1 artifact records with native DeerFlow state artifact paths."""

    items = list(persisted_items)
    seen_paths = {_metadata_path(item) for item in items}

    for artifact in state_artifacts or []:
        if not isinstance(artifact, str) or not artifact:
            continue
        if artifact in seen_paths:
            continue
        seen_paths.add(artifact)

        filename = PurePosixPath(artifact).name or artifact.rstrip("/").rsplit("/", 1)[-1] or artifact
        items.append(
            dto_factory(
                artifact_id=f"path:{artifact}",
                conversation_id=conversation_id,
                filename=filename,
                mime_type=None,
                url=artifact_url(conversation_id, artifact),
                created_at=None,
                metadata={
                    "source": "thread_state",
                    "path": artifact,
                    "download_url": f"{artifact_url(conversation_id, artifact)}?download=true",
                },
            )
        )

    return items
