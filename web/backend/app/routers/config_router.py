"""Configuration endpoints - models list, key validation."""
from fastapi import APIRouter
from app.models.schemas import ModelsResponse, ModelInfo, ValidateKeyRequest, ValidateKeyResponse
from app.config import AVAILABLE_MODELS
from app.services.model_manager import validate_api_key

router = APIRouter(prefix="/api/config", tags=["Configuration"])


@router.get("/models", response_model=ModelsResponse)
async def list_models():
    """List all available LLM models."""
    return ModelsResponse(models=[ModelInfo(**m) for m in AVAILABLE_MODELS])


@router.post("/validate-key", response_model=ValidateKeyResponse)
async def validate_key(request: ValidateKeyRequest):
    """Validate an API key for a specific provider."""
    valid, message = validate_api_key(request.provider.value, request.api_key)
    return ValidateKeyResponse(valid=valid, message=message)
