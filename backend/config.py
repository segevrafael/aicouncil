"""Configuration for the LLM Council."""

import os
from dotenv import load_dotenv

load_dotenv()

# OpenRouter API key
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# OpenRouter API endpoints
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"

# Legacy paths (no longer used - Supabase is primary storage)
DATA_DIR = "data/conversations"
DATABASE_PATH = "data/council.db"

# =============================================================================
# DEFAULT MODELS (user can override via UI)
# =============================================================================

DEFAULT_COUNCIL_MODELS = [
    "openai/gpt-5.2",
    "anthropic/claude-opus-4.5",
    "google/gemini-3-pro-preview",
    "x-ai/grok-4",
]

DEFAULT_CHAIRMAN_MODEL = "anthropic/claude-opus-4.5"


# =============================================================================
# COUNCIL MODES
# =============================================================================

COUNCIL_MODES = {
    "independent": {
        "name": "Independent",
        "description": "All models respond separately, see all perspectives side-by-side",
        "multi_round": False,
        "has_synthesis": False,
    },
    "synthesized": {
        "name": "Synthesized",
        "description": "Responses, peer review, then chairman synthesis",
        "multi_round": False,
        "has_synthesis": True,
    },
    "debate": {
        "name": "Debate",
        "description": "Multi-round discussion where models respond to each other",
        "multi_round": True,
        "has_synthesis": True,
    },
    "adversarial": {
        "name": "Adversarial",
        "description": "3 models answer, 1 Devil's Advocate challenges everything",
        "multi_round": True,
        "has_synthesis": True,
    },
    "socratic": {
        "name": "Socratic",
        "description": "Council asks YOU probing questions instead of giving answers",
        "multi_round": True,
        "has_synthesis": False,
    },
    "scenario": {
        "name": "Scenario Planning",
        "description": "Models generate best/worst/likely scenarios and debate probabilities",
        "multi_round": False,
        "has_synthesis": True,
    },
}

# =============================================================================
# SPECIALIST ROLES
# =============================================================================

SPECIALIST_ROLES = {
    "optimist": {
        "name": "The Optimist",
        "prompt": "Focus on opportunities, upside potential, and what could go right. "
                  "Highlight the best-case scenarios and reasons for hope. "
                  "Find the silver lining and paths to success.",
    },
    "skeptic": {
        "name": "The Skeptic",
        "prompt": "Identify risks, potential failures, and what could go wrong. "
                  "Play devil's advocate and stress-test assumptions. "
                  "Point out blind spots and hidden dangers.",
    },
    "pragmatist": {
        "name": "The Pragmatist",
        "prompt": "Focus on what's actually feasible given real-world constraints. "
                  "Consider resources, timelines, and practical limitations. "
                  "Suggest actionable, realistic next steps.",
    },
    "innovator": {
        "name": "The Innovator",
        "prompt": "Suggest unconventional approaches and outside-the-box solutions. "
                  "Challenge conventional wisdom and explore creative alternatives. "
                  "Think about what others might be missing.",
    },
}

# Default role assignments for each model (when roles are enabled)
DEFAULT_ROLE_ASSIGNMENTS = {
    "openai/gpt-5.2": "optimist",
    "anthropic/claude-opus-4.5": "pragmatist",
    "google/gemini-3-pro-preview": "skeptic",
    "x-ai/grok-4": "innovator",
}

# =============================================================================
# COUNCIL TYPES (Domain-specific configurations)
# =============================================================================

COUNCIL_TYPES = {
    "general": {
        "name": "General Purpose",
        "description": "Balanced advice for any topic",
        "icon": "message-circle",
        "color": "#6366f1",
        "system_prompt": "You are a helpful AI assistant participating in a council of AI models. "
                         "Provide thoughtful, well-reasoned responses.",
        "temperature": 0.7,
    },
    "business_strategy": {
        "name": "Business Strategy",
        "description": "Market analysis, competitive strategy, growth decisions",
        "icon": "briefcase",
        "color": "#2563eb",
        "system_prompt": "You are a strategic business consultant with expertise in market analysis, "
                         "competitive strategy, and organizational growth. Provide actionable business "
                         "advice backed by sound reasoning. Consider market dynamics, competitive "
                         "positioning, resource allocation, and risk management.",
        "temperature": 0.7,
    },
    "code_review": {
        "name": "Code Review",
        "description": "Architecture, bugs, performance, security analysis",
        "icon": "code",
        "color": "#10b981",
        "system_prompt": "You are a senior software engineer and architect. Review code and technical "
                         "decisions for correctness, performance, security, and maintainability. "
                         "Provide specific, actionable feedback with code examples when helpful. "
                         "Consider edge cases, error handling, and long-term implications.",
        "temperature": 0.3,
    },
    "creative_writing": {
        "name": "Creative Writing",
        "description": "Narrative, style, character development, theme",
        "icon": "pen-tool",
        "color": "#8b5cf6",
        "system_prompt": "You are a literary expert and creative writing mentor. Provide feedback on "
                         "narrative structure, character development, prose style, dialogue, pacing, "
                         "and thematic depth. Balance craft critique with encouragement. "
                         "Honor the writer's unique voice while suggesting improvements.",
        "temperature": 0.9,
    },
    "personal_productivity": {
        "name": "Personal Productivity",
        "description": "Habits, systems, work-life balance, time management",
        "icon": "target",
        "color": "#f59e0b",
        "system_prompt": "You are a productivity coach and life optimization expert. Provide practical "
                         "advice on habits, systems, time management, and work-life balance. "
                         "Consider psychological factors, sustainable practices, and individual "
                         "circumstances. Focus on actionable improvements.",
        "temperature": 0.6,
    },
    "research_analysis": {
        "name": "Research Analysis",
        "description": "Evidence evaluation, methodology, literature synthesis",
        "icon": "search",
        "color": "#06b6d4",
        "system_prompt": "You are a research analyst with expertise in evidence evaluation and "
                         "critical thinking. Assess claims based on evidence quality, methodology, "
                         "and logical reasoning. Acknowledge uncertainty and limitations. "
                         "Synthesize information from multiple perspectives.",
        "temperature": 0.4,
    },
}

# =============================================================================
# OUTPUT ENHANCEMENTS
# =============================================================================

ENHANCEMENTS = {
    "decision_matrix": {
        "name": "Decision Matrix",
        "description": "Generate a structured pros/cons table",
        "prompt_addition": "\n\nAfter your main response, provide a structured decision matrix "
                          "with clear pros, cons, and considerations in a table format.",
    },
    "confidence": {
        "name": "Confidence Score",
        "description": "Rate confidence level 1-10",
        "prompt_addition": "\n\nAt the end of your response, rate your confidence in this advice "
                          "on a scale of 1-10 and briefly explain your confidence level.",
    },
    "followup_questions": {
        "name": "Follow-up Questions",
        "description": "Identify what info would help give better advice",
        "prompt_addition": "\n\nEnd your response with 2-3 clarifying questions that would help "
                          "you provide even better advice if answered.",
    },
}
