from importlib import util
from pathlib import Path

_MODULE_PATH = Path(__file__).resolve().parents[1] / "app" / "gateway" / "services_v1" / "conversation_artifacts.py"
_SPEC = util.spec_from_file_location("conversation_artifacts", _MODULE_PATH)
assert _SPEC is not None
assert _SPEC.loader is not None
conversation_artifacts = util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(conversation_artifacts)

merge_conversation_artifact_items = conversation_artifacts.merge_conversation_artifact_items


def test_merge_conversation_artifact_items_adds_native_state_paths() -> None:
    items = merge_conversation_artifact_items(
        conversation_id="thread-1",
        persisted_items=[],
        state_artifacts=["/mnt/user-data/outputs/upkuajing数据系统分析报告.md"],
    )

    assert len(items) == 1
    item = items[0]
    assert item.artifact_id == "path:/mnt/user-data/outputs/upkuajing数据系统分析报告.md"
    assert item.conversation_id == "thread-1"
    assert item.filename == "upkuajing数据系统分析报告.md"
    assert item.url == (
        "/api/v1/conversations/thread-1/artifacts/by-path/"
        "mnt/user-data/outputs/upkuajing%E6%95%B0%E6%8D%AE%E7%B3%BB%E7%BB%9F%E5%88%86%E6%9E%90%E6%8A%A5%E5%91%8A.md"
    )
    assert item.metadata["source"] == "thread_state"
    assert item.metadata["path"] == "/mnt/user-data/outputs/upkuajing数据系统分析报告.md"


def test_merge_conversation_artifact_items_skips_paths_already_present_in_persisted_items() -> None:
    existing = conversation_artifacts.ArtifactDTO(
        artifact_id="art_file_1",
        conversation_id="thread-1",
        filename="report.md",
        url="/api/v1/artifacts/art_file_1/download",
        metadata={"path": "/mnt/user-data/outputs/report.md"},
    )

    items = merge_conversation_artifact_items(
        conversation_id="thread-1",
        persisted_items=[existing],
        state_artifacts=["/mnt/user-data/outputs/report.md"],
    )

    assert items == [existing]
