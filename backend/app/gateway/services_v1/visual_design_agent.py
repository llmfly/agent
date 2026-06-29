from __future__ import annotations

from app.gateway.schemas.v1.visual_assets import VisualAssetGenerateRequest, VisualDesignBriefDTO


def build_design_brief(request: VisualAssetGenerateRequest) -> VisualDesignBriefDTO:
    style = request.options.style or ["minimal", "modern"]
    avoid = request.options.avoid or ["readable text", "watermark", "busy details"]
    width = request.target.width or 1024
    height = request.target.height or 1024
    return VisualDesignBriefDTO(
        title=f"{request.scene} visual asset",
        scene=request.scene,
        intent=f"Generate a {request.scene} visual asset from the user's semantic description.",
        subject={"name": request.input[:120], "keywords": style},
        audience={"tone": style},
        visual_direction={
            "style": style,
            "symbol_ideas": ["clean abstract symbol"],
            "composition": "clear composition suitable for the requested usage",
            "color_palette": request.options.color_preferences or ["blue", "white", "silver"],
        },
        constraints={
            "aspect_ratio": request.target.aspect_ratio or f"{width}:{height}",
            "avoid_text": True,
            "transparent_background": request.target.transparent_background,
            "negative_prompt": avoid,
        },
    )
