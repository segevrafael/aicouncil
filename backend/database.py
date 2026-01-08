"""SQLite database for LLM Council with full-text search."""

import sqlite3
import json
import os
from datetime import datetime
from typing import Optional, List, Dict, Any
from pathlib import Path
from contextlib import contextmanager

from .config import DATABASE_PATH, DATA_DIR


def get_db_path() -> str:
    """Get the database path, ensuring the directory exists."""
    db_dir = os.path.dirname(DATABASE_PATH)
    if db_dir:
        Path(db_dir).mkdir(parents=True, exist_ok=True)
    return DATABASE_PATH


@contextmanager
def get_connection():
    """Context manager for database connections."""
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_database():
    """Initialize the database schema."""
    with get_connection() as conn:
        cursor = conn.cursor()

        # Sessions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                title TEXT DEFAULT 'New Conversation',
                council_type TEXT DEFAULT 'general',
                council_mode TEXT DEFAULT 'synthesized',
                models TEXT,  -- JSON array of model IDs
                chairman_model TEXT,
                roles_enabled INTEGER DEFAULT 0,
                enhancements TEXT,  -- JSON array
                tags TEXT,  -- JSON array
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Messages table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,  -- user, assistant, system
                content TEXT,
                model_name TEXT,
                specialist_role TEXT,
                confidence_score REAL,
                debate_round INTEGER,
                stage_data TEXT,  -- JSON for stage1/stage2/stage3 data
                metadata TEXT,  -- JSON for additional metadata
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
            )
        """)

        # Model presets table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS model_presets (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                description TEXT,
                models TEXT NOT NULL,  -- JSON array of model IDs
                chairman_model TEXT,
                is_default INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Predictions table for tracking advice accuracy
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS predictions (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                message_id TEXT,
                prediction_text TEXT NOT NULL,
                model_name TEXT,
                category TEXT,  -- business, personal, technical, etc.
                outcome TEXT,  -- NULL until recorded
                outcome_notes TEXT,
                accuracy_score REAL,  -- 0-1 scale
                predicted_at TEXT DEFAULT CURRENT_TIMESTAMP,
                outcome_recorded_at TEXT,
                FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE,
                FOREIGN KEY (message_id) REFERENCES messages(id) ON DELETE SET NULL
            )
        """)

        # Full-text search virtual table for messages
        cursor.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5(
                content,
                session_id,
                content='messages',
                content_rowid='rowid'
            )
        """)

        # Triggers to keep FTS index in sync
        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS messages_ai AFTER INSERT ON messages BEGIN
                INSERT INTO messages_fts(rowid, content, session_id)
                VALUES (new.rowid, new.content, new.session_id);
            END
        """)

        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS messages_ad AFTER DELETE ON messages BEGIN
                INSERT INTO messages_fts(messages_fts, rowid, content, session_id)
                VALUES ('delete', old.rowid, old.content, old.session_id);
            END
        """)

        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS messages_au AFTER UPDATE ON messages BEGIN
                INSERT INTO messages_fts(messages_fts, rowid, content, session_id)
                VALUES ('delete', old.rowid, old.content, old.session_id);
                INSERT INTO messages_fts(rowid, content, session_id)
                VALUES (new.rowid, new.content, new.session_id);
            END
        """)

        # Create indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_created ON messages(created_at)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sessions_created ON sessions(created_at)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_predictions_session ON predictions(session_id)")

        # Insert default model preset if it doesn't exist
        cursor.execute("""
            INSERT OR IGNORE INTO model_presets (id, name, description, models, chairman_model, is_default)
            VALUES (
                'default-frontier',
                'Frontier Models',
                'Latest frontier models from major providers',
                '["openai/gpt-5.2", "anthropic/claude-opus-4.5", "google/gemini-3-pro-preview", "x-ai/grok-4"]',
                'anthropic/claude-opus-4.5',
                1
            )
        """)


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
    with get_connection() as conn:
        cursor = conn.cursor()
        now = datetime.utcnow().isoformat()

        cursor.execute("""
            INSERT INTO sessions (id, council_type, council_mode, models, chairman_model,
                                  roles_enabled, enhancements, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            session_id,
            council_type,
            mode,
            json.dumps(models) if models else None,
            chairman_model,
            1 if roles_enabled else 0,
            json.dumps(enhancements) if enhancements else None,
            now,
            now
        ))

        return get_session(session_id)


def get_session(session_id: str) -> Optional[Dict[str, Any]]:
    """Get a session by ID."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM sessions WHERE id = ?", (session_id,))
        row = cursor.fetchone()

        if not row:
            return None

        session = dict(row)
        session["models"] = json.loads(session["models"]) if session["models"] else None
        session["enhancements"] = json.loads(session["enhancements"]) if session["enhancements"] else []
        session["tags"] = json.loads(session["tags"]) if session["tags"] else []
        session["roles_enabled"] = bool(session["roles_enabled"])

        # Get messages
        cursor.execute("""
            SELECT * FROM messages WHERE session_id = ? ORDER BY created_at
        """, (session_id,))

        messages = []
        for msg_row in cursor.fetchall():
            msg = dict(msg_row)
            msg["stage_data"] = json.loads(msg["stage_data"]) if msg["stage_data"] else None
            msg["metadata"] = json.loads(msg["metadata"]) if msg["metadata"] else None
            messages.append(msg)

        session["messages"] = messages
        return session


def list_sessions(limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
    """List all sessions with metadata."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT s.*, COUNT(m.id) as message_count
            FROM sessions s
            LEFT JOIN messages m ON s.id = m.session_id
            GROUP BY s.id
            ORDER BY s.updated_at DESC
            LIMIT ? OFFSET ?
        """, (limit, offset))

        sessions = []
        for row in cursor.fetchall():
            session = dict(row)
            session["tags"] = json.loads(session["tags"]) if session["tags"] else []
            sessions.append(session)

        return sessions


def update_session(session_id: str, **kwargs) -> Optional[Dict[str, Any]]:
    """Update session fields."""
    allowed_fields = ["title", "council_type", "council_mode", "models", "chairman_model",
                      "roles_enabled", "enhancements", "tags"]

    updates = []
    values = []

    for field, value in kwargs.items():
        if field in allowed_fields:
            if field in ["models", "enhancements", "tags"]:
                value = json.dumps(value) if value else None
            elif field == "roles_enabled":
                value = 1 if value else 0
            updates.append(f"{field} = ?")
            values.append(value)

    if not updates:
        return get_session(session_id)

    updates.append("updated_at = ?")
    values.append(datetime.utcnow().isoformat())
    values.append(session_id)

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(f"""
            UPDATE sessions SET {', '.join(updates)} WHERE id = ?
        """, values)

    return get_session(session_id)


def delete_session(session_id: str) -> bool:
    """Delete a session and all its messages."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        return cursor.rowcount > 0


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

    message_id = str(uuid.uuid4())

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO messages (id, session_id, role, content, model_name, specialist_role,
                                  confidence_score, debate_round, stage_data, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            message_id,
            session_id,
            role,
            content,
            model_name,
            specialist_role,
            confidence_score,
            debate_round,
            json.dumps(stage_data) if stage_data else None,
            json.dumps(metadata) if metadata else None
        ))

        # Update session updated_at
        cursor.execute("""
            UPDATE sessions SET updated_at = ? WHERE id = ?
        """, (datetime.utcnow().isoformat(), session_id))

    return {"id": message_id, "role": role, "content": content}


def get_messages(session_id: str, limit: int = 100) -> List[Dict[str, Any]]:
    """Get messages for a session."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM messages WHERE session_id = ? ORDER BY created_at LIMIT ?
        """, (session_id, limit))

        messages = []
        for row in cursor.fetchall():
            msg = dict(row)
            msg["stage_data"] = json.loads(msg["stage_data"]) if msg["stage_data"] else None
            msg["metadata"] = json.loads(msg["metadata"]) if msg["metadata"] else None
            messages.append(msg)

        return messages


# =============================================================================
# SEARCH OPERATIONS
# =============================================================================

def search_messages(query: str, limit: int = 20) -> List[Dict[str, Any]]:
    """Full-text search across messages."""
    with get_connection() as conn:
        cursor = conn.cursor()

        # Search using FTS5
        cursor.execute("""
            SELECT m.*, s.title as session_title,
                   highlight(messages_fts, 0, '<mark>', '</mark>') as highlighted_content
            FROM messages_fts
            JOIN messages m ON messages_fts.rowid = m.rowid
            JOIN sessions s ON m.session_id = s.id
            WHERE messages_fts MATCH ?
            ORDER BY rank
            LIMIT ?
        """, (query, limit))

        results = []
        for row in cursor.fetchall():
            result = dict(row)
            result["stage_data"] = json.loads(result["stage_data"]) if result["stage_data"] else None
            result["metadata"] = json.loads(result["metadata"]) if result["metadata"] else None
            results.append(result)

        return results


# =============================================================================
# MODEL PRESETS
# =============================================================================

def get_presets() -> List[Dict[str, Any]]:
    """Get all model presets."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM model_presets ORDER BY is_default DESC, name")

        presets = []
        for row in cursor.fetchall():
            preset = dict(row)
            preset["models"] = json.loads(preset["models"])
            preset["is_default"] = bool(preset["is_default"])
            presets.append(preset)

        return presets


def create_preset(
    preset_id: str,
    name: str,
    models: List[str],
    chairman_model: Optional[str] = None,
    description: Optional[str] = None
) -> Dict[str, Any]:
    """Create a new model preset."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO model_presets (id, name, description, models, chairman_model)
            VALUES (?, ?, ?, ?, ?)
        """, (preset_id, name, description, json.dumps(models), chairman_model))

    return get_preset(preset_id)


def get_preset(preset_id: str) -> Optional[Dict[str, Any]]:
    """Get a preset by ID."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM model_presets WHERE id = ?", (preset_id,))
        row = cursor.fetchone()

        if not row:
            return None

        preset = dict(row)
        preset["models"] = json.loads(preset["models"])
        preset["is_default"] = bool(preset["is_default"])
        return preset


def delete_preset(preset_id: str) -> bool:
    """Delete a preset."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM model_presets WHERE id = ? AND is_default = 0", (preset_id,))
        return cursor.rowcount > 0


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
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO predictions (id, session_id, message_id, prediction_text, model_name, category)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (prediction_id, session_id, message_id, prediction_text, model_name, category))

    return get_prediction(prediction_id)


def get_prediction(prediction_id: str) -> Optional[Dict[str, Any]]:
    """Get a prediction by ID."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM predictions WHERE id = ?", (prediction_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


def record_outcome(
    prediction_id: str,
    outcome: str,
    accuracy_score: Optional[float] = None,
    notes: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """Record the outcome of a prediction."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE predictions
            SET outcome = ?, accuracy_score = ?, outcome_notes = ?, outcome_recorded_at = ?
            WHERE id = ?
        """, (outcome, accuracy_score, notes, datetime.utcnow().isoformat(), prediction_id))

    return get_prediction(prediction_id)


def get_prediction_stats() -> Dict[str, Any]:
    """Get statistics on prediction accuracy."""
    with get_connection() as conn:
        cursor = conn.cursor()

        # Overall stats
        cursor.execute("""
            SELECT
                COUNT(*) as total_predictions,
                COUNT(outcome) as recorded_outcomes,
                AVG(accuracy_score) as avg_accuracy
            FROM predictions
        """)
        overall = dict(cursor.fetchone())

        # Stats by model
        cursor.execute("""
            SELECT
                model_name,
                COUNT(*) as predictions,
                AVG(accuracy_score) as avg_accuracy
            FROM predictions
            WHERE outcome IS NOT NULL AND model_name IS NOT NULL
            GROUP BY model_name
            ORDER BY avg_accuracy DESC
        """)
        by_model = [dict(row) for row in cursor.fetchall()]

        # Stats by category
        cursor.execute("""
            SELECT
                category,
                COUNT(*) as predictions,
                AVG(accuracy_score) as avg_accuracy
            FROM predictions
            WHERE outcome IS NOT NULL AND category IS NOT NULL
            GROUP BY category
            ORDER BY avg_accuracy DESC
        """)
        by_category = [dict(row) for row in cursor.fetchall()]

        return {
            "overall": overall,
            "by_model": by_model,
            "by_category": by_category
        }


# =============================================================================
# MIGRATION FROM JSON
# =============================================================================

def migrate_from_json():
    """Migrate existing JSON conversations to SQLite."""
    if not os.path.exists(DATA_DIR):
        return {"migrated": 0, "errors": []}

    migrated = 0
    errors = []

    for filename in os.listdir(DATA_DIR):
        if not filename.endswith('.json'):
            continue

        filepath = os.path.join(DATA_DIR, filename)
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)

            session_id = data.get("id", filename.replace('.json', ''))

            # Check if already migrated
            if get_session(session_id):
                continue

            # Create session
            create_session(session_id)
            update_session(session_id, title=data.get("title", "Migrated Conversation"))

            # Add messages
            for msg in data.get("messages", []):
                if msg.get("role") == "user":
                    add_message(session_id, "user", content=msg.get("content"))
                elif msg.get("role") == "assistant":
                    add_message(
                        session_id,
                        "assistant",
                        stage_data={
                            "stage1": msg.get("stage1"),
                            "stage2": msg.get("stage2"),
                            "stage3": msg.get("stage3")
                        }
                    )

            migrated += 1

        except Exception as e:
            errors.append({"file": filename, "error": str(e)})

    return {"migrated": migrated, "errors": errors}


# Initialize database on import
init_database()
