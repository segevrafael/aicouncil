"""LLM Council orchestration with multiple modes and role support."""

from typing import List, Dict, Any, Tuple, Optional, AsyncGenerator
from .openrouter import query_models_parallel, query_models_streaming, query_model
from .config import (
    DEFAULT_COUNCIL_MODELS,
    DEFAULT_CHAIRMAN_MODEL,
    COUNCIL_TYPES,
    SPECIALIST_ROLES,
    DEFAULT_ROLE_ASSIGNMENTS,
    ENHANCEMENTS,
)


# =============================================================================
# PROMPT BUILDING
# =============================================================================

def build_system_prompt(
    council_type: str = "general",
    role: Optional[str] = None,
    enhancements: Optional[List[str]] = None
) -> str:
    """
    Build a system prompt combining council type, role, and enhancements.

    Args:
        council_type: The council type (business_strategy, code_review, etc.)
        role: Optional specialist role (optimist, skeptic, pragmatist, innovator)
        enhancements: List of enhancement keys to include

    Returns:
        Complete system prompt string
    """
    # Get base prompt from council type
    type_config = COUNCIL_TYPES.get(council_type, COUNCIL_TYPES["general"])
    prompt_parts = [type_config["system_prompt"]]

    # Add role perspective if specified
    if role and role in SPECIALIST_ROLES:
        role_config = SPECIALIST_ROLES[role]
        prompt_parts.append(f"\n\nYour perspective as {role_config['name']}: {role_config['prompt']}")

    # Add enhancement instructions
    if enhancements:
        for enhancement_key in enhancements:
            if enhancement_key in ENHANCEMENTS:
                prompt_parts.append(ENHANCEMENTS[enhancement_key]["prompt_addition"])

    return "".join(prompt_parts)


def get_role_for_model(model_id: str, roles_enabled: bool = False) -> Optional[str]:
    """
    Get the assigned role for a model.

    Args:
        model_id: The model identifier
        roles_enabled: Whether roles are enabled

    Returns:
        Role key or None
    """
    if not roles_enabled:
        return None

    return DEFAULT_ROLE_ASSIGNMENTS.get(model_id)


def get_model_display_name(model_id: str) -> str:
    """Get a friendly display name for a model."""
    # Extract the model name from the ID (e.g., "openai/gpt-5.2" -> "GPT-5.2")
    if "/" in model_id:
        provider, name = model_id.split("/", 1)
        # Capitalize appropriately
        name = name.replace("-", " ").title().replace(" ", "-")
        return name
    return model_id


# =============================================================================
# STAGE 1: COLLECT RESPONSES
# =============================================================================

async def stage1_collect_responses(
    user_query: str,
    models: Optional[List[str]] = None,
    council_type: str = "general",
    roles_enabled: bool = False,
    enhancements: Optional[List[str]] = None
) -> List[Dict[str, Any]]:
    """
    Stage 1: Collect individual responses from all council models.

    Args:
        user_query: The user's question
        models: List of model IDs to query (uses defaults if None)
        council_type: Council type for system prompt
        roles_enabled: Whether to use specialist roles
        enhancements: List of enhancement keys

    Returns:
        List of dicts with 'model', 'response', 'role' keys
    """
    models = models or DEFAULT_COUNCIL_MODELS

    # Build messages with role-specific system prompts
    model_messages = {}
    model_roles = {}

    for model in models:
        role = get_role_for_model(model, roles_enabled)
        model_roles[model] = role

        system_prompt = build_system_prompt(council_type, role, enhancements)
        model_messages[model] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_query}
        ]

    # Query all models in parallel
    responses = await query_models_parallel(models, model_messages)

    # Format results
    stage1_results = []
    for model, response in responses.items():
        if response is not None:
            role = model_roles.get(model)
            result = {
                "model": model,
                "model_name": get_model_display_name(model),
                "response": response.get('content', ''),
            }
            if role:
                result["role"] = role
                result["role_name"] = SPECIALIST_ROLES[role]["name"]
            stage1_results.append(result)

    return stage1_results


async def stage1_collect_responses_streaming(
    user_query: str,
    models: Optional[List[str]] = None,
    council_type: str = "general",
    roles_enabled: bool = False,
    enhancements: Optional[List[str]] = None
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    Stage 1: Collect individual responses, yielding each as it completes.

    Args:
        user_query: The user's question
        models: List of model IDs to query (uses defaults if None)
        council_type: Council type for system prompt
        roles_enabled: Whether to use specialist roles
        enhancements: List of enhancement keys

    Yields:
        Dict with 'model', 'response', 'role' keys as each model completes
    """
    models = models or DEFAULT_COUNCIL_MODELS

    # Build messages with role-specific system prompts
    model_messages = {}
    model_roles = {}

    for model in models:
        role = get_role_for_model(model, roles_enabled)
        model_roles[model] = role

        system_prompt = build_system_prompt(council_type, role, enhancements)
        model_messages[model] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_query}
        ]

    # Stream results as each model completes
    async for model, response in query_models_streaming(models, model_messages):
        if response is not None:
            role = model_roles.get(model)
            result = {
                "model": model,
                "model_name": get_model_display_name(model),
                "response": response.get('content', ''),
            }
            if role:
                result["role"] = role
                result["role_name"] = SPECIALIST_ROLES[role]["name"]
            yield result


# =============================================================================
# STAGE 2: PEER RANKINGS
# =============================================================================

async def stage2_collect_rankings(
    user_query: str,
    stage1_results: List[Dict[str, Any]],
    models: Optional[List[str]] = None
) -> Tuple[List[Dict[str, Any]], Dict[str, str]]:
    """
    Stage 2: Each model ranks the anonymized responses.

    Args:
        user_query: The original user query
        stage1_results: Results from Stage 1
        models: List of model IDs (uses defaults if None)

    Returns:
        Tuple of (rankings list, label_to_model mapping)
    """
    models = models or DEFAULT_COUNCIL_MODELS

    # Create anonymized labels for responses (Response A, Response B, etc.)
    labels = [chr(65 + i) for i in range(len(stage1_results))]

    # Create mapping from label to model name
    label_to_model = {
        f"Response {label}": result['model']
        for label, result in zip(labels, stage1_results)
    }

    # Build the ranking prompt
    responses_text = "\n\n".join([
        f"Response {label}:\n{result['response']}"
        for label, result in zip(labels, stage1_results)
    ])

    ranking_prompt = f"""You are evaluating different responses to the following question:

Question: {user_query}

Here are the responses from different models (anonymized):

{responses_text}

Your task:
1. First, evaluate each response individually. For each response, explain what it does well and what it does poorly.
2. Then, at the very end of your response, provide a final ranking.

IMPORTANT: Your final ranking MUST be formatted EXACTLY as follows:
- Start with the line "FINAL RANKING:" (all caps, with colon)
- Then list the responses from best to worst as a numbered list
- Each line should be: number, period, space, then ONLY the response label (e.g., "1. Response A")
- Do not add any other text or explanations in the ranking section

Example format:
FINAL RANKING:
1. Response C
2. Response A
3. Response B

Now provide your evaluation and ranking:"""

    messages = [{"role": "user", "content": ranking_prompt}]

    # Get rankings from all council models in parallel
    responses = await query_models_parallel(models, messages)

    # Format results
    stage2_results = []
    for model, response in responses.items():
        if response is not None:
            full_text = response.get('content', '')
            parsed = parse_ranking_from_text(full_text)
            stage2_results.append({
                "model": model,
                "model_name": get_model_display_name(model),
                "ranking": full_text,
                "parsed_ranking": parsed
            })

    return stage2_results, label_to_model


async def stage2_collect_rankings_streaming(
    user_query: str,
    stage1_results: List[Dict[str, Any]],
    models: Optional[List[str]] = None
) -> AsyncGenerator[Tuple[Dict[str, Any], Dict[str, str]], None]:
    """
    Stage 2: Each model ranks the anonymized responses, yielding as each completes.

    Args:
        user_query: The original user query
        stage1_results: Results from Stage 1
        models: List of model IDs (uses defaults if None)

    Yields:
        Tuple of (ranking_dict, label_to_model mapping) as each model completes
    """
    models = models or DEFAULT_COUNCIL_MODELS

    # Create anonymized labels for responses (Response A, Response B, etc.)
    labels = [chr(65 + i) for i in range(len(stage1_results))]

    # Create mapping from label to model name
    label_to_model = {
        f"Response {label}": result['model']
        for label, result in zip(labels, stage1_results)
    }

    # Build the ranking prompt
    responses_text = "\n\n".join([
        f"Response {label}:\n{result['response']}"
        for label, result in zip(labels, stage1_results)
    ])

    ranking_prompt = f"""You are evaluating different responses to the following question:

Question: {user_query}

Here are the responses from different models (anonymized):

{responses_text}

Your task:
1. First, evaluate each response individually. For each response, explain what it does well and what it does poorly.
2. Then, at the very end of your response, provide a final ranking.

IMPORTANT: Your final ranking MUST be formatted EXACTLY as follows:
- Start with the line "FINAL RANKING:" (all caps, with colon)
- Then list the responses from best to worst as a numbered list
- Each line should be: number, period, space, then ONLY the response label (e.g., "1. Response A")
- Do not add any other text or explanations in the ranking section

Example format:
FINAL RANKING:
1. Response C
2. Response A
3. Response B

Now provide your evaluation and ranking:"""

    messages = [{"role": "user", "content": ranking_prompt}]

    # Stream rankings as each model completes
    async for model, response in query_models_streaming(models, messages):
        if response is not None:
            full_text = response.get('content', '')
            parsed = parse_ranking_from_text(full_text)
            result = {
                "model": model,
                "model_name": get_model_display_name(model),
                "ranking": full_text,
                "parsed_ranking": parsed
            }
            yield (result, label_to_model)


# =============================================================================
# STAGE 3: SYNTHESIS
# =============================================================================

async def stage3_synthesize_final(
    user_query: str,
    stage1_results: List[Dict[str, Any]],
    stage2_results: List[Dict[str, Any]],
    chairman_model: Optional[str] = None,
    council_type: str = "general"
) -> Dict[str, Any]:
    """
    Stage 3: Chairman synthesizes final response.

    Args:
        user_query: The original user query
        stage1_results: Individual model responses from Stage 1
        stage2_results: Rankings from Stage 2
        chairman_model: Model to use for synthesis
        council_type: Council type for context

    Returns:
        Dict with 'model', 'response' keys
    """
    chairman = chairman_model or DEFAULT_CHAIRMAN_MODEL

    # Build comprehensive context for chairman
    stage1_text = "\n\n".join([
        f"Model: {result.get('model_name', result['model'])}"
        + (f" ({result.get('role_name', '')})" if result.get('role_name') else "")
        + f"\nResponse: {result['response']}"
        for result in stage1_results
    ])

    stage2_text = "\n\n".join([
        f"Model: {result.get('model_name', result['model'])}\nRanking: {result['ranking']}"
        for result in stage2_results
    ])

    type_config = COUNCIL_TYPES.get(council_type, COUNCIL_TYPES["general"])

    chairman_prompt = f"""You are the Chairman of an LLM Council focused on {type_config['name']}.

Multiple AI models have provided responses to a user's question, and then ranked each other's responses.

Original Question: {user_query}

STAGE 1 - Individual Responses:
{stage1_text}

STAGE 2 - Peer Rankings:
{stage2_text}

Your task as Chairman is to synthesize all of this information into a single, comprehensive, accurate answer to the user's original question. Consider:
- The individual responses and their unique insights
- The peer rankings and what they reveal about response quality
- Any patterns of agreement or disagreement
- The specific perspectives each model brought (if they had assigned roles)

Provide a clear, well-reasoned final answer that represents the council's collective wisdom:"""

    messages = [{"role": "user", "content": chairman_prompt}]

    # Query the chairman model
    response = await query_model(chairman, messages)

    if response is None:
        return {
            "model": chairman,
            "model_name": get_model_display_name(chairman),
            "response": "Error: Unable to generate final synthesis."
        }

    return {
        "model": chairman,
        "model_name": get_model_display_name(chairman),
        "response": response.get('content', '')
    }


# =============================================================================
# DEBATE MODE
# =============================================================================

async def debate_round(
    user_query: str,
    previous_responses: List[Dict[str, Any]],
    round_number: int,
    models: Optional[List[str]] = None,
    council_type: str = "general",
    roles_enabled: bool = False,
    user_clarification: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Execute a single round of debate.

    In round 1, models respond independently.
    In round 2+, models see and respond to each other's previous responses.

    Args:
        user_query: The original question
        previous_responses: Responses from the previous round (empty for round 1)
        round_number: Current round number (1-indexed)
        models: List of model IDs
        council_type: Council type for prompts
        roles_enabled: Whether roles are enabled
        user_clarification: Optional user input to inject as additional context

    Returns:
        List of response dicts for this round
    """
    models = models or DEFAULT_COUNCIL_MODELS

    if round_number == 1:
        # First round: independent responses
        return await stage1_collect_responses(
            user_query, models, council_type, roles_enabled
        )

    # Build context from previous responses
    previous_text = "\n\n".join([
        f"[{result.get('model_name', result['model'])}"
        + (f" - {result.get('role_name', '')}" if result.get('role_name') else "")
        + f"]:\n{result['response']}"
        for result in previous_responses
    ])

    # Build user clarification section if provided
    clarification_section = ""
    if user_clarification:
        clarification_section = f"""
USER CLARIFICATION: The user has provided additional input during the debate:
"{user_clarification}"
Please take this clarification into account in your response.

"""

    debate_prompt = f"""This is round {round_number} of a council debate on the following question:

Original Question: {user_query}

Previous round's responses:
{previous_text}
{clarification_section}
Now it's your turn to respond. You should:
1. Acknowledge points from other council members that you agree with
2. Respectfully challenge or refine points you disagree with
3. Add any new insights or perspectives
4. Work toward building consensus while maintaining intellectual honesty
{f"5. Address the user's clarification: {user_clarification}" if user_clarification else ""}

Your response for round {round_number}:"""

    model_messages = {}
    model_roles = {}

    for model in models:
        role = get_role_for_model(model, roles_enabled)
        model_roles[model] = role
        system_prompt = build_system_prompt(council_type, role)

        model_messages[model] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": debate_prompt}
        ]

    responses = await query_models_parallel(models, model_messages)

    results = []
    for model, response in responses.items():
        if response is not None:
            role = model_roles.get(model)
            result = {
                "model": model,
                "model_name": get_model_display_name(model),
                "response": response.get('content', ''),
                "round": round_number
            }
            if role:
                result["role"] = role
                result["role_name"] = SPECIALIST_ROLES[role]["name"]
            results.append(result)

    return results


async def debate_summary(
    user_query: str,
    all_rounds: List[List[Dict[str, Any]]],
    chairman_model: Optional[str] = None,
    council_type: str = "general"
) -> Dict[str, Any]:
    """
    Generate a summary of a multi-round debate.

    Args:
        user_query: The original question
        all_rounds: List of rounds, each containing response dicts
        chairman_model: Model to use for summary
        council_type: Council type

    Returns:
        Summary dict with model and response
    """
    chairman = chairman_model or DEFAULT_CHAIRMAN_MODEL

    # Build the full debate transcript
    debate_text = ""
    for round_num, round_responses in enumerate(all_rounds, 1):
        debate_text += f"\n{'='*40}\nROUND {round_num}\n{'='*40}\n"
        for resp in round_responses:
            debate_text += f"\n[{resp.get('model_name', resp['model'])}"
            if resp.get('role_name'):
                debate_text += f" - {resp['role_name']}"
            debate_text += f"]:\n{resp['response']}\n"

    summary_prompt = f"""You are summarizing a council debate on the following question:

Original Question: {user_query}

DEBATE TRANSCRIPT:
{debate_text}

Please provide a comprehensive summary that includes:
1. The key points of consensus reached by the council
2. Any remaining areas of disagreement or nuance
3. The strongest arguments and insights that emerged
4. A final, actionable recommendation based on the collective discussion

Summary:"""

    messages = [{"role": "user", "content": summary_prompt}]
    response = await query_model(chairman, messages)

    if response is None:
        return {
            "model": chairman,
            "model_name": get_model_display_name(chairman),
            "response": "Error: Unable to generate debate summary."
        }

    return {
        "model": chairman,
        "model_name": get_model_display_name(chairman),
        "response": response.get('content', '')
    }


# =============================================================================
# SOCRATIC MODE
# =============================================================================

async def socratic_questions(
    user_query: str,
    models: Optional[List[str]] = None,
    council_type: str = "general",
    roles_enabled: bool = False
) -> List[Dict[str, Any]]:
    """
    Socratic mode: Council asks probing questions instead of giving answers.

    Args:
        user_query: The user's initial question/topic
        models: List of model IDs
        council_type: Council type
        roles_enabled: Whether roles are enabled

    Returns:
        List of response dicts containing questions
    """
    models = models or DEFAULT_COUNCIL_MODELS

    socratic_prompt = f"""The user has brought the following question or topic to the council:

{user_query}

Instead of answering directly, your role is to help the user think more deeply about this topic by asking 3-5 probing questions. These questions should:

1. Challenge assumptions the user might be making
2. Explore implications they may not have considered
3. Clarify what they really want to achieve
4. Uncover potential obstacles or trade-offs
5. Help them see the issue from different angles

Format your response as a numbered list of questions. After each question, briefly explain (in parentheses) why this question is important to consider.

Your probing questions:"""

    model_messages = {}
    model_roles = {}

    for model in models:
        role = get_role_for_model(model, roles_enabled)
        model_roles[model] = role
        system_prompt = build_system_prompt(council_type, role)

        model_messages[model] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": socratic_prompt}
        ]

    responses = await query_models_parallel(models, model_messages)

    results = []
    for model, response in responses.items():
        if response is not None:
            role = model_roles.get(model)
            result = {
                "model": model,
                "model_name": get_model_display_name(model),
                "response": response.get('content', ''),
                "mode": "socratic"
            }
            if role:
                result["role"] = role
                result["role_name"] = SPECIALIST_ROLES[role]["name"]
            results.append(result)

    return results


# =============================================================================
# SCENARIO PLANNING MODE
# =============================================================================

async def scenario_planning(
    user_query: str,
    models: Optional[List[str]] = None,
    chairman_model: Optional[str] = None,
    council_type: str = "general"
) -> Dict[str, Any]:
    """
    Scenario planning mode: Each model generates a scenario, then synthesis.

    Args:
        user_query: The user's question about future planning
        models: List of model IDs
        chairman_model: Model for synthesis
        council_type: Council type

    Returns:
        Dict with scenarios and synthesis
    """
    models = models or DEFAULT_COUNCIL_MODELS
    chairman = chairman_model or DEFAULT_CHAIRMAN_MODEL

    # Assign each model a scenario type
    scenario_types = ["best case", "worst case", "most likely", "wildcard/unexpected"]

    scenario_results = []

    for i, model in enumerate(models[:4]):  # Max 4 scenarios
        scenario_type = scenario_types[i] if i < len(scenario_types) else "alternative"

        scenario_prompt = f"""The user is considering the following question or decision:

{user_query}

Your task is to develop a detailed {scenario_type.upper()} scenario. Describe:

1. What this scenario looks like (be specific and vivid)
2. The key factors or events that would lead to this scenario
3. The probability you assign to this scenario (as a percentage)
4. Key indicators that would signal this scenario is unfolding
5. Recommended actions if this scenario materializes

Be concrete and actionable in your scenario planning.

Your {scenario_type} scenario:"""

        messages = [{"role": "user", "content": scenario_prompt}]
        response = await query_model(model, messages)

        if response:
            scenario_results.append({
                "model": model,
                "model_name": get_model_display_name(model),
                "scenario_type": scenario_type,
                "response": response.get('content', '')
            })

    # Synthesize scenarios
    scenarios_text = "\n\n".join([
        f"### {r['scenario_type'].upper()} SCENARIO (by {r['model_name']}):\n{r['response']}"
        for r in scenario_results
    ])

    synthesis_prompt = f"""The council has developed multiple scenarios for the following question:

{user_query}

SCENARIOS:
{scenarios_text}

As the Chairman, synthesize these scenarios into actionable guidance:
1. Compare the scenarios and their likelihood
2. Identify common factors across scenarios
3. Recommend a robust strategy that performs reasonably well across scenarios
4. Suggest specific trigger points for when to pivot strategies

Your synthesis:"""

    messages = [{"role": "user", "content": synthesis_prompt}]
    synthesis_response = await query_model(chairman, messages)

    return {
        "scenarios": scenario_results,
        "synthesis": {
            "model": chairman,
            "model_name": get_model_display_name(chairman),
            "response": synthesis_response.get('content', '') if synthesis_response else "Error generating synthesis"
        }
    }


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def parse_ranking_from_text(ranking_text: str) -> List[str]:
    """Parse the FINAL RANKING section from the model's response."""
    import re

    if "FINAL RANKING:" in ranking_text:
        parts = ranking_text.split("FINAL RANKING:")
        if len(parts) >= 2:
            ranking_section = parts[1]
            numbered_matches = re.findall(r'\d+\.\s*Response [A-Z]', ranking_section)
            if numbered_matches:
                return [re.search(r'Response [A-Z]', m).group() for m in numbered_matches]
            matches = re.findall(r'Response [A-Z]', ranking_section)
            return matches

    matches = re.findall(r'Response [A-Z]', ranking_text)
    return matches


def calculate_aggregate_rankings(
    stage2_results: List[Dict[str, Any]],
    label_to_model: Dict[str, str]
) -> List[Dict[str, Any]]:
    """Calculate aggregate rankings across all models."""
    from collections import defaultdict

    model_positions = defaultdict(list)

    for ranking in stage2_results:
        ranking_text = ranking['ranking']
        parsed_ranking = parse_ranking_from_text(ranking_text)

        for position, label in enumerate(parsed_ranking, start=1):
            if label in label_to_model:
                model_name = label_to_model[label]
                model_positions[model_name].append(position)

    aggregate = []
    for model, positions in model_positions.items():
        if positions:
            avg_rank = sum(positions) / len(positions)
            aggregate.append({
                "model": model,
                "model_name": get_model_display_name(model),
                "average_rank": round(avg_rank, 2),
                "rankings_count": len(positions)
            })

    aggregate.sort(key=lambda x: x['average_rank'])
    return aggregate


async def generate_conversation_title(user_query: str) -> str:
    """Generate a short title for a conversation."""
    title_prompt = f"""Generate a very short title (3-5 words maximum) that summarizes the following question.
The title should be concise and descriptive. Do not use quotes or punctuation in the title.

Question: {user_query}

Title:"""

    messages = [{"role": "user", "content": title_prompt}]
    response = await query_model("google/gemini-2.5-flash", messages, timeout=30.0)

    if response is None:
        return "New Conversation"

    title = response.get('content', 'New Conversation').strip()
    title = title.strip('"\'')

    if len(title) > 50:
        title = title[:47] + "..."

    return title


# =============================================================================
# MAIN ORCHESTRATION
# =============================================================================

async def run_full_council(
    user_query: str,
    models: Optional[List[str]] = None,
    chairman_model: Optional[str] = None,
    council_type: str = "general",
    roles_enabled: bool = False,
    enhancements: Optional[List[str]] = None
) -> Tuple[List, List, Dict, Dict]:
    """
    Run the complete 3-stage council process (synthesized mode).

    Args:
        user_query: The user's question
        models: List of model IDs (uses defaults if None)
        chairman_model: Model for synthesis (uses default if None)
        council_type: Council type for prompts
        roles_enabled: Whether to use specialist roles
        enhancements: List of enhancement keys

    Returns:
        Tuple of (stage1_results, stage2_results, stage3_result, metadata)
    """
    # Stage 1: Collect individual responses
    stage1_results = await stage1_collect_responses(
        user_query, models, council_type, roles_enabled, enhancements
    )

    if not stage1_results:
        return [], [], {
            "model": "error",
            "response": "All models failed to respond. Please try again."
        }, {}

    # Stage 2: Collect rankings
    stage2_results, label_to_model = await stage2_collect_rankings(
        user_query, stage1_results, models
    )

    # Calculate aggregate rankings
    aggregate_rankings = calculate_aggregate_rankings(stage2_results, label_to_model)

    # Stage 3: Synthesize final answer
    stage3_result = await stage3_synthesize_final(
        user_query, stage1_results, stage2_results, chairman_model, council_type
    )

    # Prepare metadata
    metadata = {
        "label_to_model": label_to_model,
        "aggregate_rankings": aggregate_rankings,
        "council_type": council_type,
        "roles_enabled": roles_enabled
    }

    return stage1_results, stage2_results, stage3_result, metadata
