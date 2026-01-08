"""OpenRouter models API - fetch and manage available models."""

import httpx
from datetime import datetime, timedelta
from typing import Optional
from .config import OPENROUTER_API_KEY, OPENROUTER_MODELS_URL


# In-memory cache for models (they don't change often)
_models_cache: dict = {
    "data": None,
    "expires": None
}

# Cache duration
CACHE_DURATION_HOURS = 1


async def fetch_available_models(api_key: Optional[str] = None) -> list[dict]:
    """
    Fetch all available models from OpenRouter.

    Results are cached for 1 hour to avoid repeated API calls.

    Args:
        api_key: OpenRouter API key. Uses config default if not provided.

    Returns:
        List of model dictionaries with id, name, context_length, pricing, etc.
    """
    # Check cache first
    if _models_cache["data"] and _models_cache["expires"]:
        if datetime.now() < _models_cache["expires"]:
            return _models_cache["data"]

    key = api_key or OPENROUTER_API_KEY

    if not key:
        raise ValueError("OpenRouter API key not configured")

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                OPENROUTER_MODELS_URL,
                headers={"Authorization": f"Bearer {key}"}
            )
            response.raise_for_status()

            data = response.json()
            models = data.get("data", [])

            # Cache the results
            _models_cache["data"] = models
            _models_cache["expires"] = datetime.now() + timedelta(hours=CACHE_DURATION_HOURS)

            return models

    except httpx.HTTPError as e:
        print(f"Error fetching models from OpenRouter: {e}")
        # Return cached data if available, even if expired
        if _models_cache["data"]:
            return _models_cache["data"]
        raise


def filter_chat_models(models: list[dict]) -> list[dict]:
    """
    Filter to only chat-capable models.

    Args:
        models: List of model dictionaries from OpenRouter

    Returns:
        Filtered list containing only models that support chat
    """
    chat_models = []

    for model in models:
        # Check if model supports text input/output (chat)
        architecture = model.get("architecture", {})
        modality = architecture.get("modality", "")

        # Models with text->text or text+image->text are chat capable
        if "text" in modality.lower():
            chat_models.append(model)

    return chat_models


def sort_models_by_popularity(models: list[dict]) -> list[dict]:
    """
    Sort models by a popularity/quality heuristic.

    Prioritizes:
    1. Known frontier models (GPT-4+, Claude 3+, Gemini, etc.)
    2. Models with larger context windows
    3. Alphabetically as fallback
    """
    # Priority providers/models (higher = more priority)
    priority_prefixes = [
        ("openai/gpt-5", 100),
        ("openai/gpt-4", 90),
        ("anthropic/claude-opus", 95),
        ("anthropic/claude-sonnet", 85),
        ("anthropic/claude", 80),
        ("google/gemini-3", 90),
        ("google/gemini-2", 85),
        ("google/gemini", 75),
        ("x-ai/grok", 80),
        ("meta-llama/llama-3", 70),
        ("mistralai/mistral-large", 70),
        ("deepseek", 65),
        ("qwen", 60),
    ]

    def get_priority(model: dict) -> tuple:
        model_id = model.get("id", "").lower()

        # Check priority prefixes
        for prefix, priority in priority_prefixes:
            if model_id.startswith(prefix.lower()):
                return (priority, model.get("context_length", 0), model_id)

        # Default priority based on context length
        return (0, model.get("context_length", 0), model_id)

    return sorted(models, key=get_priority, reverse=True)


def format_model_for_display(model: dict) -> dict:
    """
    Format a model dictionary for frontend display.

    Args:
        model: Raw model data from OpenRouter

    Returns:
        Simplified dictionary for UI
    """
    pricing = model.get("pricing", {})

    # Calculate cost per 1k tokens (prompt)
    prompt_cost = float(pricing.get("prompt", 0)) * 1000
    completion_cost = float(pricing.get("completion", 0)) * 1000

    return {
        "id": model.get("id", ""),
        "name": model.get("name", model.get("id", "Unknown")),
        "context_length": model.get("context_length", 0),
        "pricing": {
            "prompt_per_1k": round(prompt_cost, 6),
            "completion_per_1k": round(completion_cost, 6),
        },
        "provider": model.get("id", "").split("/")[0] if "/" in model.get("id", "") else "unknown",
        "description": model.get("description", ""),
        "architecture": model.get("architecture", {}),
    }


async def get_models_for_picker(api_key: Optional[str] = None) -> list[dict]:
    """
    Get models formatted for the model picker UI.

    Args:
        api_key: Optional OpenRouter API key

    Returns:
        List of formatted, filtered, and sorted models ready for display
    """
    models = await fetch_available_models(api_key)
    chat_models = filter_chat_models(models)
    sorted_models = sort_models_by_popularity(chat_models)

    return [format_model_for_display(m) for m in sorted_models]


def clear_cache():
    """Clear the models cache (useful for testing or forcing refresh)."""
    _models_cache["data"] = None
    _models_cache["expires"] = None


def get_model_info(models: list[dict], model_id: str) -> Optional[dict]:
    """
    Get info for a specific model by ID.

    Args:
        models: List of model dictionaries
        model_id: The model ID to look up (e.g., "openai/gpt-4")

    Returns:
        Model dictionary or None if not found
    """
    for model in models:
        if model.get("id") == model_id:
            return model
    return None
