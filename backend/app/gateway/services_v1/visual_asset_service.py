from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import HTTPException, Request

from app.gateway.schemas.v1.visual_assets import (
    VisualAssetCancelResponse,
    VisualAssetCreateResponse,
    VisualAssetDTO,
    VisualAssetErrorDTO,
    VisualAssetGenerateRequest,
    VisualAssetJobDTO,
    VisualAssetOwnerDTO,
    VisualAssetSimpleAssetDTO,
    VisualAssetSimpleCreateResponse,
    VisualAssetSimpleErrorDTO,
    VisualAssetSimpleGenerateRequest,
    VisualAssetSimpleJobDTO,
    VisualAssetUsageDTO,
)
from app.gateway.services_v1.artifact_service import create_image_artifact
from app.gateway.services_v1.external_context import ExternalContext
from app.gateway.services_v1.image_provider import ImageProvider, ImageProviderError, create_image_provider_from_env
from app.gateway.services_v1.visual_asset_job_store import VisualAssetJob, job_store
from app.gateway.services_v1.visual_design_agent import build_design_brief
from app.gateway.services_v1.visual_prompt_builder import build_image_prompt


class VisualAssetService:
    def _configure_job_store(self, request: Request) -> None:
        persist_dir = getattr(request.app.state, "v1_visual_asset_job_dir", None)
        if persist_dir is None:
            from deerflow.config.paths import get_paths
            persist_dir = get_paths().base_dir / "v1" / "jobs" / "visual-assets"
        job_store.configure_persistence(Path(persist_dir))

    def _get_image_provider(self, request: Request) -> ImageProvider:
        provider = getattr(request.app.state, "v1_image_provider", None)
        if provider is not None:
            return provider
        return create_image_provider_from_env()

    def create_job(self, request: Request, body: VisualAssetGenerateRequest, context: ExternalContext) -> VisualAssetCreateResponse:
        self._configure_job_store(request)
        job = VisualAssetJob(
            job_id=f"job_visual_{uuid.uuid4().hex[:12]}",
            scene=body.scene,
            owner=VisualAssetOwnerDTO(app_id=context.app_id, external_user_id=context.external_user_id),
            request=body,
        )
        job_store.create(job)
        return VisualAssetCreateResponse(
            job_id=job.job_id,
            status=job.status,
            stage=job.stage,
            progress=job.progress,
            scene=job.scene,
            message=job.message,
            created_at=job.created_at,
        )

    def create_simple_job(self, request: Request, body: VisualAssetSimpleGenerateRequest, context: ExternalContext) -> VisualAssetSimpleCreateResponse:
        response = self.create_job(request, body.to_generate_request(), context)
        return VisualAssetSimpleCreateResponse(
            job_id=response.job_id,
            status=response.status,
            progress=response.progress,
            message=response.message,
            created_at=response.created_at,
        )

    async def process_job(self, request: Request, job_id: str, context: ExternalContext) -> None:
        self._configure_job_store(request)
        job = job_store.get(job_id, app_id=context.app_id, external_user_id=context.external_user_id)
        if job is None or job.status == "cancelled":
            return

        provider_name = "openai"
        try:
            provider = self._get_image_provider(request)
            provider_name = provider.provider_name
            job.usage = VisualAssetUsageDTO(provider=provider_name)

            job_store.update_state(job, status="running", stage="analyzing", progress=10, message="正在理解你的描述")
            brief = build_design_brief(job.request)
            job.design_brief = brief

            job_store.update_state(job, status="running", stage="prompting", progress=30, message="正在整理视觉设计方案")
            prompt = build_image_prompt(job.request, brief)

            job_store.update_state(job, status="running", stage="generating", progress=50, message="正在生成候选图片")
            images = await provider.generate(prompt)

            job_store.update_state(job, status="running", stage="storing", progress=90, message="正在保存生成结果")
            from deerflow.config.paths import get_paths
            base_dir = Path(getattr(request.app.state, "v1_artifact_base_dir", None) or (get_paths().base_dir / "v1" / "artifacts"))
            assets: list[VisualAssetDTO] = []
            for index, image in enumerate(images):
                asset_id = f"asset_{index + 1:03d}"
                artifact = create_image_artifact(
                    base_dir=base_dir,
                    app_id=context.app_id,
                    external_user_id=context.external_user_id,
                    job_id=job.job_id,
                    asset_id=asset_id,
                    image_bytes=image.bytes,
                    mime_type=image.mime_type,
                    width=image.width,
                    height=image.height,
                    metadata={**job.request.metadata, "job_id": job.job_id, "asset_id": asset_id, "scene": job.scene},
                )
                assets.append(
                    VisualAssetDTO(
                        asset_id=asset_id,
                        artifact_id=artifact.artifact_id,
                        scene=job.scene,
                        usage=job.request.target.usage or job.scene,
                        mime_type=artifact.mime_type,
                        width=image.width,
                        height=image.height,
                        preview_url=artifact.preview_url,
                        download_url=artifact.download_url,
                    )
                )

            job.assets = assets
            job.usage = VisualAssetUsageDTO(image_count=len(assets), provider=provider_name)
            job_store.update_state(job, status="succeeded", stage="succeeded", progress=100, message="生成完成")
        except ImageProviderError as exc:
            job.usage = VisualAssetUsageDTO(provider=provider_name)
            job.error = VisualAssetErrorDTO(code=exc.code, message=exc.message, retryable=exc.retryable, details=exc.details)
            job_store.update_state(job, status="failed", stage="failed", progress=100, message=exc.message)
        except Exception as exc:
            job.usage = VisualAssetUsageDTO(provider=provider_name)
            job.error = VisualAssetErrorDTO(
                code="visual_asset_generation_failed",
                message="Visual asset generation failed",
                retryable=False,
                details={"error": str(exc)[:500]},
            )
            job_store.update_state(job, status="failed", stage="failed", progress=100, message="Visual asset generation failed")

    def get_job(self, request: Request, job_id: str, context: ExternalContext) -> VisualAssetJobDTO:
        self._configure_job_store(request)
        job = job_store.get(job_id, app_id=context.app_id, external_user_id=context.external_user_id)
        if job is None:
            raise HTTPException(status_code=404, detail=f"Visual asset job {job_id} not found")
        return job.to_dto()

    def get_simple_job(self, request: Request, job_id: str, context: ExternalContext) -> VisualAssetSimpleJobDTO:
        job = self.get_job(request, job_id, context)
        return VisualAssetSimpleJobDTO(
            job_id=job.job_id,
            status=job.status,
            progress=job.progress,
            message=job.message,
            assets=[
                VisualAssetSimpleAssetDTO(
                    asset_id=asset.asset_id,
                    preview_url=asset.preview_url,
                    download_url=asset.download_url,
                    width=asset.width,
                    height=asset.height,
                )
                for asset in job.assets
            ],
            error=VisualAssetSimpleErrorDTO(code=job.error.code, message=job.error.message) if job.error else None,
        )

    def cancel_job(self, request: Request, job_id: str, context: ExternalContext, reason: str | None = None) -> VisualAssetCancelResponse:
        self._configure_job_store(request)
        job = job_store.get(job_id, app_id=context.app_id, external_user_id=context.external_user_id)
        if job is None:
            raise HTTPException(status_code=404, detail=f"Visual asset job {job_id} not found")
        if job.status in {"succeeded", "failed"}:
            return VisualAssetCancelResponse(job_id=job.job_id, status=job.status, stage=job.stage, progress=job.progress, message=job.message)
        job_store.update_state(job, status="cancelled", stage="cancelled", progress=100, message=reason or "任务已取消")
        return VisualAssetCancelResponse(job_id=job.job_id, status=job.status, stage=job.stage, progress=job.progress, message=job.message)


visual_asset_service = VisualAssetService()
