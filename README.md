# LLM Council

> **Fork Notice:** This project is an extended fork of [karpathy/llm-council](https://github.com/karpathy/llm-council), the original "vibe coded" weekend project by Andrej Karpathy. This version adds multiple council modes, cloud deployment, streaming, authentication, and other features.

![llmcouncil](header.jpg)

A multi-LLM deliberation system where AI models collaborate, debate, and peer-review each other's responses to provide more thoughtful answers than any single model alone.

## What is LLM Council?

Instead of asking a question to a single AI, LLM Council sends your query to multiple leading models simultaneously. The models then review and rank each other's work (anonymously, to prevent favoritism), and a "Chairman" model synthesizes everything into a final response.

This approach provides:
- **Multiple perspectives** on complex questions
- **Peer review** to catch errors and blind spots
- **Transparency** into how different models think
- **Higher quality** synthesis from collective intelligence

## Council Modes

LLM Council supports several deliberation modes:

| Mode | Description |
|------|-------------|
| **Synthesized** | Full 3-stage process: responses → peer review → chairman synthesis |
| **Independent** | See all model responses side-by-side without synthesis |
| **Debate** | Multi-round discussion where models respond to each other's arguments |
| **Adversarial** | Three models answer while a Devil's Advocate challenges everything |
| **Socratic** | The council asks YOU probing questions to clarify your thinking |
| **Scenario Planning** | Models generate best/worst/likely scenarios and debate probabilities |

## The Three Stages

For the synthesized mode, here's what happens when you submit a query:

1. **Stage 1: Individual Responses** — Your query goes to all council models independently. Each response is shown in tabs so you can inspect them.

2. **Stage 2: Peer Review** — Each model reviews and ranks the others' responses. Identities are anonymized (Response A, B, C...) so models can't play favorites.

3. **Stage 3: Final Synthesis** — The Chairman model compiles all responses and rankings into a unified final answer.

## Council Types

Customize the council's expertise with domain-specific configurations:

- **General Purpose** — Balanced advice for any topic
- **Business Strategy** — Market analysis, competitive strategy, growth decisions
- **Code Review** — Architecture, bugs, performance, security analysis
- **Creative Writing** — Narrative, style, character development
- **Personal Productivity** — Habits, systems, work-life balance
- **Research Analysis** — Evidence evaluation, methodology, synthesis

## Specialist Roles

Enable specialist roles to have each model take a different perspective:

- **The Optimist** — Focuses on opportunities and upside potential
- **The Skeptic** — Identifies risks and plays devil's advocate
- **The Pragmatist** — Considers real-world constraints and feasibility
- **The Innovator** — Suggests unconventional, creative solutions

## Tech Stack

- **Backend:** FastAPI (Python 3.10+), async httpx, OpenRouter API
- **Frontend:** React + Vite, react-markdown for rendering
- **Database:** Supabase (PostgreSQL)
- **Deployment:** Vercel (serverless)
- **LLM Access:** OpenRouter (supports 100+ models)

> **Note on Streaming:** The app supports real-time streaming where model responses appear as they complete (hot loading with skeleton tabs). This works when running locally, but Vercel's Python runtime buffers responses, so production shows all results at once. For true streaming in production, deploy the backend to Railway, Render, or Fly.io.

## Quick Start

### Prerequisites

- Python 3.10+
- Node.js 18+
- [OpenRouter](https://openrouter.ai) API key
- [Supabase](https://supabase.com) account (for persistence)

### 1. Clone and Install

```bash
git clone https://github.com/alexclowe/aicouncil.git
cd aicouncil

# Backend dependencies
pip install -r requirements.txt

# Frontend dependencies
cd frontend && npm install && cd ..
```

### 2. Configure Environment

Create a `.env` file in the project root:

```bash
# Required: OpenRouter API key
OPENROUTER_API_KEY=sk-or-v1-your-key-here

# Required: Supabase configuration
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key

# Required for production: API password
COUNCIL_API_PASSWORD=your-secure-password

# Optional: CORS origins (comma-separated)
CORS_ORIGINS=http://localhost:5173,https://your-app.vercel.app
```

### 3. Set Up Database

Run the schema in your Supabase SQL Editor:

```bash
# The schema is in supabase/schema.sql
```

### 4. Run Locally

**Option A: Use the start script**
```bash
./start.sh
```

**Option B: Run manually**

Terminal 1 (Backend):
```bash
python -m backend.main
```

Terminal 2 (Frontend):
```bash
cd frontend && npm run dev
```

Open http://localhost:5173 in your browser.

## Deployment

See [DEPLOYMENT.md](DEPLOYMENT.md) for detailed instructions on deploying to Vercel with Supabase.

## Configuration

### Models

Edit `backend/config.py` to customize the council:

```python
DEFAULT_COUNCIL_MODELS = [
    "openai/gpt-5.2",
    "anthropic/claude-opus-4.5",
    "google/gemini-3-pro-preview",
    "x-ai/grok-4",
]

DEFAULT_CHAIRMAN_MODEL = "anthropic/claude-opus-4.5"
```

You can use any model available on [OpenRouter](https://openrouter.ai/models).

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│     Frontend    │────▶│     FastAPI     │────▶│   OpenRouter    │
│   (React/Vite)  │     │    (Backend)    │     │   (LLM APIs)    │
└─────────────────┘     └────────┬────────┘     └─────────────────┘
                                 │
                                 ▼
                        ┌─────────────────┐
                        │    Supabase     │
                        │   (PostgreSQL)  │
                        └─────────────────┘
```

## Credits

This project is forked from [karpathy/llm-council](https://github.com/karpathy/llm-council) by **Andrej Karpathy**, who created the original concept and implementation as a weekend "vibe coding" project. The original was inspired by [reading books together with LLMs](https://x.com/karpathy/status/1990577951671509438) — seeing multiple AI perspectives side-by-side while exploring complex topics.

**This fork adds:**
- Multiple council modes (Debate, Adversarial, Socratic, Scenario Planning)
- Domain-specific council types and specialist roles
- Supabase database for persistence
- Vercel serverless deployment
- Streaming responses with real-time UI updates
- Password authentication
- Conversation archiving
- Mid-session message injection

## License

MIT License - see [LICENSE](LICENSE) for details.
