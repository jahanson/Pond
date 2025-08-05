"""
Tests for request ID tracking and comprehensive health checks.
"""
import re

import pytest


@pytest.mark.asyncio
async def test_request_id_header_present(test_client, mock_ollama_response):
    """Test that all responses include request ID header."""
    # Test various endpoints
    endpoints = [
        ("POST", f"/api/v1/{test_client.test_tenant}/init", {}),
        ("POST", f"/api/v1/{test_client.test_tenant}/store", {"content": "Test memory"}),
        ("POST", f"/api/v1/{test_client.test_tenant}/search", {"query": "test"}),
        ("POST", f"/api/v1/{test_client.test_tenant}/recent", {"hours": 1}),
        ("GET", "/api/v1/health", None),
    ]

    for method, path, json_data in endpoints:
        if method == "POST":
            response = await test_client.post(path, json=json_data)
        else:
            response = await test_client.get(path)

        # Should have request ID header
        assert "X-Request-ID" in response.headers
        request_id = response.headers["X-Request-ID"]

        # Should be a valid UUID-like format
        assert len(request_id) > 0
        # Basic format check (not strict UUID validation)
        assert re.match(r'^[a-f0-9\-]+$', request_id.lower())


@pytest.mark.asyncio
async def test_request_id_unique(test_client, mock_ollama_response):
    """Test that each request gets a unique ID."""
    # Make multiple requests
    request_ids = []
    for _ in range(5):
        response = await test_client.post(f"/api/v1/{test_client.test_tenant}/store", json={
            "content": "Test memory"
        })
        request_ids.append(response.headers["X-Request-ID"])

    # All IDs should be unique
    assert len(set(request_ids)) == len(request_ids)


@pytest.mark.asyncio
async def test_health_check_comprehensive(test_client):
    """Test that health check returns detailed information."""
    response = await test_client.get("/api/v1/health")
    assert response.status_code == 200

    data = response.json()

    # Basic health info
    assert "status" in data
    assert data["status"] in ["healthy", "degraded", "unhealthy"]
    assert "timestamp" in data

    # Component details (per SPEC)
    assert "components" in data
    components = data["components"]

    # Database component
    assert "database" in components
    assert "status" in components["database"]
    assert "pool_size" in components["database"]
    assert "pool_available" in components["database"]
    assert "response_time_ms" in components["database"]

    # Ollama component
    assert "ollama" in components
    assert "status" in components["ollama"]
    assert "response_time_ms" in components["ollama"]

    # Version and uptime at top level (per SPEC)
    assert "version" in data
    assert "uptime_seconds" in data


@pytest.mark.asyncio
async def test_health_check_degrades_gracefully(test_client):
    """Test health check when components are unhealthy."""
    # This would need mock to simulate unhealthy components
    # For now, just verify the endpoint works
    response = await test_client.get("/api/v1/health")
    assert response.status_code == 200

    # Even if unhealthy, should return valid JSON
    data = response.json()
    assert isinstance(data, dict)


@pytest.mark.asyncio
async def test_health_check_performance(test_client):
    """Test that health check is fast."""
    import time

    start = time.time()
    response = await test_client.get("/api/v1/health")
    duration = time.time() - start

    assert response.status_code == 200
    # Health check should be fast (under 100ms)
    assert duration < 0.1
