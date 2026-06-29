from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from app.gateway.schemas.v1.visual_assets import (
    VisualAssetDTO,
    VisualAssetErrorDTO,
    VisualAssetGenerateRequest,
    VisualAssetJobDTO,
    VisualAssetOwnerDTO,
    VisualAssetScene,
    VisualAssetStage,
    VisualAssetStatus,
    VisualAssetUsageDTO,
    VisualDesignBriefDTO,
)


def _now() -> str:
    return datetime.now(UTC).isoformat()


@dataclass
class VisualAssetJob:
    job_id: str
    scene: VisualAssetScene
    owner: VisualAssetOwnerDTO
    request: VisualAssetGenerateRequest
    status: VisualAssetStatus = "queued"
    stage: VisualAssetStage = "queued"
    progress: int = 0
    message: str = "任务已创建"
    design_brief: VisualDesignBriefDTO | None = None
    assets: list[VisualAssetDTO] = field(default_factory=list)
    usage: VisualAssetUsageDTO = field(default_factory=VisualAssetUsageDTO)
    error: VisualAssetErrorDTO | None = None
    attempt: int = 1
    max_attempts: int = 2
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)
    completed_at: str | None = None

    def to_dto(self) -> VisualAssetJobDTO:
        return VisualAssetJobDTO(
            job_id=self.job_id,
            scene=self.scene,
            status=self.status,
            stage=self.stage,
            progress=self.progress,
            message=self.message,
            owner=self.owner,
            request=self.request,
            design_brief=self.design_brief,
            assets=self.assets,
            usage=self.usage,
            error=self.error,
            attempt=self.attempt,
            max_attempts=self.max_attempts,
            created_at=self.created_at,
            updated_at=self.updated_at,
            completed_at=self.completed_at,
        )

    @classmethod
    def from_dto(cls, dto: VisualAssetJobDTO) -> VisualAssetJob:
        return cls(
            job_id=dto.job_id,
            scene=dto.scene,
            owner=dto.owner or VisualAssetOwnerDTO(app_id="unknown"),
            request=dto.request or VisualAssetGenerateRequest(scene=dto.scene, input=""),
            status=dto.status,
            stage=dto.stage,
            progress=dto.progress,
            message=dto.message,
            design_brief=dto.design_brief,
            assets=dto.assets,
            usage=dto.usage,
            error=dto.error,
            attempt=dto.attempt,
            max_attempts=dto.max_attempts,
            created_at=dto.created_at,
            updated_at=dto.updated_at,
            completed_at=dto.completed_at,
        )


class VisualAssetJobStore:
    def __init__(self, persist_dir: Path | None = None) -> None:
        self._jobs: dict[str, VisualAssetJob] = {}
        self._persist_dir = persist_dir

    def configure_persistence(self, persist_dir: Path | None) -> None:
        self._persist_dir = persist_dir

    def create(self, job: VisualAssetJob) -> VisualAssetJob:
        self._jobs[job.job_id] = job
        self._persist(job)
        return job

    def get(self, job_id: str, *, app_id: str, external_user_id: str | None) -> VisualAssetJob | None:
        job = self._jobs.get(job_id)
        if job is None:
            job = self._load(job_id)
            if job is not None:
                self._jobs[job.job_id] = job
        if job is None:
            return None
        if job.owner.app_id != app_id:
            return None
        if job.owner.external_user_id and external_user_id and job.owner.external_user_id != external_user_id:
            return None
        return job

    def update_state(self, job: VisualAssetJob, *, status: VisualAssetStatus, stage: VisualAssetStage, progress: int, message: str) -> None:
        job.status = status
        job.stage = stage
        job.progress = progress
        job.message = message
        job.updated_at = _now()
        if status in {"succeeded", "failed", "cancelled"}:
            job.completed_at = job.updated_at
        self._persist(job)

    def _job_path(self, job_id: str) -> Path | None:
        if self._persist_dir is None:
            return None
        return self._persist_dir / f"{job_id}.json"

    def _persist(self, job: VisualAssetJob) -> None:
        path = self._job_path(job.job_id)
        if path is None:
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(job.to_dto().model_dump_json(indent=2), encoding="utf-8")

    def _load(self, job_id: str) -> VisualAssetJob | None:
        path = self._job_path(job_id)
        if path is None or not path.exists():
            return None
        dto = VisualAssetJobDTO.model_validate_json(path.read_text(encoding="utf-8"))
        return VisualAssetJob.from_dto(dto)


job_store = VisualAssetJobStore()
