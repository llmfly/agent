from __future__ import annotations

from app.gateway.schemas.v1.visual_assets import VisualAssetGenerateRequest, VisualDesignBriefDTO
from app.gateway.services_v1.image_provider import ImagePromptSpec


def _default_size(request: VisualAssetGenerateRequest) -> tuple[int, int]:
    if request.target.width and request.target.height:
        return request.target.width, request.target.height
    if request.scene == "notebook_background":
        return 1024, 576
    return 1024, 1024


def build_image_prompt(request: VisualAssetGenerateRequest, brief: VisualDesignBriefDTO) -> ImagePromptSpec:
    width, height = _default_size(request)
    direction = brief.visual_direction
    style = ", ".join(direction.get("style") or ["minimal", "modern"])
    colors = ", ".join(direction.get("color_palette") or [])
    negative = ", ".join(brief.constraints.get("negative_prompt") or request.options.avoid or ["readable text", "watermark"])
    prompt = (
        f"Create a {style} {request.scene} image. "
        f"Subject: {request.input}. "
        f"Composition: {direction.get('composition', 'clean composition')}. "
        f"Colors: {colors}. "
        "No readable text, no watermark, no clutter."
    )
    return ImagePromptSpec(
        prompt=prompt,
        negative_prompt=negative,
        width=width,
        height=height,
        num_images=request.options.num_images,
        transparent_background=request.target.transparent_background,
        output_format=request.target.output_format,
        seed=request.options.seed,
    )
