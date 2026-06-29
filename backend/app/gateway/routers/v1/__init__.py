from fastapi import APIRouter

from app.gateway.routers.v1 import (
    agents,
    artifacts,
    capabilities,
    conversations,
    data_sources,
    reports,
    runs,
    visual_assets,
    workspace_datasource,
)

router = APIRouter(prefix="/api/v1")
router.include_router(capabilities.router)
router.include_router(conversations.router)
router.include_router(agents.router)
router.include_router(runs.router)
router.include_router(data_sources.router)
router.include_router(artifacts.router)
router.include_router(reports.router)
router.include_router(reports.status_router)
router.include_router(visual_assets.router)
router.include_router(workspace_datasource.router)


__all__ = [
    "agents",
    "artifacts",
    "capabilities",
    "conversations",
    "data_sources",
    "reports",
    "runs",
    "visual_assets",
    "workspace_datasource",
]
