"""Vercel serverless function handler - Flask-based API."""

import os
import sys
import json
import uuid
import asyncio
from pathlib import Path
from functools import wraps

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, request, jsonify, Response, stream_with_context
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# Import backend modules
from backend import supabase_db as db
from backend.council import (
    run_full_council,
    generate_conversation_title,
    stage1_collect_responses,
    stage2_collect_rankings,
    stage3_synthesize_final,
    calculate_aggregate_rankings,
    debate_round,
    debate_summary,
    socratic_questions,
    scenario_planning,
)
from backend.models_api import get_models_for_picker, clear_cache as clear_models_cache
from backend.config import (
    COUNCIL_MODES,
    COUNCIL_TYPES,
    SPECIALIST_ROLES,
    ENHANCEMENTS,
    DEFAULT_COUNCIL_MODELS,
    DEFAULT_CHAIRMAN_MODEL,
)

# Auth configuration
API_PASSWORD = os.getenv("COUNCIL_API_PASSWORD", "")
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:3000").split(",")


# =============================================================================
# CORS MIDDLEWARE
# =============================================================================

@app.after_request
def add_cors_headers(response):
    origin = request.headers.get('Origin', '')
    if origin in CORS_ORIGINS or '*' in CORS_ORIGINS:
        response.headers['Access-Control-Allow-Origin'] = origin
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, PATCH, OPTIONS'
    response.headers['Access-Control-Allow-Credentials'] = 'true'
    return response


@app.route('/api/<path:path>', methods=['OPTIONS'])
def handle_options(path):
    return '', 204


# =============================================================================
# AUTH MIDDLEWARE
# =============================================================================

def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not API_PASSWORD:
            return f(*args, **kwargs)

        auth_header = request.headers.get('Authorization', '')
        if not auth_header:
            return jsonify({"error": "Authentication required"}), 401

        parts = auth_header.split()
        if len(parts) != 2 or parts[0].lower() != 'bearer':
            return jsonify({"error": "Invalid authorization format"}), 401

        if parts[1] != API_PASSWORD:
            return jsonify({"error": "Invalid password"}), 401

        return f(*args, **kwargs)
    return decorated


# Helper to run async functions
def run_async(coro):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# =============================================================================
# HEALTH & CONFIG ENDPOINTS
# =============================================================================

@app.route('/')
@app.route('/api/')
def root():
    return jsonify({"status": "ok", "service": "LLM Council API", "version": "2.0.0"})


@app.route('/api/auth/verify', methods=['POST'])
def verify_auth():
    """Verify password and return auth status."""
    data = request.get_json() or {}
    password = data.get('password', '')

    if not API_PASSWORD:
        return jsonify({"authenticated": True, "message": "No password required"})

    if password == API_PASSWORD:
        return jsonify({"authenticated": True})

    return jsonify({"authenticated": False, "error": "Invalid password"}), 401


@app.route('/api/config')
def get_config():
    return jsonify({
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
    })


# =============================================================================
# MODELS ENDPOINTS
# =============================================================================

@app.route('/api/models')
def list_models():
    try:
        models = run_async(get_models_for_picker())
        return jsonify({
            "models": models,
            "count": len(models),
            "defaults": DEFAULT_COUNCIL_MODELS,
            "default_chairman": DEFAULT_CHAIRMAN_MODEL,
        })
    except Exception as e:
        return jsonify({"error": f"Failed to fetch models: {str(e)}"}), 500


# =============================================================================
# CONVERSATION ENDPOINTS
# =============================================================================

@app.route('/api/conversations', methods=['GET'])
@require_auth
def list_conversations():
    include_archived = request.args.get('include_archived', 'false').lower() == 'true'
    sessions = db.list_sessions(include_archived=include_archived)
    return jsonify([
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
    ])


@app.route('/api/conversations', methods=['POST'])
@require_auth
def create_conversation():
    data = request.get_json() or {}
    session_id = str(uuid.uuid4())
    session = db.create_session(
        session_id,
        council_type=data.get('council_type', 'general'),
        mode=data.get('mode', 'synthesized'),
    )
    return jsonify({
        "id": session["id"],
        "created_at": session.get("created_at", ""),
        "title": session.get("title", "New Conversation"),
        "messages": [],
        "council_type": session.get("council_type"),
        "mode": session.get("council_mode"),
    })


@app.route('/api/conversations/<conversation_id>', methods=['GET'])
@require_auth
def get_conversation(conversation_id):
    session = db.get_session(conversation_id)
    if session is None:
        return jsonify({"error": "Conversation not found"}), 404
    return jsonify({
        "id": session["id"],
        "created_at": session.get("created_at", ""),
        "title": session.get("title", "New Conversation"),
        "messages": session.get("messages", []),
        "council_type": session.get("council_type"),
        "mode": session.get("council_mode"),
    })


@app.route('/api/conversations/<conversation_id>', methods=['DELETE'])
@require_auth
def delete_conversation(conversation_id):
    deleted = db.delete_session(conversation_id)
    if not deleted:
        return jsonify({"error": "Conversation not found"}), 404
    return jsonify({"status": "deleted", "id": conversation_id})


@app.route('/api/conversations/<conversation_id>/archive', methods=['PATCH'])
@require_auth
def toggle_archive(conversation_id):
    """Archive or unarchive a conversation."""
    session = db.get_session(conversation_id)
    if session is None:
        return jsonify({"error": "Conversation not found"}), 404

    data = request.get_json() or {}
    is_archived = data.get('is_archived', True)

    db.update_session(conversation_id, is_archived=is_archived)
    return jsonify({
        "id": conversation_id,
        "is_archived": is_archived,
        "status": "archived" if is_archived else "unarchived"
    })


# =============================================================================
# MESSAGE ENDPOINTS
# =============================================================================

@app.route('/api/conversations/<conversation_id>/message', methods=['POST'])
@require_auth
def send_message(conversation_id):
    session = db.get_session(conversation_id)
    if session is None:
        return jsonify({"error": "Conversation not found"}), 404

    data = request.get_json() or {}
    content = data.get('content', '')
    mode = data.get('mode', 'synthesized')
    council_type = data.get('council_type', 'general')
    models = data.get('models')
    chairman_model = data.get('chairman_model')
    roles_enabled = data.get('roles_enabled', False)
    enhancements = data.get('enhancements', [])

    # Validate mode
    if mode not in COUNCIL_MODES:
        return jsonify({"error": f"Invalid mode '{mode}'"}), 400

    # Check if first message
    is_first_message = len(session.get("messages", [])) == 0

    # Add user message
    db.add_message(conversation_id, "user", content)

    # Generate title if first message
    if is_first_message:
        title = run_async(generate_conversation_title(content))
        db.update_session(conversation_id, title=title)

    # Helper to create content summary
    def make_summary(responses, prefix=""):
        parts = []
        for r in responses:
            resp = r.get('response', '')
            name = r.get('model_name', r.get('model', 'Model'))
            if len(resp) > 500:
                parts.append(f"**{name}**: {resp[:500]}...")
            else:
                parts.append(f"**{name}**: {resp}")
        return prefix + "\n\n---\n\n".join(parts)

    # Route to mode handler
    if mode == "independent":
        stage1_results = run_async(stage1_collect_responses(
            content, models, council_type, roles_enabled, enhancements
        ))
        summary = make_summary(stage1_results)
        db.add_message(
            conversation_id, "assistant",
            content=summary,
            stage_data={"stage1": stage1_results, "mode": "independent"}
        )
        return jsonify({
            "mode": "independent",
            "responses": stage1_results,
        })

    elif mode == "synthesized":
        stage1_results, stage2_results, stage3_result, metadata = run_async(
            run_full_council(content, models, chairman_model, council_type, roles_enabled, enhancements)
        )
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
        return jsonify({
            "mode": "synthesized",
            "stage1": stage1_results,
            "stage2": stage2_results,
            "stage3": stage3_result,
            "metadata": metadata
        })

    elif mode == "debate":
        round1_responses = run_async(debate_round(
            content, [], 1, models, council_type, roles_enabled
        ))

        db.save_conversation_state(
            session_id=conversation_id,
            mode="debate",
            query=content,
            rounds=[round1_responses],
            current_round=1,
            models=models or DEFAULT_COUNCIL_MODELS,
            chairman_model=chairman_model or DEFAULT_CHAIRMAN_MODEL,
            council_type=council_type,
            roles_enabled=roles_enabled,
        )

        summary = make_summary(round1_responses, "**Debate Round 1**\n\n")
        db.add_message(
            conversation_id, "assistant",
            content=summary,
            stage_data={"round": 1, "responses": round1_responses, "mode": "debate"},
            debate_round=1
        )
        return jsonify({
            "mode": "debate",
            "round": 1,
            "responses": round1_responses,
            "can_continue": True,
            "message": "Round 1 complete. Use /continue to start the next round, or /end to summarize."
        })

    elif mode == "adversarial":
        models_list = models or DEFAULT_COUNCIL_MODELS
        responders = models_list[:3]
        devils_advocate = models_list[3] if len(models_list) > 3 else models_list[0]

        initial_responses = run_async(stage1_collect_responses(
            content, responders, council_type, roles_enabled, enhancements
        ))

        responses_text = "\n\n".join([
            f"[{r.get('model_name', r['model'])}]: {r['response']}"
            for r in initial_responses
        ])

        devils_advocate_prompt = f"""The user asked: {content}

Three AI models have provided the following responses:

{responses_text}

You are the Devil's Advocate. Your job is to:
1. Challenge the assumptions made by the other models
2. Point out flaws, risks, or overlooked considerations
3. Present counterarguments or alternative perspectives
4. Be constructively critical

Provide your critique:"""

        from backend.openrouter import query_model
        critique_response = run_async(query_model(
            devils_advocate, [{"role": "user", "content": devils_advocate_prompt}]
        ))

        critique = {
            "model": devils_advocate,
            "model_name": f"{devils_advocate.split('/')[-1]} (Devil's Advocate)",
            "response": critique_response.get('content', '') if critique_response else "Error",
            "role": "devils_advocate"
        }

        # Create summary with initial responses + critique
        summary = "**Initial Responses:**\n\n" + make_summary(initial_responses)
        summary += f"\n\n---\n\n**Devil's Advocate ({critique['model_name']}):**\n\n{critique['response']}"
        db.add_message(
            conversation_id, "assistant",
            content=summary,
            stage_data={
                "initial_responses": initial_responses,
                "devils_advocate": critique,
                "mode": "adversarial"
            }
        )
        return jsonify({
            "mode": "adversarial",
            "initial_responses": initial_responses,
            "devils_advocate": critique,
        })

    elif mode == "socratic":
        questions = run_async(socratic_questions(content, models, council_type, roles_enabled))

        db.save_conversation_state(
            session_id=conversation_id,
            mode="socratic",
            query=content,
            rounds=[questions],
            current_round=1,
            models=models or DEFAULT_COUNCIL_MODELS,
            chairman_model=chairman_model or DEFAULT_CHAIRMAN_MODEL,
            council_type=council_type,
            roles_enabled=roles_enabled,
        )

        # Create summary of questions
        questions_summary = "**The Council asks:**\n\n" + make_summary(questions)
        db.add_message(
            conversation_id, "assistant",
            content=questions_summary,
            stage_data={"questions": questions, "mode": "socratic"}
        )
        return jsonify({
            "mode": "socratic",
            "questions": questions,
            "message": "The council has questions for you."
        })

    elif mode == "scenario":
        result = run_async(scenario_planning(content, models, chairman_model, council_type))

        db.add_message(
            conversation_id, "assistant",
            content=result["synthesis"].get("synthesis", ""),
            stage_data={
                "scenarios": result["scenarios"],
                "synthesis": result["synthesis"],
                "mode": "scenario"
            }
        )
        return jsonify({
            "mode": "scenario",
            "scenarios": result["scenarios"],
            "synthesis": result["synthesis"],
        })

    else:
        # Fallback to synthesized
        stage1_results, stage2_results, stage3_result, metadata = run_async(
            run_full_council(content, models, chairman_model, council_type, roles_enabled, enhancements)
        )
        db.add_message(
            conversation_id, "assistant",
            content=stage3_result.get("synthesis", ""),
            stage_data={
                "stage1": stage1_results,
                "stage2": stage2_results,
                "stage3": stage3_result,
                "mode": mode
            }
        )
        return jsonify({
            "mode": mode,
            "stage1": stage1_results,
            "stage2": stage2_results,
            "stage3": stage3_result,
            "metadata": metadata
        })


@app.route('/api/conversations/<conversation_id>/message/stream', methods=['POST'])
@require_auth
def send_message_stream(conversation_id):
    """Send a message and stream the council process using Server-Sent Events."""
    session = db.get_session(conversation_id)
    if session is None:
        return jsonify({"error": "Conversation not found"}), 404

    data = request.get_json() or {}
    content = data.get('content', '')
    mode = data.get('mode', 'synthesized')
    council_type = data.get('council_type', 'general')
    models = data.get('models')
    chairman_model = data.get('chairman_model')
    roles_enabled = data.get('roles_enabled', False)
    enhancements = data.get('enhancements', [])

    is_first_message = len(session.get("messages", [])) == 0

    def generate():
        try:
            # Send mode info
            yield f"data: {json.dumps({'type': 'mode', 'data': mode})}\n\n"

            # Add user message
            db.add_message(conversation_id, "user", content)

            # Generate title if first message
            if is_first_message:
                title = run_async(generate_conversation_title(content))
                db.update_session(conversation_id, title=title)
                yield f"data: {json.dumps({'type': 'title_complete', 'data': {'title': title}})}\n\n"

            if mode == "independent":
                yield f"data: {json.dumps({'type': 'stage1_start'})}\n\n"
                stage1_results = run_async(stage1_collect_responses(
                    content, models, council_type, roles_enabled, enhancements
                ))
                yield f"data: {json.dumps({'type': 'stage1_complete', 'data': stage1_results})}\n\n"

                # Create summary content for storage
                summary = "\n\n---\n\n".join([
                    f"**{r.get('model_name', r['model'])}**: {r['response'][:500]}..."
                    if len(r.get('response', '')) > 500 else f"**{r.get('model_name', r['model'])}**: {r.get('response', '')}"
                    for r in stage1_results
                ])
                db.add_message(
                    conversation_id, "assistant",
                    content=summary,
                    stage_data={"stage1": stage1_results, "mode": "independent"}
                )

            elif mode == "debate":
                # Debate mode: Round 1 - independent responses
                yield f"data: {json.dumps({'type': 'debate_round_start', 'round': 1})}\n\n"
                round1_responses = run_async(debate_round(
                    content, [], 1, models, council_type, roles_enabled
                ))
                yield f"data: {json.dumps({'type': 'debate_round_complete', 'round': 1, 'data': round1_responses})}\n\n"

                # Save state for continuation
                db.save_conversation_state(
                    session_id=conversation_id,
                    mode="debate",
                    query=content,
                    rounds=[round1_responses],
                    current_round=1,
                    models=models or DEFAULT_COUNCIL_MODELS,
                    chairman_model=chairman_model or DEFAULT_CHAIRMAN_MODEL,
                    council_type=council_type,
                    roles_enabled=roles_enabled,
                )

                # Create summary content for storage
                summary = f"**Debate Round 1**\n\n" + "\n\n---\n\n".join([
                    f"**{r.get('model_name', r['model'])}**: {r.get('response', '')[:500]}..."
                    if len(r.get('response', '')) > 500 else f"**{r.get('model_name', r['model'])}**: {r.get('response', '')}"
                    for r in round1_responses
                ])
                db.add_message(
                    conversation_id, "assistant",
                    content=summary,
                    stage_data={"round": 1, "responses": round1_responses, "mode": "debate"},
                    debate_round=1
                )

                yield f"data: {json.dumps({'type': 'debate_can_continue', 'message': 'Round 1 complete. Use Continue for more rounds or End to summarize.'})}\n\n"

            elif mode == "synthesized":
                # Synthesized mode: 3-stage process
                yield f"data: {json.dumps({'type': 'stage1_start'})}\n\n"
                stage1_results = run_async(stage1_collect_responses(
                    content, models, council_type, roles_enabled, enhancements
                ))
                yield f"data: {json.dumps({'type': 'stage1_complete', 'data': stage1_results})}\n\n"

                yield f"data: {json.dumps({'type': 'stage2_start'})}\n\n"
                stage2_results, label_to_model = run_async(stage2_collect_rankings(content, stage1_results))
                aggregate_rankings = calculate_aggregate_rankings(stage2_results, label_to_model)
                yield f"data: {json.dumps({'type': 'stage2_complete', 'data': stage2_results, 'metadata': {'label_to_model': label_to_model, 'aggregate_rankings': aggregate_rankings}})}\n\n"

                yield f"data: {json.dumps({'type': 'stage3_start'})}\n\n"
                stage3_result = run_async(stage3_synthesize_final(content, stage1_results, stage2_results))
                yield f"data: {json.dumps({'type': 'stage3_complete', 'data': stage3_result})}\n\n"

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

            elif mode == "adversarial":
                # Adversarial mode: 3 responses + devil's advocate critique
                models_list = models or DEFAULT_COUNCIL_MODELS
                responders = models_list[:3]
                devils_advocate = models_list[3] if len(models_list) > 3 else models_list[0]

                yield f"data: {json.dumps({'type': 'stage1_start'})}\n\n"
                initial_responses = run_async(stage1_collect_responses(
                    content, responders, council_type, roles_enabled, enhancements
                ))
                yield f"data: {json.dumps({'type': 'stage1_complete', 'data': initial_responses})}\n\n"

                # Devil's advocate critique
                yield f"data: {json.dumps({'type': 'critique_start'})}\n\n"
                responses_text = "\n\n".join([
                    f"[{r.get('model_name', r['model'])}]: {r['response']}"
                    for r in initial_responses
                ])

                devils_advocate_prompt = f"""The user asked: {content}

Three AI models have provided the following responses:

{responses_text}

You are the Devil's Advocate. Your job is to:
1. Challenge the assumptions made by the other models
2. Point out flaws, risks, or overlooked considerations
3. Present counterarguments or alternative perspectives
4. Be constructively critical

Provide your critique:"""

                from backend.openrouter import query_model
                critique_response = run_async(query_model(
                    devils_advocate, [{"role": "user", "content": devils_advocate_prompt}]
                ))

                critique = {
                    "model": devils_advocate,
                    "model_name": f"{devils_advocate.split('/')[-1]} (Devil's Advocate)",
                    "response": critique_response.get('content', '') if critique_response else "Error generating critique",
                    "role": "devils_advocate"
                }
                yield f"data: {json.dumps({'type': 'critique_complete', 'data': critique})}\n\n"

                # Save to database
                summary = "**Initial Responses:**\n\n" + "\n\n---\n\n".join([
                    f"**{r.get('model_name', r['model'])}**: {r.get('response', '')[:500]}..."
                    if len(r.get('response', '')) > 500 else f"**{r.get('model_name', r['model'])}**: {r.get('response', '')}"
                    for r in initial_responses
                ])
                summary += f"\n\n---\n\n**Devil's Advocate ({critique['model_name']}):**\n\n{critique['response']}"
                db.add_message(
                    conversation_id, "assistant",
                    content=summary,
                    stage_data={
                        "initial_responses": initial_responses,
                        "devils_advocate": critique,
                        "mode": "adversarial"
                    }
                )

            elif mode == "socratic":
                # Socratic mode: council asks questions
                yield f"data: {json.dumps({'type': 'questions_start'})}\n\n"
                questions = run_async(socratic_questions(content, models, council_type, roles_enabled))
                yield f"data: {json.dumps({'type': 'questions_complete', 'data': questions})}\n\n"

                # Save state for continuation
                db.save_conversation_state(
                    session_id=conversation_id,
                    mode="socratic",
                    query=content,
                    rounds=[questions],
                    current_round=1,
                    models=models or DEFAULT_COUNCIL_MODELS,
                    chairman_model=chairman_model or DEFAULT_CHAIRMAN_MODEL,
                    council_type=council_type,
                    roles_enabled=roles_enabled,
                )

                # Save to database
                questions_summary = "**The Council asks:**\n\n" + "\n\n---\n\n".join([
                    f"**{q.get('model_name', q['model'])}**: {q.get('response', '')}"
                    for q in questions
                ])
                db.add_message(
                    conversation_id, "assistant",
                    content=questions_summary,
                    stage_data={"questions": questions, "mode": "socratic"}
                )

            elif mode == "scenario":
                # Scenario planning mode
                yield f"data: {json.dumps({'type': 'scenarios_start'})}\n\n"
                result = run_async(scenario_planning(content, models, chairman_model, council_type))
                yield f"data: {json.dumps({'type': 'scenarios_complete', 'data': result['scenarios']})}\n\n"

                yield f"data: {json.dumps({'type': 'stage3_start'})}\n\n"
                yield f"data: {json.dumps({'type': 'stage3_complete', 'data': result['synthesis']})}\n\n"

                db.add_message(
                    conversation_id, "assistant",
                    content=result["synthesis"].get("response", ""),
                    stage_data={
                        "scenarios": result["scenarios"],
                        "synthesis": result["synthesis"],
                        "mode": "scenario"
                    }
                )

            else:
                # Unknown mode - fallback error
                yield f"data: {json.dumps({'type': 'error', 'message': f'Unknown mode: {mode}'})}\n\n"

            yield f"data: {json.dumps({'type': 'complete'})}\n\n"

        except Exception as e:
            import traceback
            error_detail = traceback.format_exc()
            yield f"data: {json.dumps({'type': 'error', 'message': str(e), 'detail': error_detail})}\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no',
        }
    )


# =============================================================================
# DEBATE ENDPOINTS
# =============================================================================

@app.route('/api/conversations/<conversation_id>/continue', methods=['POST'])
@require_auth
def continue_conversation(conversation_id):
    session = db.get_session(conversation_id)
    if session is None:
        return jsonify({"error": "Conversation not found"}), 404

    state = db.get_conversation_state(conversation_id)
    if state is None:
        return jsonify({"error": "No active multi-round session"}), 400

    data = request.get_json() or {}
    mode = state["mode"]
    rounds = state.get("rounds", [])
    models = state.get("models", DEFAULT_COUNCIL_MODELS)

    if mode == "debate":
        current_round = state.get("current_round", 1)
        previous_responses = rounds[-1] if rounds else []
        next_round = current_round + 1

        round_responses = run_async(debate_round(
            state["query"],
            previous_responses,
            next_round,
            models,
            state.get("council_type", "general"),
            state.get("roles_enabled", False)
        ))

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

        # Create summary content for this round
        round_summary = f"**Debate Round {next_round}**\n\n" + "\n\n---\n\n".join([
            f"**{r.get('model_name', r.get('model', 'Model'))}**: {r.get('response', '')[:500]}..."
            if len(r.get('response', '')) > 500 else f"**{r.get('model_name', r.get('model', 'Model'))}**: {r.get('response', '')}"
            for r in round_responses
        ])
        db.add_message(
            conversation_id, "assistant",
            content=round_summary,
            stage_data={"round": next_round, "responses": round_responses, "mode": "debate"},
            debate_round=next_round
        )

        return jsonify({
            "mode": "debate",
            "round": next_round,
            "responses": round_responses,
            "total_rounds": len(rounds),
            "can_continue": True,
        })

    elif mode == "socratic":
        user_input = data.get('user_input')
        if not user_input:
            return jsonify({"error": "Socratic mode requires user_input"}), 400

        enriched_query = f"""Original question: {state["query"]}

The council asked clarifying questions and the user provided these answers:
{user_input}

Based on this additional context, please provide comprehensive advice."""

        stage1_results, stage2_results, stage3_result, metadata = run_async(
            run_full_council(enriched_query, models, None, state.get("council_type", "general"), state.get("roles_enabled", False))
        )

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

        return jsonify({
            "mode": "socratic_response",
            "stage1": stage1_results,
            "stage2": stage2_results,
            "stage3": stage3_result,
            "metadata": metadata,
        })

    return jsonify({"error": f"Mode '{mode}' does not support continuation"}), 400


@app.route('/api/conversations/<conversation_id>/end', methods=['POST'])
@require_auth
def end_conversation(conversation_id):
    session = db.get_session(conversation_id)
    if session is None:
        return jsonify({"error": "Conversation not found"}), 404

    state = db.get_conversation_state(conversation_id)
    if state is None:
        return jsonify({"error": "No active multi-round session"}), 400

    mode = state["mode"]
    rounds = state.get("rounds", [])

    if mode == "debate":
        summary = run_async(debate_summary(
            state["query"],
            rounds,
            state.get("chairman_model", DEFAULT_CHAIRMAN_MODEL),
            state.get("council_type", "general")
        ))

        db.delete_conversation_state(conversation_id)

        # debate_summary returns {"model": ..., "response": ...} not {"synthesis": ...}
        summary_content = f"**Debate Summary** (by {summary.get('model_name', 'Chairman')})\n\n{summary.get('response', '')}"
        db.add_message(
            conversation_id, "assistant",
            content=summary_content,
            stage_data={"summary": summary, "mode": "debate_summary"}
        )

        return jsonify({
            "mode": "debate_summary",
            "total_rounds": len(rounds),
            "summary": summary,
        })

    db.delete_conversation_state(conversation_id)
    return jsonify({"mode": f"{mode}_ended"})


@app.route('/api/conversations/<conversation_id>/state', methods=['GET'])
@require_auth
def get_conv_state(conversation_id):
    state = db.get_conversation_state(conversation_id)
    if state is None:
        return jsonify({"has_active_session": False})

    return jsonify({
        "has_active_session": True,
        "mode": state["mode"],
        "current_round": state.get("current_round", 0),
        "total_rounds": len(state.get("rounds", [])),
    })


# =============================================================================
# SEARCH ENDPOINT
# =============================================================================

@app.route('/api/search')
@require_auth
def search_conversations():
    q = request.args.get('q', '')
    limit = int(request.args.get('limit', 20))

    if not q or len(q) < 2:
        return jsonify({"error": "Search query must be at least 2 characters"}), 400

    results = db.search_messages(q, limit)
    return jsonify({
        "query": q,
        "results": results,
        "count": len(results)
    })


# =============================================================================
# PRESETS ENDPOINTS
# =============================================================================

@app.route('/api/presets', methods=['GET'])
@require_auth
def list_presets():
    presets = db.get_presets()
    return jsonify({"presets": presets})


@app.route('/api/presets', methods=['POST'])
@require_auth
def create_preset():
    data = request.get_json() or {}
    preset_id = str(uuid.uuid4())

    try:
        preset = db.create_preset(
            preset_id,
            data.get('name', 'Unnamed'),
            data.get('models', []),
            data.get('chairman_model'),
            data.get('description')
        )
        return jsonify(preset)
    except Exception as e:
        if "UNIQUE" in str(e) or "duplicate" in str(e).lower():
            return jsonify({"error": f"Preset with name already exists"}), 400
        return jsonify({"error": str(e)}), 500


@app.route('/api/presets/<preset_id>', methods=['GET'])
@require_auth
def get_preset(preset_id):
    preset = db.get_preset(preset_id)
    if not preset:
        return jsonify({"error": "Preset not found"}), 404
    return jsonify(preset)


@app.route('/api/presets/<preset_id>', methods=['DELETE'])
@require_auth
def delete_preset(preset_id):
    deleted = db.delete_preset(preset_id)
    if not deleted:
        return jsonify({"error": "Preset not found or is default"}), 404
    return jsonify({"status": "deleted", "id": preset_id})


# =============================================================================
# PREDICTIONS ENDPOINTS
# =============================================================================

@app.route('/api/predictions', methods=['POST'])
@require_auth
def create_prediction():
    data = request.get_json() or {}
    prediction_id = str(uuid.uuid4())
    prediction = db.add_prediction(
        prediction_id,
        data.get('session_id'),
        data.get('prediction_text'),
        data.get('model_name'),
        data.get('message_id'),
        data.get('category')
    )
    return jsonify(prediction)


@app.route('/api/predictions/<prediction_id>', methods=['GET'])
@require_auth
def get_prediction(prediction_id):
    prediction = db.get_prediction(prediction_id)
    if not prediction:
        return jsonify({"error": "Prediction not found"}), 404
    return jsonify(prediction)


@app.route('/api/predictions/<prediction_id>/outcome', methods=['PUT'])
@require_auth
def record_prediction_outcome(prediction_id):
    existing = db.get_prediction(prediction_id)
    if not existing:
        return jsonify({"error": "Prediction not found"}), 404

    data = request.get_json() or {}
    prediction = db.record_outcome(
        prediction_id,
        data.get('outcome'),
        data.get('accuracy_score'),
        data.get('notes')
    )
    return jsonify(prediction)


@app.route('/api/predictions/stats', methods=['GET'])
@require_auth
def get_prediction_stats():
    stats = db.get_prediction_stats()
    return jsonify(stats)


# Vercel expects 'app' to be the WSGI application
# This works for Flask
