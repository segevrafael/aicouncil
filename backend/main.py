"""FastAPI backend for LLM Council."""

import os
from fastapi import FastAPI, HTTPException, Depends, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
import uuid
import json
import asyncio

from .council import (
    run_full_council,
    generate_conversation_title,
    stage1_collect_responses,
    stage1_collect_responses_streaming,
    stage2_collect_rankings,
    stage2_collect_rankings_streaming,
    stage3_synthesize_final,
    calculate_aggregate_rankings,
    # Mode handlers
    debate_round,
    debate_round_streaming,
    debate_summary,
    socratic_questions,
    socratic_questions_streaming,
    scenario_planning,
    scenario_planning_streaming,
    scenario_synthesis,
)
from .models_api import get_models_for_picker, clear_cache as clear_models_cache
from . import supabase_db as db
from .auth import require_auth
from . import files as file_handler
from .config import (
    COUNCIL_MODES,
    COUNCIL_TYPES,
    SPECIALIST_ROLES,
    ENHANCEMENTS,
    DEFAULT_COUNCIL_MODELS,
    DEFAULT_CHAIRMAN_MODEL,
)

app = FastAPI(
    title="LLM Council API",
    description="Multi-model AI council for collaborative decision making",
    version="2.0.0"
)

# Get allowed origins from environment or use defaults
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:3000").split(",")

# Enable CORS for local development and Vercel
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================

class CreateConversationRequest(BaseModel):
    """Request to create a new conversation."""
    council_type: str = "general"
    mode: str = "synthesized"


class SendMessageRequest(BaseModel):
    """Request to send a message in a conversation."""
    content: str
    mode: str = Field(default="synthesized", description="Council mode: independent|synthesized|debate|adversarial|socratic|scenario")
    council_type: str = Field(default="general", description="Council type for domain-specific prompts")
    models: Optional[List[str]] = Field(default=None, description="Override default models (list of 4 model IDs)")
    chairman_model: Optional[str] = Field(default=None, description="Override chairman model for synthesis")
    roles_enabled: bool = Field(default=False, description="Enable specialist roles (Optimist, Skeptic, etc.)")
    enhancements: List[str] = Field(default=[], description="Output enhancements: decision_matrix|confidence|followup_questions")
    web_search: bool = Field(default=False, description="Enable web search for models via OpenRouter plugin")
    attachments: List[Dict[str, Any]] = Field(default=[], description="File attachments (from upload endpoint)")


class ContinueDebateRequest(BaseModel):
    """Request to continue a multi-round debate."""
    user_input: Optional[str] = Field(default=None, description="Optional user input for this round (for socratic mode)")


class ConversationMetadata(BaseModel):
    """Conversation metadata for list view."""
    id: str
    created_at: str
    title: str
    message_count: int
    council_type: Optional[str] = None
    mode: Optional[str] = None


class Conversation(BaseModel):
    """Full conversation with all messages."""
    id: str
    created_at: str
    title: str
    messages: List[Dict[str, Any]]
    council_type: Optional[str] = None
    mode: Optional[str] = None


# =============================================================================
# HEALTH & CONFIG ENDPOINTS
# =============================================================================

@app.get("/")
async def root():
    """Health check endpoint."""
    return {"status": "ok", "service": "LLM Council API", "version": "2.0.0"}


@app.get("/api/config")
async def get_config():
    """Get all configuration options (modes, types, roles, enhancements)."""
    return {
        "modes": {
            key: {
                "name": val["name"],
                "description": val["description"],
                "multi_round": val["multi_round"],
                "has_synthesis": val["has_synthesis"],
            }
            for key, val in COUNCIL_MODES.items()
        },
        "council_types": {
            key: {
                "name": val["name"],
                "description": val["description"],
                "icon": val["icon"],
                "color": val["color"],
            }
            for key, val in COUNCIL_TYPES.items()
        },
        "roles": {
            key: {
                "name": val["name"],
                "description": val["prompt"][:100] + "..." if len(val["prompt"]) > 100 else val["prompt"],
            }
            for key, val in SPECIALIST_ROLES.items()
        },
        "enhancements": {
            key: {
                "name": val["name"],
                "description": val["description"],
            }
            for key, val in ENHANCEMENTS.items()
        },
        "defaults": {
            "models": DEFAULT_COUNCIL_MODELS,
            "chairman_model": DEFAULT_CHAIRMAN_MODEL,
            "mode": "synthesized",
            "council_type": "general",
        }
    }


@app.get("/api/config/modes")
async def get_modes():
    """Get available council modes."""
    return {
        key: {
            "name": val["name"],
            "description": val["description"],
            "multi_round": val["multi_round"],
            "has_synthesis": val["has_synthesis"],
        }
        for key, val in COUNCIL_MODES.items()
    }


@app.get("/api/config/council-types")
async def get_council_types():
    """Get available council types."""
    return {
        key: {
            "name": val["name"],
            "description": val["description"],
            "icon": val["icon"],
            "color": val["color"],
        }
        for key, val in COUNCIL_TYPES.items()
    }


@app.get("/api/config/roles")
async def get_roles():
    """Get available specialist roles."""
    return {
        key: {
            "name": val["name"],
            "description": val["prompt"],
        }
        for key, val in SPECIALIST_ROLES.items()
    }


@app.get("/api/config/enhancements")
async def get_enhancements():
    """Get available output enhancements."""
    return {
        key: {
            "name": val["name"],
            "description": val["description"],
        }
        for key, val in ENHANCEMENTS.items()
    }


# =============================================================================
# MODELS ENDPOINTS
# =============================================================================

@app.get("/api/models")
async def list_models():
    """
    Get all available models from OpenRouter.

    Returns models sorted by popularity/quality, filtered to chat-capable models.
    Results are cached for 1 hour.
    """
    try:
        models = await get_models_for_picker()
        return {
            "models": models,
            "count": len(models),
            "defaults": DEFAULT_COUNCIL_MODELS,
            "default_chairman": DEFAULT_CHAIRMAN_MODEL,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch models: {str(e)}")


@app.post("/api/models/refresh")
async def refresh_models():
    """Force refresh the models cache."""
    clear_models_cache()
    models = await get_models_for_picker()
    return {
        "models": models,
        "count": len(models),
        "message": "Models cache refreshed"
    }


# =============================================================================
# CONVERSATION ENDPOINTS
# =============================================================================

@app.get("/api/conversations")
async def list_conversations(include_archived: bool = False, user: dict = Depends(require_auth)):
    """List all conversations (metadata only).

    Args:
        include_archived: If True, include archived conversations. Default is False.
    """
    user_id = user.get("user_id")
    sessions = db.list_sessions(include_archived=include_archived, user_id=user_id)
    return [
        {
            "id": s["id"],
            "created_at": s.get("created_at", ""),
            "title": s.get("title", "New Conversation"),
            "message_count": s.get("message_count", 0),
            "council_type": s.get("council_type"),
            "mode": s.get("council_mode"),
            "is_archived": s.get("is_archived", False),
        }
        for s in sessions
    ]


@app.post("/api/conversations")
async def create_conversation(request: CreateConversationRequest, user: dict = Depends(require_auth)):
    """Create a new conversation."""
    session_id = str(uuid.uuid4())
    user_id = user.get("user_id")
    session = db.create_session(
        session_id,
        council_type=request.council_type,
        mode=request.mode,
        user_id=user_id,
    )
    return {
        "id": session["id"],
        "created_at": session.get("created_at", ""),
        "title": session.get("title", "New Conversation"),
        "messages": [],
        "council_type": session.get("council_type"),
        "mode": session.get("council_mode"),
    }


@app.get("/api/conversations/{conversation_id}")
async def get_conversation(conversation_id: str, _: None = Depends(require_auth)):
    """Get a specific conversation with all its messages."""
    session = db.get_session(conversation_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {
        "id": session["id"],
        "created_at": session.get("created_at", ""),
        "title": session.get("title", "New Conversation"),
        "messages": session.get("messages", []),
        "council_type": session.get("council_type"),
        "mode": session.get("council_mode"),
    }


@app.delete("/api/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str, _: None = Depends(require_auth)):
    """Delete a conversation and its attached files."""
    deleted = db.delete_session(conversation_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Conversation not found")
    # Clean up any attached files from storage
    try:
        file_handler.delete_session_files(conversation_id)
    except Exception:
        pass  # Don't fail the delete if file cleanup fails
    return {"status": "deleted", "id": conversation_id}


class ArchiveRequest(BaseModel):
    """Request to archive or unarchive a conversation."""
    is_archived: bool


@app.patch("/api/conversations/{conversation_id}/archive")
async def toggle_archive(conversation_id: str, request: ArchiveRequest, _: None = Depends(require_auth)):
    """Archive or unarchive a conversation."""
    session = db.get_session(conversation_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    db.update_session(conversation_id, is_archived=request.is_archived)
    return {
        "id": conversation_id,
        "is_archived": request.is_archived,
        "status": "archived" if request.is_archived else "unarchived"
    }


# =============================================================================
# FILE UPLOAD ENDPOINTS
# =============================================================================

@app.post("/api/conversations/{conversation_id}/upload")
async def upload_file(
    conversation_id: str,
    file: UploadFile = File(...),
    _: None = Depends(require_auth),
):
    """Upload a file attachment for a conversation."""
    session = db.get_session(conversation_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Validate file extension
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in file_handler.ALL_SUPPORTED:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Supported: images, PDF, DOCX, XLSX, text files."
        )

    # Read and upload
    content = await file.read()
    if len(content) > 20 * 1024 * 1024:  # 20MB limit
        raise HTTPException(status_code=400, detail="File too large. Maximum size is 20MB.")

    try:
        file_handler.ensure_bucket()
        result = file_handler.upload_file(
            conversation_id,
            file.filename,
            content,
            file.content_type or "application/octet-stream",
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


# =============================================================================
# MESSAGE ENDPOINTS
# =============================================================================

@app.post("/api/conversations/{conversation_id}/message")
async def send_message(conversation_id: str, request: SendMessageRequest, _: None = Depends(require_auth)):
    """
    Send a message and run the council process.

    The mode determines how the council deliberates:
    - independent: All models respond separately
    - synthesized: Responses, peer review, then chairman synthesis (default)
    - debate: Multi-round discussion
    - adversarial: 3 models + 1 devil's advocate
    - socratic: Council asks probing questions
    - scenario: Generate and analyze scenarios
    """
    # Check if conversation exists
    session = db.get_session(conversation_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Validate mode
    if request.mode not in COUNCIL_MODES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid mode '{request.mode}'. Valid modes: {list(COUNCIL_MODES.keys())}"
        )

    # Validate council type
    if request.council_type not in COUNCIL_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid council_type '{request.council_type}'. Valid types: {list(COUNCIL_TYPES.keys())}"
        )

    # Check if this is the first message
    is_first_message = len(session.get("messages", [])) == 0

    # Add user message
    db.add_message(conversation_id, "user", request.content)

    # If this is the first message, generate a title
    if is_first_message:
        title = await generate_conversation_title(request.content)
        db.update_session(conversation_id, title=title)

    # Route to appropriate mode handler
    if request.mode == "independent":
        # Independent mode: just collect responses, no ranking or synthesis
        stage1_results = await stage1_collect_responses(
            request.content,
            request.models,
            request.council_type,
            request.roles_enabled,
            request.enhancements,
            web_search=request.web_search,
            attachments=request.attachments or None
        )
        # Save assistant message with stage data
        db.add_message(
            conversation_id, "assistant",
            stage_data={"stage1": stage1_results, "mode": "independent"}
        )
        return {
            "mode": "independent",
            "responses": stage1_results,
        }

    elif request.mode == "synthesized":
        # Default 3-stage process
        stage1_results, stage2_results, stage3_result, metadata = await run_full_council(
            request.content,
            request.models,
            request.chairman_model,
            request.council_type,
            request.roles_enabled,
            request.enhancements,
            web_search=request.web_search,
            attachments=request.attachments or None
        )
        # Save complete response
        db.add_message(
            conversation_id, "assistant",
            content=stage3_result.get("synthesis", ""),
            stage_data={
                "stage1": stage1_results,
                "stage2": stage2_results,
                "stage3": stage3_result,
                "mode": "synthesized"
            }
        )
        return {
            "mode": "synthesized",
            "stage1": stage1_results,
            "stage2": stage2_results,
            "stage3": stage3_result,
            "metadata": metadata
        }

    elif request.mode == "debate":
        # Debate mode: Start round 1, store state for continuation
        round1_responses = await debate_round(
            request.content,
            [],  # No previous responses for round 1
            1,
            request.models,
            request.council_type,
            request.roles_enabled,
            web_search=request.web_search
        )

        # Store debate state in database for serverless compatibility
        db.save_conversation_state(
            session_id=conversation_id,
            mode="debate",
            query=request.content,
            rounds=[round1_responses],
            current_round=1,
            models=request.models or DEFAULT_COUNCIL_MODELS,
            chairman_model=request.chairman_model or DEFAULT_CHAIRMAN_MODEL,
            council_type=request.council_type,
            roles_enabled=request.roles_enabled,
        )

        db.add_message(
            conversation_id, "assistant",
            stage_data={"round": 1, "responses": round1_responses, "mode": "debate"},
            debate_round=1
        )
        return {
            "mode": "debate",
            "round": 1,
            "responses": round1_responses,
            "can_continue": True,
            "message": "Round 1 complete. Use /continue to start the next round, or /end to summarize."
        }

    elif request.mode == "adversarial":
        # Adversarial mode: 3 models answer, then devil's advocate critiques
        # Use first 3 models for initial responses
        models = request.models or DEFAULT_COUNCIL_MODELS
        responders = models[:3]
        devils_advocate = models[3] if len(models) > 3 else models[0]

        # Get initial responses from 3 models
        initial_responses = await stage1_collect_responses(
            request.content,
            responders,
            request.council_type,
            request.roles_enabled,
            request.enhancements,
            web_search=request.web_search,
            attachments=request.attachments or None
        )

        # Build context for devil's advocate
        responses_text = "\n\n".join([
            f"[{r.get('model_name', r['model'])}]: {r['response']}"
            for r in initial_responses
        ])

        devils_advocate_prompt = f"""The user asked: {request.content}

Three AI models have provided the following responses:

{responses_text}

You are the Devil's Advocate. Your job is to:
1. Challenge the assumptions made by the other models
2. Point out flaws, risks, or overlooked considerations in each response
3. Present counterarguments or alternative perspectives
4. Be constructively critical - aim to strengthen the final answer by stress-testing these responses

Provide your critique:"""

        from .openrouter import query_model
        critique_response = await query_model(devils_advocate, [{"role": "user", "content": devils_advocate_prompt}], web_search=request.web_search)

        critique = {
            "model": devils_advocate,
            "model_name": f"{devils_advocate.split('/')[-1]} (Devil's Advocate)",
            "response": critique_response.get('content', '') if critique_response else "Error generating critique",
            "role": "devils_advocate"
        }

        db.add_message(
            conversation_id, "assistant",
            stage_data={
                "initial_responses": initial_responses,
                "devils_advocate": critique,
                "mode": "adversarial"
            }
        )
        return {
            "mode": "adversarial",
            "initial_responses": initial_responses,
            "devils_advocate": critique,
        }

    elif request.mode == "socratic":
        # Socratic mode: Council asks probing questions
        questions = await socratic_questions(
            request.content,
            request.models,
            request.council_type,
            request.roles_enabled,
            web_search=request.web_search
        )

        # Store state in database for serverless compatibility
        db.save_conversation_state(
            session_id=conversation_id,
            mode="socratic",
            query=request.content,
            rounds=[questions],  # Store questions as first "round"
            current_round=1,
            models=request.models or DEFAULT_COUNCIL_MODELS,
            chairman_model=request.chairman_model or DEFAULT_CHAIRMAN_MODEL,
            council_type=request.council_type,
            roles_enabled=request.roles_enabled,
        )

        db.add_message(
            conversation_id, "assistant",
            stage_data={"questions": questions, "mode": "socratic"}
        )
        return {
            "mode": "socratic",
            "questions": questions,
            "message": "The council has questions for you. Answer them to get more tailored advice."
        }

    elif request.mode == "scenario":
        # Scenario planning mode
        result = await scenario_planning(
            request.content,
            request.models,
            request.chairman_model,
            request.council_type,
            web_search=request.web_search
        )

        db.add_message(
            conversation_id, "assistant",
            content=result["synthesis"].get("synthesis", ""),
            stage_data={
                "scenarios": result["scenarios"],
                "synthesis": result["synthesis"],
                "mode": "scenario"
            }
        )
        return {
            "mode": "scenario",
            "scenarios": result["scenarios"],
            "synthesis": result["synthesis"],
        }

    else:
        # Fallback to synthesized mode for any unrecognized modes
        stage1_results, stage2_results, stage3_result, metadata = await run_full_council(
            request.content,
            request.models,
            request.chairman_model,
            request.council_type,
            request.roles_enabled,
            request.enhancements,
            web_search=request.web_search,
            attachments=request.attachments or None
        )
        db.add_message(
            conversation_id, "assistant",
            content=stage3_result.get("synthesis", ""),
            stage_data={
                "stage1": stage1_results,
                "stage2": stage2_results,
                "stage3": stage3_result,
                "mode": request.mode
            }
        )
        return {
            "mode": request.mode,
            "note": f"Mode '{request.mode}' not recognized, using synthesized mode",
            "stage1": stage1_results,
            "stage2": stage2_results,
            "stage3": stage3_result,
            "metadata": metadata
        }


@app.post("/api/conversations/{conversation_id}/message/stream")
async def send_message_stream(conversation_id: str, request: SendMessageRequest, _: None = Depends(require_auth)):
    """
    Send a message and stream the council process.
    Returns Server-Sent Events as each stage completes.
    """
    # Check if conversation exists
    session = db.get_session(conversation_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Check if this is the first message
    is_first_message = len(session.get("messages", [])) == 0

    async def event_generator():
        try:
            # Send mode info
            yield f"data: {json.dumps({'type': 'mode', 'data': request.mode})}\n\n"

            # Add user message
            db.add_message(conversation_id, "user", request.content)

            # Start title generation in parallel (don't await yet)
            title_task = None
            if is_first_message:
                title_task = asyncio.create_task(generate_conversation_title(request.content))

            if request.mode == "independent":
                # Independent mode: stream individual responses as they complete
                yield f"data: {json.dumps({'type': 'stage1_start'})}\n\n"
                stage1_results = []
                async for result in stage1_collect_responses_streaming(
                    request.content,
                    request.models,
                    request.council_type,
                    request.roles_enabled,
                    request.enhancements,
                    web_search=request.web_search,
                    attachments=request.attachments or None
                ):
                    stage1_results.append(result)
                    yield f"data: {json.dumps({'type': 'stage1_model_complete', 'data': result})}\n\n"
                yield f"data: {json.dumps({'type': 'stage1_complete', 'data': stage1_results})}\n\n"

                # Save and complete
                db.add_message(
                    conversation_id, "assistant",
                    stage_data={"stage1": stage1_results, "mode": "independent"}
                )

            elif request.mode == "debate":
                # Debate mode: Start round 1, store state for continuation
                yield f"data: {json.dumps({'type': 'debate_round_start', 'round': 1})}\n\n"
                round1_responses = []
                async for result in debate_round_streaming(
                    request.content,
                    [],  # No previous responses for round 1
                    1,
                    request.models,
                    request.council_type,
                    request.roles_enabled,
                    web_search=request.web_search
                ):
                    round1_responses.append(result)
                    yield f"data: {json.dumps({'type': 'stage1_model_complete', 'data': result})}\n\n"
                yield f"data: {json.dumps({'type': 'debate_round_complete', 'round': 1, 'data': round1_responses})}\n\n"

                # Store debate state in database for serverless compatibility
                db.save_conversation_state(
                    session_id=conversation_id,
                    mode="debate",
                    query=request.content,
                    rounds=[round1_responses],
                    current_round=1,
                    models=request.models or DEFAULT_COUNCIL_MODELS,
                    chairman_model=request.chairman_model or DEFAULT_CHAIRMAN_MODEL,
                    council_type=request.council_type,
                    roles_enabled=request.roles_enabled,
                )

                db.add_message(
                    conversation_id, "assistant",
                    stage_data={"round": 1, "responses": round1_responses, "mode": "debate"},
                    debate_round=1
                )
                yield f"data: {json.dumps({'type': 'debate_can_continue', 'can_continue': True})}\n\n"

            elif request.mode == "adversarial":
                # Adversarial mode: 3 models answer, then devil's advocate critiques
                models = request.models or DEFAULT_COUNCIL_MODELS
                responders = models[:3]
                devils_advocate = models[3] if len(models) > 3 else models[0]

                # Get initial responses from 3 models with streaming
                yield f"data: {json.dumps({'type': 'stage1_start'})}\n\n"
                initial_responses = []
                async for result in stage1_collect_responses_streaming(
                    request.content,
                    responders,
                    request.council_type,
                    request.roles_enabled,
                    request.enhancements,
                    web_search=request.web_search,
                    attachments=request.attachments or None
                ):
                    initial_responses.append(result)
                    yield f"data: {json.dumps({'type': 'stage1_model_complete', 'data': result})}\n\n"
                yield f"data: {json.dumps({'type': 'stage1_complete', 'data': initial_responses})}\n\n"

                # Build context for devil's advocate
                responses_text = "\n\n".join([
                    f"[{r.get('model_name', r['model'])}]: {r['response']}"
                    for r in initial_responses
                ])

                devils_advocate_prompt = f"""The user asked: {request.content}

Three AI models have provided the following responses:

{responses_text}

You are the Devil's Advocate. Your job is to:
1. Challenge the assumptions made by the other models
2. Point out flaws, risks, or overlooked considerations in each response
3. Present counterarguments or alternative perspectives
4. Be constructively critical - aim to strengthen the final answer by stress-testing these responses

Provide your critique:"""

                yield f"data: {json.dumps({'type': 'critique_start'})}\n\n"
                from .openrouter import query_model
                critique_response = await query_model(devils_advocate, [{"role": "user", "content": devils_advocate_prompt}], web_search=request.web_search)

                critique = {
                    "model": devils_advocate,
                    "model_name": f"{devils_advocate.split('/')[-1]} (Devil's Advocate)",
                    "response": critique_response.get('content', '') if critique_response else "Error generating critique",
                    "role": "devils_advocate"
                }
                yield f"data: {json.dumps({'type': 'critique_complete', 'data': critique})}\n\n"

                db.add_message(
                    conversation_id, "assistant",
                    stage_data={
                        "initial_responses": initial_responses,
                        "devils_advocate": critique,
                        "mode": "adversarial"
                    }
                )

            elif request.mode == "socratic":
                # Socratic mode: Council asks probing questions with streaming
                yield f"data: {json.dumps({'type': 'questions_start'})}\n\n"
                questions = []
                async for result in socratic_questions_streaming(
                    request.content,
                    request.models,
                    request.council_type,
                    request.roles_enabled,
                    web_search=request.web_search
                ):
                    questions.append(result)
                    yield f"data: {json.dumps({'type': 'questions_model_complete', 'data': result})}\n\n"
                yield f"data: {json.dumps({'type': 'questions_complete', 'data': questions})}\n\n"

                # Store state in database for serverless compatibility
                db.save_conversation_state(
                    session_id=conversation_id,
                    mode="socratic",
                    query=request.content,
                    rounds=[questions],  # Store questions as first "round"
                    current_round=1,
                    models=request.models or DEFAULT_COUNCIL_MODELS,
                    chairman_model=request.chairman_model or DEFAULT_CHAIRMAN_MODEL,
                    council_type=request.council_type,
                    roles_enabled=request.roles_enabled,
                )

                db.add_message(
                    conversation_id, "assistant",
                    stage_data={"questions": questions, "mode": "socratic"}
                )

            elif request.mode == "scenario":
                # Scenario planning mode with streaming
                yield f"data: {json.dumps({'type': 'scenarios_start'})}\n\n"
                scenario_results = []
                async for result in scenario_planning_streaming(
                    request.content,
                    request.models,
                    request.council_type,
                    web_search=request.web_search
                ):
                    scenario_results.append(result)
                    yield f"data: {json.dumps({'type': 'scenario_model_complete', 'data': result})}\n\n"
                yield f"data: {json.dumps({'type': 'scenarios_complete', 'data': scenario_results})}\n\n"

                # Now synthesize the scenarios
                yield f"data: {json.dumps({'type': 'stage3_start'})}\n\n"
                synthesis = await scenario_synthesis(
                    request.content,
                    scenario_results,
                    request.chairman_model
                )
                yield f"data: {json.dumps({'type': 'stage3_complete', 'data': synthesis})}\n\n"

                db.add_message(
                    conversation_id, "assistant",
                    content=synthesis.get("response", ""),
                    stage_data={
                        "scenarios": scenario_results,
                        "synthesis": synthesis,
                        "mode": "scenario"
                    }
                )

            else:
                # Full 3-stage process (synthesized mode and fallback)
                # Stage 1: Stream individual model responses as they complete
                yield f"data: {json.dumps({'type': 'stage1_start'})}\n\n"
                stage1_results = []
                async for result in stage1_collect_responses_streaming(
                    request.content,
                    request.models,
                    request.council_type,
                    request.roles_enabled,
                    request.enhancements,
                    web_search=request.web_search,
                    attachments=request.attachments or None
                ):
                    stage1_results.append(result)
                    yield f"data: {json.dumps({'type': 'stage1_model_complete', 'data': result})}\n\n"
                yield f"data: {json.dumps({'type': 'stage1_complete', 'data': stage1_results})}\n\n"

                # Stage 2: Stream individual rankings as they complete
                yield f"data: {json.dumps({'type': 'stage2_start'})}\n\n"
                stage2_results = []
                label_to_model = {}
                async for result, ltm in stage2_collect_rankings_streaming(request.content, stage1_results):
                    stage2_results.append(result)
                    label_to_model = ltm  # Same for all, just keep updating
                    yield f"data: {json.dumps({'type': 'stage2_model_complete', 'data': result})}\n\n"
                aggregate_rankings = calculate_aggregate_rankings(stage2_results, label_to_model)
                yield f"data: {json.dumps({'type': 'stage2_complete', 'data': stage2_results, 'metadata': {'label_to_model': label_to_model, 'aggregate_rankings': aggregate_rankings}})}\n\n"

                # Stage 3: Single model synthesis
                yield f"data: {json.dumps({'type': 'stage3_start'})}\n\n"
                stage3_result = await stage3_synthesize_final(request.content, stage1_results, stage2_results)
                yield f"data: {json.dumps({'type': 'stage3_complete', 'data': stage3_result})}\n\n"

                # Save complete assistant message
                db.add_message(
                    conversation_id, "assistant",
                    content=stage3_result.get("synthesis", ""),
                    stage_data={
                        "stage1": stage1_results,
                        "stage2": stage2_results,
                        "stage3": stage3_result,
                        "mode": "synthesized"
                    }
                )

            # Wait for title generation if it was started
            if title_task:
                title = await title_task
                db.update_session(conversation_id, title=title)
                yield f"data: {json.dumps({'type': 'title_complete', 'data': {'title': title}})}\n\n"

            # Send completion event
            yield f"data: {json.dumps({'type': 'complete'})}\n\n"

        except Exception as e:
            # Send error event
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


# =============================================================================
# DEBATE ENDPOINTS (for multi-round modes)
# =============================================================================

@app.post("/api/conversations/{conversation_id}/continue")
async def continue_conversation(conversation_id: str, request: ContinueDebateRequest = None, _: None = Depends(require_auth)):
    """
    Continue a multi-round conversation (debate, adversarial, socratic).
    Triggers the next round of the council discussion.
    """
    # Check if conversation exists
    session = db.get_session(conversation_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Check if we have state for this conversation (stored in database)
    state = db.get_conversation_state(conversation_id)
    if state is None:
        raise HTTPException(
            status_code=400,
            detail="No active multi-round session for this conversation. Start a new debate/socratic query first."
        )

    mode = state["mode"]
    rounds = state.get("rounds", [])
    models = state.get("models", DEFAULT_COUNCIL_MODELS)

    if mode == "debate":
        # Execute next debate round
        current_round = state.get("current_round", 1)
        previous_responses = rounds[-1] if rounds else []

        # Get optional user clarification from request
        user_clarification = request.user_input if request and request.user_input else None

        next_round = current_round + 1
        round_responses = await debate_round(
            state["query"],
            previous_responses,
            next_round,
            models,
            state.get("council_type", "general"),
            state.get("roles_enabled", False),
            user_clarification=user_clarification
        )

        # Update state in database
        rounds.append(round_responses)
        db.save_conversation_state(
            session_id=conversation_id,
            mode="debate",
            query=state["query"],
            rounds=rounds,
            current_round=next_round,
            models=models,
            chairman_model=state.get("chairman_model", DEFAULT_CHAIRMAN_MODEL),
            council_type=state.get("council_type", "general"),
            roles_enabled=state.get("roles_enabled", False),
        )

        db.add_message(
            conversation_id, "assistant",
            stage_data={"round": next_round, "responses": round_responses, "mode": "debate"},
            debate_round=next_round
        )

        return {
            "mode": "debate",
            "round": next_round,
            "responses": round_responses,
            "total_rounds": len(rounds),
            "can_continue": True,
            "message": f"Round {next_round} complete. Use /continue for another round, or /end to summarize."
        }

    elif mode == "socratic":
        # In socratic mode, continuation means the user answered questions
        # and wants follow-up advice based on their answers
        if not request or not request.user_input:
            raise HTTPException(
                status_code=400,
                detail="Socratic mode requires user_input with your answers to the questions."
            )

        # Get advice based on the original query plus user's answers
        enriched_query = f"""Original question: {state["query"]}

The council asked clarifying questions and the user provided these answers:
{request.user_input}

Based on this additional context, please provide comprehensive advice."""

        # Run full council with the enriched context
        stage1_results, stage2_results, stage3_result, metadata = await run_full_council(
            enriched_query,
            models,
            None,  # Use default chairman
            state.get("council_type", "general"),
            state.get("roles_enabled", False)
        )

        # Clear state as socratic session is complete
        db.delete_conversation_state(conversation_id)

        db.add_message(
            conversation_id, "assistant",
            content=stage3_result.get("synthesis", ""),
            stage_data={
                "stage1": stage1_results,
                "stage2": stage2_results,
                "stage3": stage3_result,
                "mode": "socratic_response"
            }
        )

        return {
            "mode": "socratic_response",
            "stage1": stage1_results,
            "stage2": stage2_results,
            "stage3": stage3_result,
            "metadata": metadata,
            "message": "Council has provided advice based on your answers."
        }

    else:
        raise HTTPException(
            status_code=400,
            detail=f"Mode '{mode}' does not support continuation."
        )


@app.post("/api/conversations/{conversation_id}/end")
async def end_conversation(conversation_id: str, _: None = Depends(require_auth)):
    """
    End a multi-round conversation and generate final summary.
    """
    # Check if conversation exists
    session = db.get_session(conversation_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Check if we have state for this conversation (stored in database)
    state = db.get_conversation_state(conversation_id)
    if state is None:
        raise HTTPException(
            status_code=400,
            detail="No active multi-round session for this conversation."
        )

    mode = state["mode"]
    rounds = state.get("rounds", [])

    if mode == "debate":
        # Generate debate summary
        summary = await debate_summary(
            state["query"],
            rounds,
            state.get("chairman_model", DEFAULT_CHAIRMAN_MODEL),
            state.get("council_type", "general")
        )

        # Clear state
        db.delete_conversation_state(conversation_id)

        db.add_message(
            conversation_id, "assistant",
            content=summary.get("synthesis", ""),
            stage_data={"summary": summary, "mode": "debate_summary"}
        )

        return {
            "mode": "debate_summary",
            "total_rounds": len(rounds),
            "summary": summary,
            "message": "Debate concluded with summary."
        }

    elif mode == "socratic":
        # End socratic without providing answers - just clear state
        db.delete_conversation_state(conversation_id)

        return {
            "mode": "socratic_ended",
            "message": "Socratic session ended without follow-up advice."
        }

    else:
        # Clear state for any other mode
        db.delete_conversation_state(conversation_id)
        return {
            "mode": f"{mode}_ended",
            "message": f"{mode} session ended."
        }


@app.get("/api/conversations/{conversation_id}/state")
async def get_conv_state(conversation_id: str, _: None = Depends(require_auth)):
    """
    Get the current state of a multi-round conversation.
    Useful for the frontend to know if Continue/End buttons should be shown.
    """
    state = db.get_conversation_state(conversation_id)
    if state is None:
        return {
            "has_active_session": False
        }

    return {
        "has_active_session": True,
        "mode": state["mode"],
        "current_round": state.get("current_round", 0),
        "total_rounds": len(state.get("rounds", [])),
    }


# =============================================================================
# SEARCH ENDPOINT
# =============================================================================

@app.get("/api/search")
async def search_conversations(q: str, limit: int = 20, _: None = Depends(require_auth)):
    """
    Full-text search across all conversation messages.

    Uses PostgreSQL full-text search for fast, relevant search results.
    Returns messages with highlighted matches and session context.
    """
    if not q or len(q) < 2:
        raise HTTPException(status_code=400, detail="Search query must be at least 2 characters")

    results = db.search_messages(q, limit)
    return {
        "query": q,
        "results": results,
        "count": len(results)
    }


# =============================================================================
# MODEL PRESETS ENDPOINTS
# =============================================================================

class CreatePresetRequest(BaseModel):
    """Request to create a model preset."""
    name: str
    models: List[str]
    chairman_model: Optional[str] = None
    description: Optional[str] = None


@app.get("/api/presets")
async def list_presets(_: None = Depends(require_auth)):
    """List all model presets."""
    presets = db.get_presets()
    return {"presets": presets}


@app.post("/api/presets")
async def create_preset(request: CreatePresetRequest, user: dict = Depends(require_auth)):
    """Create a new model preset."""
    preset_id = str(uuid.uuid4())
    user_id = user.get("user_id")
    try:
        preset = db.create_preset(
            preset_id,
            request.name,
            request.models,
            request.chairman_model,
            request.description,
            user_id=user_id
        )
        return preset
    except Exception as e:
        if "UNIQUE constraint" in str(e) or "duplicate key" in str(e).lower():
            raise HTTPException(status_code=400, detail=f"Preset with name '{request.name}' already exists")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/presets/{preset_id}")
async def get_preset(preset_id: str, _: None = Depends(require_auth)):
    """Get a specific preset."""
    preset = db.get_preset(preset_id)
    if not preset:
        raise HTTPException(status_code=404, detail="Preset not found")
    return preset


@app.delete("/api/presets/{preset_id}")
async def delete_preset(preset_id: str, _: None = Depends(require_auth)):
    """Delete a preset (cannot delete default presets)."""
    deleted = db.delete_preset(preset_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Preset not found or is a default preset")
    return {"status": "deleted", "id": preset_id}


# =============================================================================
# PREDICTIONS ENDPOINTS
# =============================================================================

class CreatePredictionRequest(BaseModel):
    """Request to log a prediction."""
    session_id: str
    prediction_text: str
    model_name: Optional[str] = None
    message_id: Optional[str] = None
    category: Optional[str] = None


class RecordOutcomeRequest(BaseModel):
    """Request to record a prediction outcome."""
    outcome: str
    accuracy_score: Optional[float] = Field(default=None, ge=0, le=1)
    notes: Optional[str] = None


@app.post("/api/predictions")
async def create_prediction(request: CreatePredictionRequest, user: dict = Depends(require_auth)):
    """Log a prediction for later accuracy tracking."""
    prediction_id = str(uuid.uuid4())
    user_id = user.get("user_id")
    prediction = db.add_prediction(
        prediction_id,
        request.session_id,
        request.prediction_text,
        request.model_name,
        request.message_id,
        request.category,
        user_id=user_id
    )
    return prediction


@app.get("/api/predictions/{prediction_id}")
async def get_prediction(prediction_id: str, _: None = Depends(require_auth)):
    """Get a specific prediction."""
    prediction = db.get_prediction(prediction_id)
    if not prediction:
        raise HTTPException(status_code=404, detail="Prediction not found")
    return prediction


@app.put("/api/predictions/{prediction_id}/outcome")
async def record_prediction_outcome(prediction_id: str, request: RecordOutcomeRequest, _: None = Depends(require_auth)):
    """Record the outcome of a prediction."""
    # Check prediction exists
    existing = db.get_prediction(prediction_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Prediction not found")

    prediction = db.record_outcome(
        prediction_id,
        request.outcome,
        request.accuracy_score,
        request.notes
    )
    return prediction


@app.get("/api/predictions/stats")
async def get_prediction_stats(user: dict = Depends(require_auth)):
    """Get prediction accuracy statistics by model and category."""
    user_id = user.get("user_id")
    stats = db.get_prediction_stats(user_id=user_id)
    return stats


# =============================================================================
# VERCEL SERVERLESS HANDLER
# =============================================================================
# For Vercel deployment, we export the app directly
# Vercel will use the ASGI handler automatically
