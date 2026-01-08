"""Supabase database client for LLM Council."""

import os
from typing import Optional, List, Dict, Any
from datetime import datetime
from supabase import create_client, Client

# Initialize Supabase client
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")  # Use service role for backend

_supabase_client: Optional[Client] = None


def get_client() -> Client:
    """Get or create Supabase client."""
    global _supabase_client

    if _supabase_client is None:
        if not SUPABASE_URL or not SUPABASE_KEY:
            raise ValueError(
                "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY environment variables must be set"
            )
        _supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)

    return _supabase_client


# =============================================================================
# SESSION OPERATIONS
# =============================================================================

def create_session(
    session_id: str,
    council_type: str = "general",
    mode: str = "synthesized",
    models: Optional[List[str]] = None,
    chairman_model: Optional[str] = None,
    roles_enabled: bool = False,
    enhancements: Optional[List[str]] = None
) -> Dict[str, Any]:
    """Create a new session."""
    client = get_client()

    data = {
        "id": session_id,
        "council_type": council_type,
        "council_mode": mode,
        "models": models,
        "chairman_model": chairman_model,
        "roles_enabled": roles_enabled,
        "enhancements": enhancements,
    }

    result = client.table("sessions").insert(data).execute()
    return result.data[0] if result.data else None


def get_session(session_id: str) -> Optional[Dict[str, Any]]:
    """Get a session by ID with all its messages."""
    client = get_client()

    # Get session
    result = client.table("sessions").select("*").eq("id", session_id).execute()

    if not result.data:
        return None

    session = result.data[0]

    # Get messages for this session
    messages_result = client.table("messages")\
        .select("*")\
        .eq("session_id", session_id)\
        .order("created_at")\
        .execute()

    session["messages"] = messages_result.data or []
    return session


def list_sessions(limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
    """List all sessions with metadata."""
    client = get_client()

    result = client.table("sessions")\
        .select("*, messages(count)")\
        .order("updated_at", desc=True)\
        .range(offset, offset + limit - 1)\
        .execute()

    sessions = []
    for row in result.data or []:
        session = dict(row)
        # Handle the count aggregation
        message_count = row.get("messages", [])
        if isinstance(message_count, list) and len(message_count) > 0:
            session["message_count"] = message_count[0].get("count", 0)
        else:
            session["message_count"] = 0
        del session["messages"]
        sessions.append(session)

    return sessions


def update_session(session_id: str, **kwargs) -> Optional[Dict[str, Any]]:
    """Update session fields."""
    client = get_client()

    allowed_fields = ["title", "council_type", "council_mode", "models", "chairman_model",
                      "roles_enabled", "enhancements", "tags"]

    updates = {k: v for k, v in kwargs.items() if k in allowed_fields}

    if not updates:
        return get_session(session_id)

    result = client.table("sessions")\
        .update(updates)\
        .eq("id", session_id)\
        .execute()

    return get_session(session_id)


def delete_session(session_id: str) -> bool:
    """Delete a session and all its messages."""
    client = get_client()

    result = client.table("sessions").delete().eq("id", session_id).execute()
    return len(result.data) > 0 if result.data else False


# =============================================================================
# MESSAGE OPERATIONS
# =============================================================================

def add_message(
    session_id: str,
    role: str,
    content: Optional[str] = None,
    model_name: Optional[str] = None,
    specialist_role: Optional[str] = None,
    confidence_score: Optional[float] = None,
    debate_round: Optional[int] = None,
    stage_data: Optional[Dict] = None,
    metadata: Optional[Dict] = None
) -> Dict[str, Any]:
    """Add a message to a session."""
    import uuid

    client = get_client()
    message_id = str(uuid.uuid4())

    data = {
        "id": message_id,
        "session_id": session_id,
        "role": role,
        "content": content,
        "model_name": model_name,
        "specialist_role": specialist_role,
        "confidence_score": confidence_score,
        "debate_round": debate_round,
        "stage_data": stage_data,
        "metadata": metadata,
    }

    result = client.table("messages").insert(data).execute()

    # Update session's updated_at (trigger should handle this, but explicit is safer)
    client.table("sessions")\
        .update({"updated_at": datetime.utcnow().isoformat()})\
        .eq("id", session_id)\
        .execute()

    return {"id": message_id, "role": role, "content": content}


def get_messages(session_id: str, limit: int = 100) -> List[Dict[str, Any]]:
    """Get messages for a session."""
    client = get_client()

    result = client.table("messages")\
        .select("*")\
        .eq("session_id", session_id)\
        .order("created_at")\
        .limit(limit)\
        .execute()

    return result.data or []


# =============================================================================
# SEARCH OPERATIONS
# =============================================================================

def search_messages(query: str, limit: int = 20) -> List[Dict[str, Any]]:
    """Full-text search across messages using PostgreSQL."""
    client = get_client()

    # Use PostgreSQL full-text search
    result = client.table("messages")\
        .select("*, sessions!inner(title)")\
        .text_search("content", query)\
        .limit(limit)\
        .execute()

    results = []
    for row in result.data or []:
        result_item = dict(row)
        result_item["session_title"] = row.get("sessions", {}).get("title", "Unknown")
        if "sessions" in result_item:
            del result_item["sessions"]
        results.append(result_item)

    return results


# =============================================================================
# CONVERSATION STATE (for multi-round modes)
# =============================================================================

def get_conversation_state(session_id: str) -> Optional[Dict[str, Any]]:
    """Get the state of a multi-round conversation."""
    client = get_client()

    result = client.table("conversation_state")\
        .select("*")\
        .eq("session_id", session_id)\
        .execute()

    if result.data:
        return result.data[0]
    return None


def save_conversation_state(
    session_id: str,
    mode: str,
    query: str,
    rounds: List[List[Dict]],
    current_round: int,
    models: List[str],
    chairman_model: str,
    council_type: str,
    roles_enabled: bool
) -> Dict[str, Any]:
    """Save or update conversation state."""
    client = get_client()

    data = {
        "session_id": session_id,
        "mode": mode,
        "query": query,
        "rounds": rounds,
        "current_round": current_round,
        "models": models,
        "chairman_model": chairman_model,
        "council_type": council_type,
        "roles_enabled": roles_enabled,
    }

    # Upsert - insert or update if exists
    result = client.table("conversation_state")\
        .upsert(data, on_conflict="session_id")\
        .execute()

    return result.data[0] if result.data else None


def delete_conversation_state(session_id: str) -> bool:
    """Delete conversation state."""
    client = get_client()

    result = client.table("conversation_state")\
        .delete()\
        .eq("session_id", session_id)\
        .execute()

    return len(result.data) > 0 if result.data else False


# =============================================================================
# MODEL PRESETS
# =============================================================================

def get_presets() -> List[Dict[str, Any]]:
    """Get all model presets."""
    client = get_client()

    result = client.table("model_presets")\
        .select("*")\
        .order("is_default", desc=True)\
        .order("name")\
        .execute()

    return result.data or []


def create_preset(
    preset_id: str,
    name: str,
    models: List[str],
    chairman_model: Optional[str] = None,
    description: Optional[str] = None
) -> Dict[str, Any]:
    """Create a new model preset."""
    client = get_client()

    data = {
        "id": preset_id,
        "name": name,
        "models": models,
        "chairman_model": chairman_model,
        "description": description,
    }

    result = client.table("model_presets").insert(data).execute()
    return result.data[0] if result.data else None


def get_preset(preset_id: str) -> Optional[Dict[str, Any]]:
    """Get a preset by ID."""
    client = get_client()

    result = client.table("model_presets")\
        .select("*")\
        .eq("id", preset_id)\
        .execute()

    return result.data[0] if result.data else None


def delete_preset(preset_id: str) -> bool:
    """Delete a preset (cannot delete default presets)."""
    client = get_client()

    result = client.table("model_presets")\
        .delete()\
        .eq("id", preset_id)\
        .eq("is_default", False)\
        .execute()

    return len(result.data) > 0 if result.data else False


# =============================================================================
# PREDICTIONS
# =============================================================================

def add_prediction(
    prediction_id: str,
    session_id: str,
    prediction_text: str,
    model_name: Optional[str] = None,
    message_id: Optional[str] = None,
    category: Optional[str] = None
) -> Dict[str, Any]:
    """Log a prediction for later tracking."""
    client = get_client()

    data = {
        "id": prediction_id,
        "session_id": session_id,
        "message_id": message_id,
        "prediction_text": prediction_text,
        "model_name": model_name,
        "category": category,
    }

    result = client.table("predictions").insert(data).execute()
    return result.data[0] if result.data else None


def get_prediction(prediction_id: str) -> Optional[Dict[str, Any]]:
    """Get a prediction by ID."""
    client = get_client()

    result = client.table("predictions")\
        .select("*")\
        .eq("id", prediction_id)\
        .execute()

    return result.data[0] if result.data else None


def record_outcome(
    prediction_id: str,
    outcome: str,
    accuracy_score: Optional[float] = None,
    notes: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """Record the outcome of a prediction."""
    client = get_client()

    data = {
        "outcome": outcome,
        "accuracy_score": accuracy_score,
        "outcome_notes": notes,
        "outcome_recorded_at": datetime.utcnow().isoformat(),
    }

    result = client.table("predictions")\
        .update(data)\
        .eq("id", prediction_id)\
        .execute()

    return get_prediction(prediction_id)


def get_prediction_stats() -> Dict[str, Any]:
    """Get statistics on prediction accuracy."""
    client = get_client()

    # Get all predictions with outcomes
    result = client.table("predictions")\
        .select("*")\
        .not_.is_("outcome", "null")\
        .execute()

    predictions = result.data or []

    # Calculate stats manually (Supabase doesn't support aggregations well in client)
    total = len(predictions)
    if total == 0:
        return {
            "overall": {"total_predictions": 0, "recorded_outcomes": 0, "avg_accuracy": None},
            "by_model": [],
            "by_category": []
        }

    # Calculate average accuracy
    scores = [p["accuracy_score"] for p in predictions if p.get("accuracy_score") is not None]
    avg_accuracy = sum(scores) / len(scores) if scores else None

    # Group by model
    by_model = {}
    for p in predictions:
        model = p.get("model_name") or "unknown"
        if model not in by_model:
            by_model[model] = {"predictions": 0, "scores": []}
        by_model[model]["predictions"] += 1
        if p.get("accuracy_score") is not None:
            by_model[model]["scores"].append(p["accuracy_score"])

    by_model_list = [
        {
            "model_name": k,
            "predictions": v["predictions"],
            "avg_accuracy": sum(v["scores"]) / len(v["scores"]) if v["scores"] else None
        }
        for k, v in by_model.items()
    ]

    # Group by category
    by_category = {}
    for p in predictions:
        cat = p.get("category") or "unknown"
        if cat not in by_category:
            by_category[cat] = {"predictions": 0, "scores": []}
        by_category[cat]["predictions"] += 1
        if p.get("accuracy_score") is not None:
            by_category[cat]["scores"].append(p["accuracy_score"])

    by_category_list = [
        {
            "category": k,
            "predictions": v["predictions"],
            "avg_accuracy": sum(v["scores"]) / len(v["scores"]) if v["scores"] else None
        }
        for k, v in by_category.items()
    ]

    return {
        "overall": {
            "total_predictions": total,
            "recorded_outcomes": total,
            "avg_accuracy": avg_accuracy
        },
        "by_model": sorted(by_model_list, key=lambda x: x.get("avg_accuracy") or 0, reverse=True),
        "by_category": sorted(by_category_list, key=lambda x: x.get("avg_accuracy") or 0, reverse=True)
    }
