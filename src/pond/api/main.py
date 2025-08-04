"""Main FastAPI application."""
from fastapi import FastAPI

app = FastAPI(
    title="Pond",
    description="Semantic memory system for AI assistants",
    version="0.1.0",
)
