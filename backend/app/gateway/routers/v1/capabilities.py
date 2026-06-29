from __future__ import annotations

from fastapi import APIRouter, Depends

from app.gateway.services_v1.external_context import get_external_context

router = APIRouter(prefix="/capabilities", tags=["v1-capabilities"], dependencies=[Depends(get_external_context)])


@router.get("", summary="Get v1 capabilities", description="Return feature flags for the external intelli-engine v1 API.")
async def get_capabilities() -> dict:
    return {
        "conversation": {"supported": True, "streaming": True, "multi_turn": True, "history": True, "file_upload": True},
        "agents": {"supported": True, "invoke": True, "stream": True, "custom_agents": True, "subagents": True},
        "data_sources": {
            "supported": True,
            "selected_ids_in_message": True,
            "registration": True,
            "types": ["text", "file", "url", "sql", "es"],
            "nl_query": {
                "supported": True,
                "text_to_sql": {"supported": True, "dialects": ["mysql", "postgresql", "sqlite", "mssql", "oracle"]},
                "text_to_es": {"supported": True},
            },
        },
        "data_assets": {
            "supported": True,
            "workspace_api": True,
            "types": ["mysql", "postgresql", "clickhouse", "es", "minio", "s3", "pdf", "docx", "txt", "markdown", "xlsx", "csv", "ppt"],
            "features": {
                "test_connection": True,
                "attach_to_conversation": True,
                "alias_rename": True,
                "soft_delete": True,
            },
        },
        "reports": {"enabled": True, "supported": True, "formats": ["docx", "html"], "types": ["analysis", "summary", "research", "meeting_notes", "decision_memo"]},
        "visual_assets": {
            "enabled": True,
            "async": True,
            "scenes": ["logo", "notebook_icon", "notebook_background", "cover_image", "general_image"],
            "max_num_images": 4,
            "artifact_output": True,
        },
        "logo": {"image_generate": True, "via": "visual_assets", "accurate_text_supported": False},
    }
