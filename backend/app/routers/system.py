"""System configuration routes - LLM config, health check."""

from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional

from app.schemas.common import ApiResponse
from app.llm.client import llm_client
from app.services.graph_manager import graph_manager
from app.config import settings

router = APIRouter(prefix="/api/v1/system", tags=["System"])


class LLMConfig(BaseModel):
    api_key: str
    base_url: str
    model_name: str
    temperature: Optional[float] = 0.1
    max_tokens: Optional[int] = 4096


@router.get("/config")
async def get_config():
    """Get current system configuration (API key masked)."""
    has_key = bool(settings.LLM_API_KEY and len(settings.LLM_API_KEY) > 4)
    masked_key = settings.LLM_API_KEY[:8] + "****" if len(settings.LLM_API_KEY) > 8 else "****"
    return ApiResponse(data={
        "llm": {
            "api_key": masked_key,
            "base_url": settings.LLM_BASE_URL,
            "model_name": settings.LLM_MODEL_NAME,
            "temperature": settings.LLM_TEMPERATURE,
            "max_tokens": settings.LLM_MAX_TOKENS,
            "is_configured": has_key,
        },
        "neo4j": {
            "uri": settings.NEO4J_URI,
            "database": settings.NEO4J_DATABASE,
        },
    })


@router.put("/config/llm")
async def update_llm_config(config: LLMConfig):
    """Update LLM configuration at runtime."""
    llm_client.refresh_client(
        api_key=config.api_key,
        base_url=config.base_url,
        model=config.model_name,
    )
    # Update settings in memory (not persisted to .env)
    settings.LLM_API_KEY = config.api_key
    settings.LLM_BASE_URL = config.base_url
    settings.LLM_MODEL_NAME = config.model_name
    if config.temperature is not None:
        settings.LLM_TEMPERATURE = config.temperature
    if config.max_tokens is not None:
        settings.LLM_MAX_TOKENS = config.max_tokens

    return ApiResponse(message="LLM configuration updated")


@router.post("/config/llm/test")
async def test_llm_connection():
    """Test LLM connectivity."""
    result = await llm_client.test_connection()
    return ApiResponse(data=result)


@router.get("/health")
async def health_check():
    """System health check - Neo4j + LLM connectivity."""
    neo4j_status = await graph_manager.verify_connection()
    llm_status = await llm_client.test_connection()

    overall = "healthy" if (
        neo4j_status.get("status") == "connected"
        and llm_status.get("status") == "connected"
    ) else "degraded"

    return ApiResponse(data={
        "status": overall,
        "neo4j": neo4j_status,
        "llm": llm_status,
    })
