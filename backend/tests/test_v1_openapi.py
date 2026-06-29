from app.gateway.app import create_app


def test_openapi_includes_v1_routes():
    app = create_app()
    schema = app.openapi()

    assert "/api/v1/conversations" in schema["paths"]
    assert "/api/v1/agents" in schema["paths"]
    assert "/api/v1/capabilities" in schema["paths"]
    assert "/api/v1/ai/visual-assets/generate" in schema["paths"]
    assert "/api/v1/ai/visual-assets/simple/generate" in schema["paths"]
    assert "/api/v1/ai/visual-assets/jobs/{job_id}" in schema["paths"]
    assert "/api/v1/ai/visual-assets/simple/jobs/{job_id}" in schema["paths"]
    assert "/api/v1/artifacts/{artifact_id}/preview" in schema["paths"]
    assert "/api/v1/artifacts/{artifact_id}/pin" in schema["paths"]
    assert "/api/v1/artifacts/{artifact_id}/unpin" in schema["paths"]
