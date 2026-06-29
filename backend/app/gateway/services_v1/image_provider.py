from __future__ import annotations

import base64
import os
from dataclasses import dataclass
from typing import Protocol

import httpx


@dataclass(frozen=True)
class ImagePromptSpec:
    prompt: str
    negative_prompt: str
    width: int
    height: int
    num_images: int
    transparent_background: bool = False
    output_format: str = "png"
    seed: int | None = None


@dataclass(frozen=True)
class GeneratedImage:
    bytes: bytes
    mime_type: str
    width: int
    height: int
    provider_asset_id: str


class ImageProvider(Protocol):
    provider_name: str

    async def generate(self, spec: ImagePromptSpec) -> list[GeneratedImage]:
        raise NotImplementedError


class ImageProviderError(RuntimeError):
    def __init__(self, code: str, message: str, *, retryable: bool = False, details: dict | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable
        self.details = details or {}


class ImageProviderNotConfiguredError(ImageProviderError):
    def __init__(self, message: str = "Image provider is not configured") -> None:
        super().__init__("image_provider_not_configured", message, retryable=False)


class OpenAIImageProvider:
    provider_name = "openai"

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = "https://api.openai.com/v1",
        model: str = "gpt-image-1",
        response_format: str | None = "b64_json",
        timeout_seconds: float = 120.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        if not api_key.strip():
            raise ImageProviderNotConfiguredError("Set VISUAL_ASSET_IMAGE_API_KEY or OPENAI_API_KEY to enable visual asset generation")
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._response_format = response_format
        self._timeout = httpx.Timeout(timeout_seconds)
        self._transport = transport

    async def generate(self, spec: ImagePromptSpec) -> list[GeneratedImage]:
        body: dict[str, object] = {
            "model": self._model,
            "prompt": self._merge_prompt(spec),
            "n": spec.num_images,
            "size": f"{spec.width}x{spec.height}",
        }
        if self._response_format:
            body["response_format"] = self._response_format
        if spec.transparent_background:
            body["background"] = "transparent"

        headers = {"Authorization": f"Bearer {self._api_key}"}
        async with httpx.AsyncClient(base_url=self._base_url, timeout=self._timeout, transport=self._transport) as client:
            try:
                response = await client.post("/images/generations", headers=headers, json=body)
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                status_code = exc.response.status_code
                raise ImageProviderError(
                    "image_provider_request_failed",
                    f"Image provider request failed with HTTP {status_code}",
                    retryable=status_code == 429 or status_code >= 500,
                    details={"status_code": status_code, "response": exc.response.text[:500]},
                ) from exc
            except httpx.RequestError as exc:
                raise ImageProviderError("image_provider_unavailable", str(exc), retryable=True) from exc

            payload = response.json()
            data = payload.get("data")
            if not isinstance(data, list) or not data:
                raise ImageProviderError("image_provider_invalid_response", "Image provider response does not contain image data")

            images: list[GeneratedImage] = []
            for index, item in enumerate(data):
                if not isinstance(item, dict):
                    raise ImageProviderError("image_provider_invalid_response", "Image provider returned an invalid image item")
                image_bytes, mime_type = await self._read_image_item(client, item)
                images.append(
                    GeneratedImage(
                        bytes=image_bytes,
                        mime_type=mime_type,
                        width=spec.width,
                        height=spec.height,
                        provider_asset_id=str(item.get("id") or f"openai_{index + 1}"),
                    )
                )
            return images

    def _merge_prompt(self, spec: ImagePromptSpec) -> str:
        if not spec.negative_prompt:
            return spec.prompt
        return f"{spec.prompt}\n\nAvoid: {spec.negative_prompt}"

    async def _read_image_item(self, client: httpx.AsyncClient, item: dict) -> tuple[bytes, str]:
        b64_json = item.get("b64_json")
        if isinstance(b64_json, str) and b64_json:
            try:
                return base64.b64decode(b64_json), "image/png"
            except ValueError as exc:
                raise ImageProviderError("image_provider_invalid_response", "Image provider returned invalid base64 image data") from exc

        url = item.get("url")
        if isinstance(url, str) and url:
            try:
                response = await client.get(url)
                response.raise_for_status()
            except httpx.HTTPError as exc:
                raise ImageProviderError("image_provider_download_failed", "Failed to download generated image", retryable=True) from exc
            return response.content, response.headers.get("content-type", "image/png").split(";")[0]

        raise ImageProviderError("image_provider_invalid_response", "Image provider returned neither b64_json nor url")


class ExternalGenerateImageProvider:
    provider_name = "external-generate"

    def __init__(
        self,
        *,
        endpoint_url: str,
        timeout_seconds: float = 180.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        if not endpoint_url.strip():
            raise ImageProviderNotConfiguredError("Set VISUAL_ASSET_EXTERNAL_IMAGE_URL to enable external visual asset generation")
        self._endpoint_url = endpoint_url
        self._timeout = httpx.Timeout(timeout_seconds)
        self._transport = transport

    async def generate(self, spec: ImagePromptSpec) -> list[GeneratedImage]:
        images: list[GeneratedImage] = []
        prompt = self._merge_prompt(spec)
        async with httpx.AsyncClient(timeout=self._timeout, transport=self._transport) as client:
            while len(images) < spec.num_images:
                body: dict[str, object] = {"prompt": prompt}
                if spec.seed is not None:
                    body["seed"] = spec.seed + len(images)

                try:
                    response = await client.post(self._endpoint_url, json=body)
                    response.raise_for_status()
                except httpx.HTTPStatusError as exc:
                    status_code = exc.response.status_code
                    raise ImageProviderError(
                        "image_provider_request_failed",
                        f"Image provider request failed with HTTP {status_code}",
                        retryable=status_code == 429 or status_code >= 500,
                        details={"status_code": status_code, "response": exc.response.text[:500]},
                    ) from exc
                except httpx.RequestError as exc:
                    raise ImageProviderError("image_provider_unavailable", str(exc), retryable=True) from exc

                payload = response.json()
                returned_images = payload.get("images")
                if not isinstance(returned_images, list) or not returned_images:
                    raise ImageProviderError("image_provider_invalid_response", "Image provider response does not contain images")

                for item in returned_images:
                    if not isinstance(item, dict):
                        raise ImageProviderError("image_provider_invalid_response", "Image provider returned an invalid image item")
                    image_bytes, mime_type = await self._read_image_item(client, item)
                    images.append(
                        GeneratedImage(
                            bytes=image_bytes,
                            mime_type=mime_type,
                            width=spec.width,
                            height=spec.height,
                            provider_asset_id=f"external_{len(images)}",
                        )
                    )
                    if len(images) >= spec.num_images:
                        break
        return images

    def _merge_prompt(self, spec: ImagePromptSpec) -> str:
        if not spec.negative_prompt:
            return spec.prompt
        return f"{spec.prompt}\n\nAvoid: {spec.negative_prompt}"

    async def _read_image_item(self, client: httpx.AsyncClient, item: dict) -> tuple[bytes, str]:
        b64_value = item.get("base64")
        if isinstance(b64_value, str) and b64_value:
            if "," in b64_value and b64_value.lstrip().startswith("data:"):
                b64_value = b64_value.split(",", 1)[1]
            try:
                return base64.b64decode(b64_value), "image/png"
            except ValueError as exc:
                raise ImageProviderError("image_provider_invalid_response", "Image provider returned invalid base64 image data") from exc

        url = item.get("url")
        if isinstance(url, str) and url:
            try:
                response = await client.get(url)
                response.raise_for_status()
            except httpx.HTTPError as exc:
                raise ImageProviderError("image_provider_download_failed", "Failed to download generated image", retryable=True) from exc
            return response.content, response.headers.get("content-type", "image/png").split(";")[0]

        raise ImageProviderError("image_provider_invalid_response", "Image provider returned neither base64 nor url")


def create_image_provider_from_env() -> ImageProvider:
    provider = os.getenv("VISUAL_ASSET_IMAGE_PROVIDER", "openai").strip().lower()
    if provider == "external-generate":
        return ExternalGenerateImageProvider(
            endpoint_url=os.getenv("VISUAL_ASSET_EXTERNAL_IMAGE_URL", ""),
            timeout_seconds=float(os.getenv("VISUAL_ASSET_IMAGE_TIMEOUT_SECONDS", "180")),
        )

    if provider not in {"openai", "openai-compatible"}:
        raise ImageProviderNotConfiguredError(f"Unsupported VISUAL_ASSET_IMAGE_PROVIDER={provider!r}; configure openai, openai-compatible, or external-generate")

    api_key = os.getenv("VISUAL_ASSET_IMAGE_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ImageProviderNotConfiguredError("Set VISUAL_ASSET_IMAGE_API_KEY or OPENAI_API_KEY to enable visual asset generation")

    response_format = os.getenv("VISUAL_ASSET_IMAGE_RESPONSE_FORMAT", "b64_json").strip() or None
    return OpenAIImageProvider(
        api_key=api_key,
        base_url=os.getenv("VISUAL_ASSET_IMAGE_BASE_URL") or os.getenv("OPENAI_BASE_URL") or os.getenv("OPENAI_API_BASE") or "https://api.openai.com/v1",
        model=os.getenv("VISUAL_ASSET_IMAGE_MODEL", "gpt-image-1"),
        response_format=response_format,
        timeout_seconds=float(os.getenv("VISUAL_ASSET_IMAGE_TIMEOUT_SECONDS", "120")),
    )
