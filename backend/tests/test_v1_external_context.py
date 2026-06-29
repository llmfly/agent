from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.gateway.routers import v1
from app.gateway.services_v1.external_context import build_external_metadata, get_external_context


def test_external_context_requires_app_id_and_api_key():
    app = FastAPI()
    app.include_router(v1.router)

    with TestClient(app) as client:
        response = client.get("/api/v1/capabilities")

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "UNAUTHORIZED"


def test_external_context_reads_headers_and_merges_metadata():
    app = FastAPI()

    @app.get("/ctx")
    async def ctx(context=Depends(get_external_context)):  # type: ignore[name-defined]
        return build_external_metadata(context, {"project_id": "p1"})

    with TestClient(app) as client:
        response = client.get(
            "/ctx",
            headers={
                "X-App-Id": "external-app",
                "X-API-Key": "secret",
                "X-Request-Id": "req-1",
                "X-User-Id": "u-1",
            },
        )

    assert response.status_code == 200
    assert response.json() == {
        "project_id": "p1",
        "app_id": "external-app",
        "external_user_id": "u-1",
        "request_id": "req-1",
    }
