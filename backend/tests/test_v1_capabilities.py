from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.gateway.routers import v1


def test_capabilities_returns_v1_feature_flags():
    app = FastAPI()
    app.include_router(v1.router)

    with TestClient(app) as client:
        response = client.get("/api/v1/capabilities", headers={"X-App-Id": "app", "X-API-Key": "key"})

    assert response.status_code == 200
    body = response.json()
    assert body["conversation"]["streaming"] is True
    assert body["data_sources"]["selected_ids_in_message"] is True
    assert body["visual_assets"]["enabled"] is True
    assert "notebook_icon" in body["visual_assets"]["scenes"]
    assert body["logo"]["image_generate"] is True
    assert body["logo"]["accurate_text_supported"] is False
