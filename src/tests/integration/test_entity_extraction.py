"""
Tests for entity extraction and structured information parsing.
"""
import pytest


@pytest.mark.asyncio
async def test_entity_extraction_basic(test_client, mock_ollama_response):
    """Test that entities are extracted from memories."""
    response = await test_client.post(f"/api/v1/{test_client.test_tenant}/store", json={
        "content": "Sparkle stole pizza from Jeffery in the kitchen"
    })
    
    # Should succeed
    assert response.status_code == 200
    
    # Check stored memory has entities
    search_response = await test_client.post(f"/api/v1/{test_client.test_tenant}/recent", json={
        "hours": 1,
        "limit": 1
    })
    
    # In the future, we'll add entity data to the response
    # For now, this tests that the flow works
    memories = search_response.json()["memories"]
    assert len(memories) == 1


@pytest.mark.asyncio
async def test_entity_type_detection(test_client, mock_ollama_response):
    """Test that entity types are correctly identified."""
    # This will test our custom entity recognition
    memories = [
        ("Sparkle ate her dinner", ["Sparkle"], {"Sparkle": "CAT"}),
        ("Meeting with Jeffery at 3pm", ["Jeffery", "3pm"], {"Jeffery": "PERSON"}),
        ("Debugging Python code", ["Python"], {"Python": "TECH"}),
    ]
    
    for content, expected_entities, expected_types in memories:
        response = await test_client.post(f"/api/v1/{test_client.test_tenant}/store", json={
            "content": content
        })
        assert response.status_code == 200
        
        # Future: Verify entities and types are extracted
        # This requires implementing the feature first


@pytest.mark.asyncio
async def test_action_extraction(test_client, mock_ollama_response):
    """Test that actions are extracted from memories."""
    test_cases = [
        ("Sparkle stole pizza", ["stole"]),
        ("Debugged the async issue", ["debugged"]),
        ("Implemented new feature", ["implemented"]),
    ]
    
    for content, expected_actions in test_cases:
        response = await test_client.post(f"/api/v1/{test_client.test_tenant}/store", json={
            "content": content
        })
        assert response.status_code == 200
        
        # Future: Verify actions are extracted


@pytest.mark.asyncio
async def test_auto_tag_generation(test_client, mock_ollama_response):
    """Test that tags are automatically generated from content."""
    response = await test_client.post(f"/api/v1/{test_client.test_tenant}/store", json={
        "content": "Spent 3 hours debugging Python async code with pytest"
    })
    
    assert response.status_code == 200
    
    # Future: Verify auto-generated tags include relevant terms
    # like "python", "debugging", "async", "pytest"


@pytest.mark.asyncio
async def test_entity_based_search(test_client, mock_ollama_response):
    """Test searching by specific entities."""
    # Store memories with different entities
    await test_client.post(f"/api/v1/{test_client.test_tenant}/store", json={
        "content": "Sparkle knocked over the water bowl"
    })
    await test_client.post(f"/api/v1/{test_client.test_tenant}/store", json={
        "content": "Jeffery fixed the Python bug"  
    })
    await test_client.post(f"/api/v1/{test_client.test_tenant}/store", json={
        "content": "Sparkle slept in the sun"
    })
    
    # Search for all Sparkle memories
    response = await test_client.post(f"/api/v1/{test_client.test_tenant}/search", json={
        "entity": "Sparkle",
        "limit": 10
    })
    
    memories = response.json()["memories"]
    # Should find both Sparkle memories
    sparkle_count = sum(1 for m in memories if "Sparkle" in m)
    assert sparkle_count >= 2
    
    # Should not find Jeffery memory
    jeffery_count = sum(1 for m in memories if "Jeffery" in m)
    assert jeffery_count == 0