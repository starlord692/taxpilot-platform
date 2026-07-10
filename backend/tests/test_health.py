"""Health endpoint tests."""

from fastapi.testclient import TestClient

from app.main import create_app

HTTP_OK = 200


def test_health_endpoint() -> None:
    """Health endpoint returns the expected response envelope."""
    with TestClient(create_app(initialize_resources=False)) as client:
        response = client.get("/api/v1/health")

    assert response.status_code == HTTP_OK
    assert response.json() == {
        "success": True,
        "message": "TaxPilot API is healthy",
        "data": {
            "status": "UP",
            "version": "1.0.0",
            "environment": "development",
        },
    }
