"""Supabase database client for LLM Council - using httpx REST API."""

import os
import uuid
import httpx
from typing import Optional, List, Dict, Any
from datetime import datetime

# Supabase configuration
SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

# Base headers for Supabase REST API
def _get_headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


def _rest_url(table: str) -> str:
    """Get the REST API URL for a table."""
    return f"{SUPABASE_URL}/rest/v1/{table}"


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
    enhancements: Optional[List[str]] = None,
    user_id: Optional[str] = None
) -> Dict[str, Any]:
    """Create a new session."""
    data = {
        "id": session_id,
        "council_type": council_type,
        "council_mode": mode,
        "models": models,
        "chairman_model": chairman_model,
        "roles_enabled": roles_enabled,
        "enhancements": enhancements,
    }
    if user_id:
        data["user_id"] = user_id

    with httpx.Client() as client:
        response = client.post(
            _rest_url("sessions"),
            headers=_get_headers(),
            json=data
        )
        # If 400 error and we included user_id, retry without it (column may not exist)
        if response.status_code == 400 and user_id:
            del data["user_id"]
            response = client.post(
                _rest_url("sessions"),
                headers=_get_headers(),
                json=data
            )
        response.raise_for_status()
        result = response.json()
        return result[0] if isinstance(result, list) and result else result


def get_session(session_id: str) -> Optional[Dict[str, Any]]:
    """Get a session by ID with all its messages."""
    with httpx.Client() as client:
        # Get session
        response = client.get(
            _rest_url("sessions"),
            headers=_get_headers(),
            params={"id": f"eq.{session_id}"}
        )
        response.raise_for_status()
        sessions = response.json()

        if not sessions:
            return None

        session = sessions[0]

        # Get messages for this session
        msg_response = client.get(
            _rest_url("messages"),
            headers=_get_headers(),
            params={
                "session_id": f"eq.{session_id}",
                "order": "created_at.asc"
            }
        )
        msg_response.raise_for_status()
        session["messages"] = msg_response.json() or []

        return session


def list_sessions(limit: int = 50, offset: int = 0, include_archived: bool = False, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """List all sessions with metadata.

    Args:
        limit: Maximum number of sessions to return
        offset: Number of sessions to skip
        include_archived: If False (default), exclude archived sessions
        user_id: If provided, only return sessions for this user
    """
    with httpx.Client() as client:
        # Build params
        params = {
            "order": "updated_at.desc",
            "offset": str(offset),
            "limit": str(limit),
        }

        # Filter by user_id if provided
        if user_id:
            params["user_id"] = f"eq.{user_id}"

        # Filter out archived sessions by default
        if not include_archived:
            params["or"] = "(is_archived.is.null,is_archived.eq.false)"

        # Get sessions
        response = client.get(
            _rest_url("sessions"),
            headers=_get_headers(),
            params=params
        )
        # If 400 error and we filtered by user_id, retry without it (column may not exist)
        if response.status_code == 400 and user_id:
            del params["user_id"]
            response = client.get(
                _rest_url("sessions"),
                headers=_get_headers(),
                params=params
            )
        response.raise_for_status()
        sessions = response.json() or []

        # Get message counts for each session
        for session in sessions:
            count_response = client.get(
                _rest_url("messages"),
                headers={**_get_headers(), "Prefer": "count=exact"},
                params={
                    "session_id": f"eq.{session['id']}",
                    "select": "id",
                }
            )
            # Parse count from content-range header
            content_range = count_response.headers.get("content-range", "")
            if "/" in content_range:
                try:
                    session["message_count"] = int(content_range.split("/")[1])
                except (ValueError, IndexError):
                    session["message_count"] = 0
            else:
                session["message_count"] = len(count_response.json() or [])

        return sessions


def update_session(session_id: str, **kwargs) -> Optional[Dict[str, Any]]:
    """Update session fields."""
    allowed_fields = ["title", "council_type", "council_mode", "models", "chairman_model",
                      "roles_enabled", "enhancements", "tags", "is_archived"]

    updates = {k: v for k, v in kwargs.items() if k in allowed_fields}

    if not updates:
        return get_session(session_id)

    with httpx.Client() as client:
        response = client.patch(
            _rest_url("sessions"),
            headers=_get_headers(),
            params={"id": f"eq.{session_id}"},
            json=updates
        )
        response.raise_for_status()

    return get_session(session_id)


def delete_session(session_id: str) -> bool:
    """Delete a session and all its messages."""
    with httpx.Client() as client:
        response = client.delete(
            _rest_url("sessions"),
            headers=_get_headers(),
            params={"id": f"eq.{session_id}"}
        )
        response.raise_for_status()
        return True


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

    with httpx.Client() as client:
        response = client.post(
            _rest_url("messages"),
            headers=_get_headers(),
            json=data
        )
        response.raise_for_status()

        # Update session's updated_at
        client.patch(
            _rest_url("sessions"),
            headers=_get_headers(),
            params={"id": f"eq.{session_id}"},
            json={"updated_at": datetime.utcnow().isoformat()}
        )

    return {"id": message_id, "role": role, "content": content}


def get_messages(session_id: str, limit: int = 100) -> List[Dict[str, Any]]:
    """Get messages for a session."""
    with httpx.Client() as client:
        response = client.get(
            _rest_url("messages"),
            headers=_get_headers(),
            params={
                "session_id": f"eq.{session_id}",
                "order": "created_at.asc",
                "limit": str(limit)
            }
        )
        response.raise_for_status()
        return response.json() or []


# =============================================================================
# SEARCH OPERATIONS
# =============================================================================

def search_messages(query: str, limit: int = 20) -> List[Dict[str, Any]]:
    """Full-text search across messages using PostgreSQL."""
    # Escape special characters for text search
    safe_query = query.replace("'", "''")

    with httpx.Client() as client:
        # Use ilike for simple search (full-text search requires RPC)
        response = client.get(
            _rest_url("messages"),
            headers=_get_headers(),
            params={
                "content": f"ilike.%{safe_query}%",
                "limit": str(limit),
                "order": "created_at.desc",
            }
        )
        response.raise_for_status()
        messages = response.json() or []

        # Get session titles for each message
        results = []
        session_cache = {}

        for msg in messages:
            session_id = msg.get("session_id")
            if session_id not in session_cache:
                sess_response = client.get(
                    _rest_url("sessions"),
                    headers=_get_headers(),
                    params={"id": f"eq.{session_id}", "select": "title"}
                )
                sess_data = sess_response.json()
                session_cache[session_id] = sess_data[0].get("title") if sess_data else "Unknown"

            msg["session_title"] = session_cache[session_id]
            results.append(msg)

        return results


# =============================================================================
# CONVERSATION STATE (for multi-round modes)
# =============================================================================

def get_conversation_state(session_id: str) -> Optional[Dict[str, Any]]:
    """Get the state of a multi-round conversation."""
    with httpx.Client() as client:
        response = client.get(
            _rest_url("conversation_state"),
            headers=_get_headers(),
            params={"session_id": f"eq.{session_id}"}
        )
        response.raise_for_status()
        result = response.json()
        return result[0] if result else None


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

    with httpx.Client() as client:
        # Check if exists
        existing = get_conversation_state(session_id)

        if existing:
            # Update
            response = client.patch(
                _rest_url("conversation_state"),
                headers=_get_headers(),
                params={"session_id": f"eq.{session_id}"},
                json=data
            )
        else:
            # Insert
            response = client.post(
                _rest_url("conversation_state"),
                headers=_get_headers(),
                json=data
            )

        response.raise_for_status()
        result = response.json()
        return result[0] if isinstance(result, list) and result else result


def delete_conversation_state(session_id: str) -> bool:
    """Delete conversation state."""
    with httpx.Client() as client:
        response = client.delete(
            _rest_url("conversation_state"),
            headers=_get_headers(),
            params={"session_id": f"eq.{session_id}"}
        )
        response.raise_for_status()
        return True


# =============================================================================
# MODEL PRESETS
# =============================================================================

def get_presets() -> List[Dict[str, Any]]:
    """Get all model presets."""
    with httpx.Client() as client:
        response = client.get(
            _rest_url("model_presets"),
            headers=_get_headers(),
            params={"order": "is_default.desc,name.asc"}
        )
        response.raise_for_status()
        return response.json() or []


def create_preset(
    preset_id: str,
    name: str,
    models: List[str],
    chairman_model: Optional[str] = None,
    description: Optional[str] = None,
    user_id: Optional[str] = None
) -> Dict[str, Any]:
    """Create a new model preset."""
    data = {
        "id": preset_id,
        "name": name,
        "models": models,
        "chairman_model": chairman_model,
        "description": description,
    }
    if user_id:
        data["user_id"] = user_id

    with httpx.Client() as client:
        response = client.post(
            _rest_url("model_presets"),
            headers=_get_headers(),
            json=data
        )
        response.raise_for_status()
        result = response.json()
        return result[0] if isinstance(result, list) and result else result


def get_preset(preset_id: str) -> Optional[Dict[str, Any]]:
    """Get a preset by ID."""
    with httpx.Client() as client:
        response = client.get(
            _rest_url("model_presets"),
            headers=_get_headers(),
            params={"id": f"eq.{preset_id}"}
        )
        response.raise_for_status()
        result = response.json()
        return result[0] if result else None


def delete_preset(preset_id: str) -> bool:
    """Delete a preset (cannot delete default presets)."""
    with httpx.Client() as client:
        response = client.delete(
            _rest_url("model_presets"),
            headers=_get_headers(),
            params={
                "id": f"eq.{preset_id}",
                "is_default": "eq.false"
            }
        )
        response.raise_for_status()
        return True


# =============================================================================
# PREDICTIONS
# =============================================================================

def add_prediction(
    prediction_id: str,
    session_id: str,
    prediction_text: str,
    model_name: Optional[str] = None,
    message_id: Optional[str] = None,
    category: Optional[str] = None,
    user_id: Optional[str] = None
) -> Dict[str, Any]:
    """Log a prediction for later tracking."""
    data = {
        "id": prediction_id,
        "session_id": session_id,
        "message_id": message_id,
        "prediction_text": prediction_text,
        "model_name": model_name,
        "category": category,
    }
    if user_id:
        data["user_id"] = user_id

    with httpx.Client() as client:
        response = client.post(
            _rest_url("predictions"),
            headers=_get_headers(),
            json=data
        )
        response.raise_for_status()
        result = response.json()
        return result[0] if isinstance(result, list) and result else result


def get_prediction(prediction_id: str) -> Optional[Dict[str, Any]]:
    """Get a prediction by ID."""
    with httpx.Client() as client:
        response = client.get(
            _rest_url("predictions"),
            headers=_get_headers(),
            params={"id": f"eq.{prediction_id}"}
        )
        response.raise_for_status()
        result = response.json()
        return result[0] if result else None


def record_outcome(
    prediction_id: str,
    outcome: str,
    accuracy_score: Optional[float] = None,
    notes: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """Record the outcome of a prediction."""
    data = {
        "outcome": outcome,
        "accuracy_score": accuracy_score,
        "outcome_notes": notes,
        "outcome_recorded_at": datetime.utcnow().isoformat(),
    }

    with httpx.Client() as client:
        response = client.patch(
            _rest_url("predictions"),
            headers=_get_headers(),
            params={"id": f"eq.{prediction_id}"},
            json=data
        )
        response.raise_for_status()

    return get_prediction(prediction_id)


def get_prediction_stats(user_id: Optional[str] = None) -> Dict[str, Any]:
    """Get statistics on prediction accuracy."""
    with httpx.Client() as client:
        # Get all predictions with outcomes
        params = {"outcome": "not.is.null"}
        if user_id:
            params["user_id"] = f"eq.{user_id}"
        response = client.get(
            _rest_url("predictions"),
            headers=_get_headers(),
            params=params
        )
        response.raise_for_status()
        predictions = response.json() or []

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
