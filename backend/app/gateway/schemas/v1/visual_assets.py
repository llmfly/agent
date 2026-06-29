from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

VisualAssetScene = Literal["logo", "notebook_icon", "notebook_background", "cover_image", "general_image"]
VisualAssetStatus = Literal["queued", "running", "succeeded", "failed", "cancelled"]
VisualAssetStage = Literal["queued", "analyzing", "prompting", "generating", "storing", "succeeded", "failed", "cancelled"]


class VisualAssetTarget(BaseModel):
    usage: str | None = None
    aspect_ratio: str | None = None
    width: int | None = None
    height: int | None = None
    transparent_background: bool = False
    output_format: Literal["png"] = "png"


class VisualAssetOptions(BaseModel):
    num_images: int = Field(default=4, ge=1, le=4)
    style: list[str] = Field(default_factory=list)
    color_preferences: list[str] = Field(default_factory=list)
    avoid: list[str] = Field(default_factory=list)
    quality: Literal["draft", "standard", "high"] = "standard"
    seed: int | None = None


class VisualAssetGenerateRequest(BaseModel):
    scene: VisualAssetScene
    input: str = Field(min_length=1, max_length=4000)
    target: VisualAssetTarget = Field(default_factory=VisualAssetTarget)
    options: VisualAssetOptions = Field(default_factory=VisualAssetOptions)
    metadata: dict[str, Any] = Field(default_factory=dict)


class VisualAssetSimpleGenerateRequest(BaseModel):
    scene: VisualAssetScene
    prompt: str = Field(min_length=1, max_length=4000)
    usage: str | None = None
    aspect_ratio: str | None = None
    width: int | None = None
    height: int | None = None
    transparent_background: bool = False
    num_images: int = Field(default=1, ge=1, le=4)
    style: list[str] = Field(default_factory=list)
    color_preferences: list[str] = Field(default_factory=list)
    avoid: list[str] = Field(default_factory=list)
    quality: Literal["draft", "standard", "high"] = "standard"
    seed: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    def to_generate_request(self) -> VisualAssetGenerateRequest:
        return VisualAssetGenerateRequest(
            scene=self.scene,
            input=self.prompt,
            target=VisualAssetTarget(
                usage=self.usage,
                aspect_ratio=self.aspect_ratio,
                width=self.width,
                height=self.height,
                transparent_background=self.transparent_background,
            ),
            options=VisualAssetOptions(
                num_images=self.num_images,
                style=self.style,
                color_preferences=self.color_preferences,
                avoid=self.avoid,
                quality=self.quality,
                seed=self.seed,
            ),
            metadata=self.metadata,
        )


class VisualAssetOwnerDTO(BaseModel):
    app_id: str
    external_user_id: str | None = None


class VisualDesignBriefDTO(BaseModel):
    title: str
    scene: VisualAssetScene
    intent: str
    subject: dict[str, Any] = Field(default_factory=dict)
    audience: dict[str, Any] = Field(default_factory=dict)
    visual_direction: dict[str, Any] = Field(default_factory=dict)
    constraints: dict[str, Any] = Field(default_factory=dict)


class VisualAssetReviewDTO(BaseModel):
    status: str = "not_reviewed"
    score: float | None = None
    issues: list[dict[str, Any]] = Field(default_factory=list)


class VisualAssetDTO(BaseModel):
    asset_id: str
    artifact_id: str
    status: str = "ready"
    kind: str = "image"
    scene: VisualAssetScene
    usage: str
    mime_type: str
    width: int
    height: int
    preview_url: str
    download_url: str
    selected: bool = False
    review: VisualAssetReviewDTO = Field(default_factory=VisualAssetReviewDTO)


class VisualAssetUsageDTO(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    image_count: int = 0
    provider: str = "openai"


class VisualAssetErrorDTO(BaseModel):
    code: str
    message: str
    retryable: bool = False
    details: dict[str, Any] = Field(default_factory=dict)


class VisualAssetJobDTO(BaseModel):
    job_id: str
    type: str = "visual_asset_generation"
    scene: VisualAssetScene
    status: VisualAssetStatus
    stage: VisualAssetStage
    progress: int
    message: str
    owner: VisualAssetOwnerDTO | None = None
    request: VisualAssetGenerateRequest | None = None
    design_brief: VisualDesignBriefDTO | None = None
    assets: list[VisualAssetDTO] = Field(default_factory=list)
    usage: VisualAssetUsageDTO = Field(default_factory=VisualAssetUsageDTO)
    error: VisualAssetErrorDTO | None = None
    attempt: int = 1
    max_attempts: int = 2
    created_at: str
    updated_at: str
    completed_at: str | None = None


class VisualAssetCreateResponse(BaseModel):
    job_id: str
    status: VisualAssetStatus
    stage: VisualAssetStage
    progress: int
    scene: VisualAssetScene
    message: str
    created_at: str


class VisualAssetSimpleCreateResponse(BaseModel):
    job_id: str
    status: VisualAssetStatus
    progress: int
    message: str
    created_at: str


class VisualAssetSimpleAssetDTO(BaseModel):
    asset_id: str
    preview_url: str
    download_url: str
    width: int
    height: int


class VisualAssetSimpleErrorDTO(BaseModel):
    code: str
    message: str


class VisualAssetSimpleJobDTO(BaseModel):
    job_id: str
    status: VisualAssetStatus
    progress: int
    message: str
    assets: list[VisualAssetSimpleAssetDTO] = Field(default_factory=list)
    error: VisualAssetSimpleErrorDTO | None = None


class VisualAssetCancelRequest(BaseModel):
    reason: str | None = None


class VisualAssetCancelResponse(BaseModel):
    job_id: str
    status: VisualAssetStatus
    stage: VisualAssetStage
    progress: int
    message: str
