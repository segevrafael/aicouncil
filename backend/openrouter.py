"""OpenRouter API client for making LLM requests."""

import httpx
from typing import List, Dict, Any, Optional
from .config import OPENROUTER_API_KEY, OPENROUTER_API_URL


async def query_model(
    model: str,
    messages: List[Dict[str, str]],
    timeout: float = 120.0
) -> Optional[Dict[str, Any]]:
    """
    Query a single model via OpenRouter API.

    Args:
        model: OpenRouter model identifier (e.g., "openai/gpt-4o")
        messages: List of message dicts with 'role' and 'content'
        timeout: Request timeout in seconds

    Returns:
        Response dict with 'content' and optional 'reasoning_details', or None if failed
    """
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": model,
        "messages": messages,
    }

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                OPENROUTER_API_URL,
                headers=headers,
                json=payload
            )
            response.raise_for_status()

            data = response.json()
            message = data['choices'][0]['message']

            return {
                'content': message.get('content'),
                'reasoning_details': message.get('reasoning_details')
            }

    except Exception as e:
        print(f"Error querying model {model}: {e}")
        return None


async def query_models_parallel(
    models: List[str],
    messages_or_dict,
    timeout: float = 90.0
) -> Dict[str, Optional[Dict[str, Any]]]:
    """
    Query multiple models in parallel.

    Args:
        models: List of OpenRouter model identifiers
        messages_or_dict: Either:
            - List of message dicts to send to ALL models (broadcast)
            - Dict mapping model ID to its specific message list (per-model)
        timeout: Per-model timeout in seconds

    Returns:
        Dict mapping model identifier to response dict (or None if failed)
    """
    import asyncio

    # Determine if we have per-model messages or broadcast
    if isinstance(messages_or_dict, dict):
        # Per-model messages: each model gets its own message list
        tasks = [query_model(model, messages_or_dict.get(model, []), timeout=timeout) for model in models]
    else:
        # Broadcast: same messages to all models
        tasks = [query_model(model, messages_or_dict, timeout=timeout) for model in models]

    # Wait for all to complete
    responses = await asyncio.gather(*tasks)

    # Map models to their responses
    return {model: response for model, response in zip(models, responses)}


async def query_models_streaming(
    models: List[str],
    messages_or_dict,
    timeout: float = 90.0
):
    """
    Query multiple models in parallel, yielding results as each completes.

    Args:
        models: List of OpenRouter model identifiers
        messages_or_dict: Either:
            - List of message dicts to send to ALL models (broadcast)
            - Dict mapping model ID to its specific message list (per-model)
        timeout: Per-model timeout in seconds

    Yields:
        Tuple of (model_id, response_dict or None) as each model completes
    """
    import asyncio

    # Create tasks with model tracking
    async def query_with_id(model: str, messages: List[Dict[str, str]]):
        result = await query_model(model, messages, timeout=timeout)
        return (model, result)

    # Determine if we have per-model messages or broadcast
    if isinstance(messages_or_dict, dict):
        tasks = [query_with_id(model, messages_or_dict.get(model, [])) for model in models]
    else:
        tasks = [query_with_id(model, messages_or_dict) for model in models]

    # Yield results as each completes
    for coro in asyncio.as_completed(tasks):
        model, response = await coro
        yield (model, response)
