import base64
import json

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.gateway.routers import v1
from app.gateway.schemas.v1.visual_assets import VisualAssetGenerateRequest, VisualAssetOwnerDTO
from app.gateway.services_v1.image_provider import ExternalGenerateImageProvider, GeneratedImage, ImagePromptSpec, OpenAIImageProvider
from app.gateway.services_v1.visual_asset_job_store import VisualAssetJob, VisualAssetJobStore

_PNG_BYTES = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII=")


class StaticImageProvider:
    provider_name = "test-static"

    async def generate(self, spec: ImagePromptSpec) -> list[GeneratedImage]:
        return [
            GeneratedImage(
                bytes=_PNG_BYTES,
                mime_type="image/png",
                width=spec.width,
                height=spec.height,
                provider_asset_id=f"test_{index + 1}",
            )
            for index in range(spec.num_images)
        ]


class CapturingImageProvider(StaticImageProvider):
    provider_name = "test-capturing"

    def __init__(self) -> None:
        self.specs: list[ImagePromptSpec] = []

    async def generate(self, spec: ImagePromptSpec) -> list[GeneratedImage]:
        self.specs.append(spec)
        return await super().generate(spec)


def _app_with_visual_provider(tmp_path=None) -> FastAPI:
    app = FastAPI()
    if tmp_path is not None:
        app.state.v1_artifact_base_dir = tmp_path
        app.state.v1_visual_asset_job_dir = tmp_path / "jobs"
    app.state.v1_image_provider = StaticImageProvider()
    app.include_router(v1.router)
    return app


def _headers():
    return {"X-App-Id": "notebook-app", "X-API-Key": "dev-key", "X-User-Id": "user-1", "X-Request-Id": "req-1"}


def _other_headers():
    return {"X-App-Id": "notebook-app", "X-API-Key": "dev-key", "X-User-Id": "user-2", "X-Request-Id": "req-2"}


def test_visual_asset_generate_creates_async_job_and_artifacts(tmp_path):
    app = _app_with_visual_provider(tmp_path)

    with TestClient(app) as client:
        created = client.post(
            "/api/v1/ai/visual-assets/generate",
            headers=_headers(),
            json={
                "scene": "notebook_icon",
                "input": "AI product design methodology notebook",
                "target": {"usage": "notebook_icon", "width": 1024, "height": 1024},
                "options": {"num_images": 2, "style": ["minimal", "tech"]},
                "metadata": {"notebook_id": "nb-1"},
            },
        )

        assert created.status_code == 202, created.text
        job_id = created.json()["job_id"]
        assert created.json()["status"] == "queued"
        assert created.json()["progress"] == 0
        assert (app.state.v1_visual_asset_job_dir / f"{job_id}.json").exists()

        job = client.get(f"/api/v1/ai/visual-assets/jobs/{job_id}", headers=_headers())
        assert job.status_code == 200, job.text
        body = job.json()
        assert body["status"] == "succeeded"
        assert body["progress"] == 100
        assert body["design_brief"]["scene"] == "notebook_icon"
        assert body["usage"]["provider"] == "test-static"
        assert len(body["assets"]) == 2
        assert body["assets"][0]["artifact_id"].startswith("art_")
        assert body["assets"][0]["preview_url"].endswith("/preview")
        assert body["assets"][0]["download_url"].endswith("/download")

        artifact_id = body["assets"][0]["artifact_id"]
        metadata = client.get(f"/api/v1/artifacts/{artifact_id}", headers=_headers())
        assert metadata.status_code == 200, metadata.text
        assert metadata.json()["artifact_id"] == artifact_id
        assert metadata.json()["metadata"]["notebook_id"] == "nb-1"

        preview = client.get(f"/api/v1/artifacts/{artifact_id}/preview", headers=_headers())
        assert preview.status_code == 200, preview.text
        assert preview.headers["content-type"] == "image/png"


def test_visual_asset_generate_passes_seed_to_image_provider(tmp_path):
    provider = CapturingImageProvider()
    app = FastAPI()
    app.state.v1_artifact_base_dir = tmp_path
    app.state.v1_visual_asset_job_dir = tmp_path / "jobs"
    app.state.v1_image_provider = provider
    app.include_router(v1.router)

    with TestClient(app) as client:
        created = client.post(
            "/api/v1/ai/visual-assets/generate",
            headers=_headers(),
            json={
                "scene": "notebook_icon",
                "input": "Seeded notebook icon",
                "options": {"num_images": 1, "seed": 7},
            },
        )

    assert created.status_code == 202, created.text
    assert len(provider.specs) == 1
    assert provider.specs[0].seed == 7


def test_visual_asset_simple_generate_accepts_flat_request_and_returns_compact_create_response(tmp_path):
    provider = CapturingImageProvider()
    app = FastAPI()
    app.state.v1_artifact_base_dir = tmp_path
    app.state.v1_visual_asset_job_dir = tmp_path / "jobs"
    app.state.v1_image_provider = provider
    app.include_router(v1.router)

    with TestClient(app) as client:
        created = client.post(
            "/api/v1/ai/visual-assets/simple/generate",
            headers=_headers(),
            json={
                "scene": "notebook_icon",
                "prompt": "AI product design methodology notebook",
                "num_images": 2,
                "style": ["minimal", "tech"],
                "width": 512,
                "height": 512,
                "metadata": {"notebook_id": "nb-1"},
            },
        )

    assert created.status_code == 202, created.text
    assert set(created.json()) == {"job_id", "status", "progress", "message", "created_at"}
    assert created.json()["status"] == "queued"
    assert len(provider.specs) == 1
    assert provider.specs[0].num_images == 2
    assert provider.specs[0].width == 512
    assert provider.specs[0].height == 512


def test_visual_asset_simple_job_returns_compact_progress_and_assets(tmp_path):
    app = _app_with_visual_provider(tmp_path)

    with TestClient(app) as client:
        created = client.post(
            "/api/v1/ai/visual-assets/simple/generate",
            headers=_headers(),
            json={"scene": "notebook_icon", "prompt": "Knowledge base notebook", "num_images": 1},
        )
        job_id = created.json()["job_id"]

        job = client.get(f"/api/v1/ai/visual-assets/simple/jobs/{job_id}", headers=_headers())

    assert job.status_code == 200, job.text
    body = job.json()
    assert set(body) == {"job_id", "status", "progress", "message", "assets", "error"}
    assert body["job_id"] == job_id
    assert body["status"] == "succeeded"
    assert body["progress"] == 100
    assert body["error"] is None
    assert len(body["assets"]) == 1
    assert set(body["assets"][0]) == {"asset_id", "preview_url", "download_url", "width", "height"}
    assert body["assets"][0]["preview_url"].endswith("/preview")
    assert body["assets"][0]["download_url"].endswith("/download")


def test_visual_asset_preview_survives_in_memory_artifact_index_miss(tmp_path):
    app = _app_with_visual_provider(tmp_path)

    with TestClient(app) as client:
        created = client.post(
            "/api/v1/ai/visual-assets/simple/generate",
            headers=_headers(),
            json={"scene": "notebook_icon", "prompt": "Recoverable notebook icon", "num_images": 1},
        )
        job_id = created.json()["job_id"]
        job = client.get(f"/api/v1/ai/visual-assets/jobs/{job_id}", headers=_headers())
        artifact_id = job.json()["assets"][0]["artifact_id"]

        from app.gateway.routers.v1 import artifacts as artifacts_router
        from app.gateway.services_v1 import artifact_service

        artifacts_router._artifact_registry.clear()
        artifact_service._artifacts.clear()

        preview = client.get(f"/api/v1/artifacts/{artifact_id}/preview", headers=_headers())

    assert preview.status_code == 200, preview.text
    assert preview.headers["content-type"] == "image/png"


def test_visual_asset_generate_fails_when_real_provider_is_not_configured(monkeypatch, tmp_path):
    monkeypatch.delenv("VISUAL_ASSET_IMAGE_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    app = FastAPI()
    app.state.v1_artifact_base_dir = tmp_path
    app.state.v1_visual_asset_job_dir = tmp_path / "jobs"
    app.include_router(v1.router)

    with TestClient(app) as client:
        created = client.post(
            "/api/v1/ai/visual-assets/generate",
            headers=_headers(),
            json={"scene": "notebook_icon", "input": "Knowledge base notebook", "options": {"num_images": 1}},
        )
        assert created.status_code == 202, created.text
        job_id = created.json()["job_id"]

        job = client.get(f"/api/v1/ai/visual-assets/jobs/{job_id}", headers=_headers())

    assert job.status_code == 200, job.text
    body = job.json()
    assert body["status"] == "failed"
    assert body["stage"] == "failed"
    assert body["progress"] == 100
    assert body["error"]["code"] == "image_provider_not_configured"
    assert body["usage"]["provider"] != "mock"


@pytest.mark.asyncio
async def test_openai_image_provider_posts_prompt_and_decodes_base64_image():
    requests: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(json.loads(request.content.decode("utf-8")))
        return httpx.Response(200, json={"data": [{"b64_json": base64.b64encode(_PNG_BYTES).decode("ascii")}], "usage": {"total_tokens": 12}})

    provider = OpenAIImageProvider(
        api_key="test-key",
        base_url="https://image-provider.example/v1",
        model="gpt-image-1",
        transport=httpx.MockTransport(handler),
    )

    images = await provider.generate(
        ImagePromptSpec(
            prompt="minimal notebook icon",
            negative_prompt="avoid text",
            width=1024,
            height=1024,
            num_images=1,
            transparent_background=True,
        )
    )

    assert requests == [
        {
            "model": "gpt-image-1",
            "prompt": "minimal notebook icon\n\nAvoid: avoid text",
            "n": 1,
            "size": "1024x1024",
            "response_format": "b64_json",
            "background": "transparent",
        }
    ]
    assert len(images) == 1
    assert images[0].bytes == _PNG_BYTES
    assert images[0].mime_type == "image/png"
    assert images[0].provider_asset_id == "openai_1"


@pytest.mark.asyncio
async def test_external_generate_image_provider_posts_prompt_seed_and_decodes_base64_images():
    requests: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(json.loads(request.content.decode("utf-8")))
        return httpx.Response(
            200,
            json={
                "images": [
                    {
                        "index": 0,
                        "url": f"http://image-provider.example/images/{len(requests)}.png",
                        "base64": base64.b64encode(_PNG_BYTES).decode("ascii"),
                    }
                ],
                "prompt": "minimal notebook icon",
                "time_seconds": 1.5,
            },
        )

    provider = ExternalGenerateImageProvider(
        endpoint_url="http://image-provider.example/generate",
        transport=httpx.MockTransport(handler),
    )

    images = await provider.generate(
        ImagePromptSpec(
            prompt="minimal notebook icon",
            negative_prompt="avoid text",
            width=1024,
            height=1024,
            num_images=2,
            seed=7,
        )
    )

    assert requests == [
        {"prompt": "minimal notebook icon\n\nAvoid: avoid text", "seed": 7},
        {"prompt": "minimal notebook icon\n\nAvoid: avoid text", "seed": 8},
    ]
    assert len(images) == 2
    assert images[0].bytes == _PNG_BYTES
    assert images[0].mime_type == "image/png"
    assert images[0].width == 1024
    assert images[0].height == 1024
    assert images[0].provider_asset_id == "external_0"


def test_visual_asset_cancel_queued_job():
    app = _app_with_visual_provider()

    with TestClient(app) as client:
        created = client.post(
            "/api/v1/ai/visual-assets/generate",
            headers=_headers(),
            json={"scene": "notebook_background", "input": "A calm project planning notebook"},
        )
        job_id = created.json()["job_id"]

        cancelled = client.post(
            f"/api/v1/ai/visual-assets/jobs/{job_id}/cancel",
            headers=_headers(),
            json={"reason": "user_cancelled"},
        )

    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["job_id"] == job_id
    assert cancelled.json()["status"] in {"cancelled", "succeeded"}


def test_visual_asset_artifact_can_be_pinned_and_unpinned(tmp_path):
    app = _app_with_visual_provider(tmp_path)

    with TestClient(app) as client:
        created = client.post(
            "/api/v1/ai/visual-assets/generate",
            headers=_headers(),
            json={"scene": "notebook_icon", "input": "Knowledge base notebook", "options": {"num_images": 1}},
        )
        job_id = created.json()["job_id"]
        job = client.get(f"/api/v1/ai/visual-assets/jobs/{job_id}", headers=_headers())
        artifact_id = job.json()["assets"][0]["artifact_id"]

        pinned = client.post(f"/api/v1/artifacts/{artifact_id}/pin", headers=_headers())
        assert pinned.status_code == 200, pinned.text
        assert pinned.json()["artifact_id"] == artifact_id
        assert pinned.json()["pinned"] is True

        metadata = client.get(f"/api/v1/artifacts/{artifact_id}", headers=_headers())
        assert metadata.status_code == 200, metadata.text
        assert metadata.json()["pinned"] is True

        unpinned = client.post(f"/api/v1/artifacts/{artifact_id}/unpin", headers=_headers())
        assert unpinned.status_code == 200, unpinned.text
        assert unpinned.json()["artifact_id"] == artifact_id
        assert unpinned.json()["pinned"] is False

        metadata = client.get(f"/api/v1/artifacts/{artifact_id}", headers=_headers())
        assert metadata.status_code == 200, metadata.text
        assert metadata.json()["pinned"] is False


def test_visual_asset_artifact_isolated_by_external_user(tmp_path):
    app = _app_with_visual_provider(tmp_path)

    with TestClient(app) as client:
        created = client.post(
            "/api/v1/ai/visual-assets/generate",
            headers=_headers(),
            json={"scene": "notebook_icon", "input": "Private notebook", "options": {"num_images": 1}},
        )
        job_id = created.json()["job_id"]
        job = client.get(f"/api/v1/ai/visual-assets/jobs/{job_id}", headers=_headers())
        artifact_id = job.json()["assets"][0]["artifact_id"]

        other_job = client.get(f"/api/v1/ai/visual-assets/jobs/{job_id}", headers=_other_headers())
        assert other_job.status_code == 404, other_job.text

        other_metadata = client.get(f"/api/v1/artifacts/{artifact_id}", headers=_other_headers())
        assert other_metadata.status_code == 404, other_metadata.text

        other_preview = client.get(f"/api/v1/artifacts/{artifact_id}/preview", headers=_other_headers())
        assert other_preview.status_code == 404, other_preview.text

        other_pin = client.post(f"/api/v1/artifacts/{artifact_id}/pin", headers=_other_headers())
        assert other_pin.status_code == 404, other_pin.text


def test_visual_asset_job_store_can_reload_job_from_disk(tmp_path):
    job = VisualAssetJob(
        job_id="job_visual_disk_001",
        scene="notebook_icon",
        owner=VisualAssetOwnerDTO(app_id="notebook-app", external_user_id="user-1"),
        request=VisualAssetGenerateRequest(scene="notebook_icon", input="Persistent notebook icon"),
    )
    store = VisualAssetJobStore(persist_dir=tmp_path)

    store.create(job)
    store.update_state(job, status="running", stage="generating", progress=50, message="generating")

    reloaded_store = VisualAssetJobStore(persist_dir=tmp_path)
    reloaded = reloaded_store.get("job_visual_disk_001", app_id="notebook-app", external_user_id="user-1")

    assert reloaded is not None
    assert reloaded.job_id == "job_visual_disk_001"
    assert reloaded.status == "running"
    assert reloaded.stage == "generating"
    assert reloaded.progress == 50
    assert reloaded.request.input == "Persistent notebook icon"
