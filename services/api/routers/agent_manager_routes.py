"""
FastAPI Routes for Agent Manager
--------------------------------

Endpoints:
    POST /agent/run - Execute any agent task
    GET /agent/health - Health check and model status
"""

import logging
import time
from typing import Any, Dict, Optional
from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel, Field

from services.api.agent_manager import get_agent_manager

logger = logging.getLogger(__name__)

router = APIRouter()

# Get singleton manager instance
manager = get_agent_manager()


# Request/Response Models
class AgentRunRequest(BaseModel):
    """Request model for /agent/run endpoint."""
    task: str = Field(..., description="Task type: generate, summarize, qa, embedding, translate, caption, classify")
    engine: Optional[str] = Field(None, description="Force specific engine: local, ollama, hf_api (auto-selects if None)")
    payload: Dict[str, Any] = Field(default_factory=dict, description="Task-specific parameters")


class AgentRunResponse(BaseModel):
    """Response model for /agent/run endpoint."""
    result: Any = Field(None, description="Task result")
    source: str = Field(..., description="Engine used: local, ollama, hf_api, hf_pipeline, etc.")
    latency: float = Field(..., description="Execution time in seconds")
    task: str = Field(..., description="Task that was executed")
    error: Optional[str] = Field(None, description="Error message if task failed")


class AgentHealthResponse(BaseModel):
    """Response model for /agent/health endpoint."""
    status: str = Field(..., description="Overall status")
    models_loaded: Dict[str, bool] = Field(..., description="Status of each model engine")
    device: str = Field(..., description="Device being used (cpu/cuda)")
    available_tasks: list = Field(..., description="List of supported tasks")


@router.post("/run", response_model=AgentRunResponse)
async def run_agent(request: AgentRunRequest = Body(...)):
    """
    Execute an agent task.
    
    Examples:
        POST /agent/run
        {
            "task": "generate",
            "payload": {"prompt": "Hello world", "max_new_tokens": 100}
        }
        
        POST /agent/run
        {
            "task": "summarize",
            "payload": {"text": "Long document text..."}
        }
        
        POST /agent/run
        {
            "task": "qa",
            "payload": {"question": "What is this?", "context": "..."}
        }
    """
    start_time = time.time()
    
    try:
        # Log request
        logger.info(
            f"Agent run request: task={request.task}, engine={request.engine}, "
            f"payload_keys={list(request.payload.keys())}"
        )
        
        # Execute task
        result = manager.run(
            task=request.task,
            engine=request.engine,
            **request.payload
        )
        
        # Log result
        latency = time.time() - start_time
        logger.info(
            f"Agent run completed: task={request.task}, source={result.get('source')}, "
            f"latency={result.get('latency', latency):.3f}s"
        )
        
        # Return response
        return AgentRunResponse(
            result=result.get("result"),
            source=result.get("source", "unknown"),
            latency=result.get("latency", latency),
            task=result.get("task", request.task),
            error=result.get("error"),
        )
        
    except ValueError as e:
        # Invalid task or parameters
        logger.warning(f"Invalid agent request: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        # Unexpected error
        latency = time.time() - start_time
        logger.error(f"Agent run failed: {e}", exc_info=True)
        return AgentRunResponse(
            result=None,
            source="error",
            latency=round(latency, 3),
            task=request.task,
            error=str(e),
        )


@router.get("/health", response_model=AgentHealthResponse)
async def agent_health():
    """
    Health check endpoint.
    Returns status of all model engines and available tasks.
    """
    try:
        return AgentHealthResponse(
            status="ok",
            models_loaded=manager.loaded_models.copy(),
            device=manager.device,
            available_tasks=[
                "generate",
                "summarize",
                "qa",
                "embedding",
                "translate",
                "caption",
                "classify",
            ],
        )
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/models")
async def list_models():
    """
    List available models and their status.
    """
    try:
        return {
            "local": {
                "available": manager.loaded_models.get("local", False),
                "model": manager.local_model_name or "Not configured",
            },
            "ollama": {
                "available": manager.loaded_models.get("ollama", False),
                "model": manager.ollama_model,
                "url": "http://localhost:11434",
            },
            "hf_api": {
                "available": manager.loaded_models.get("hf_api", False),
                "model": manager.api_model_name,
            },
        }
    except Exception as e:
        logger.error(f"List models failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
