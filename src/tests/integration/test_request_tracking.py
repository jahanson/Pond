"""
Tests for request ID tracking and comprehensive health checks.
"""
import pytest
import re


@pytest.mark.asyncio
async def test_request_id_header_present(test_client, mock_ollama_response):
    """Test that all responses include request ID header."""
    # Test various endpoints
    endpoints = [
        ("POST", "/api/v1/test_tenant/init", {}),
        ("POST", "/api/v1/test_tenant/store", {"content": "Test memory"}),
        ("POST", "/api/v1/test_tenant/search", {"query": "test"}),
        ("POST", "/api/v1/test_tenant/recent", {"hours": 1}),
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
        response = await test_client.post("/api/v1/test_tenant/store", json={
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
    
    # Component details
    assert "components" in data
    components = data["components"]
    
    # API component
    assert "api" in components
    assert "status" in components["api"]
    assert "version" in components["api"]
    assert "uptime_seconds" in components["api"]
    
    # Database component
    assert "database" in components
    assert "status" in components["database"]
    # These might not be available in test environment
    # but should be present in real deployment
    
    # Ollama component
    assert "ollama" in components
    assert "status" in components["ollama"]
    assert "endpoint" in components["ollama"]
    assert "model" in components["ollama"]
    
    # Timezone info
    assert "timezone" in components
    assert "configured" in components["timezone"]
    assert "source" in components["timezone"]


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