"""LLM handler management - creates and caches LLM handlers per provider/key."""
import os
import sys
from app.config import DEEPRARE_ROOT, settings

if str(DEEPRARE_ROOT) not in sys.path:
    sys.path.insert(0, str(DEEPRARE_ROOT))

from api.interface import Openai_api, deepseek_api, gemini_api, claude_api


def get_api_key(provider: str, request_key: str | None) -> str:
    """Get API key from request or fallback to server config."""
    if request_key:
        return request_key
    key_attr = {
        "openai": "openai_api_key",
        "anthropic": "anthropic_api_key",
        "google": "google_api_key",
        "deepseek": "deepseek_api_key",
    }.get(provider, "")
    return getattr(settings, key_attr, "") or ""


def get_openai_key(request_key: str | None) -> str:
    return get_api_key("openai", request_key)


def create_handler(provider: str, model: str, api_key: str):
    """Create an LLM handler for the specified provider."""
    handlers = {
        "openai": lambda: Openai_api(model=model, api_key=api_key),
        "deepseek": lambda: deepseek_api(model=model, api_key=api_key),
        "google": lambda: gemini_api(model=model, api_key=api_key),
        "anthropic": lambda: claude_api(model=model, api_key=api_key),
    }
    factory = handlers.get(provider)
    if not factory:
        raise ValueError(f"Unknown provider: {provider}")
    return factory()


def create_openai_handler(api_key: str):
    """Create OpenAI handler for embeddings and mini completions (always needed)."""
    return Openai_api(model="gpt-4o-mini", api_key=api_key)


def validate_api_key(provider: str, api_key: str) -> tuple[bool, str]:
    """Validate an API key by making a minimal API call."""
    try:
        handler = create_handler(provider, "gpt-4o-mini" if provider == "openai" else "", api_key)
        if provider == "openai":
            handler.mini_completion("Say OK", "OK")
        else:
            handler.get_completion("Say OK", "OK")
        return True, "API key is valid"
    except Exception as e:
        return False, f"Invalid API key: {str(e)[:200]}"
