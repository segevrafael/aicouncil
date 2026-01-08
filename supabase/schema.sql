-- Supabase schema for LLM Council
-- Run this in the Supabase SQL Editor to set up your database

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Sessions table (conversations)
CREATE TABLE IF NOT EXISTS sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title TEXT DEFAULT 'New Conversation',
    council_type TEXT DEFAULT 'general',
    council_mode TEXT DEFAULT 'synthesized',
    models JSONB,  -- JSON array of model IDs
    chairman_model TEXT,
    roles_enabled BOOLEAN DEFAULT FALSE,
    enhancements JSONB,  -- JSON array
    tags JSONB,  -- JSON array
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Messages table
CREATE TABLE IF NOT EXISTS messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    role TEXT NOT NULL,  -- user, assistant, system
    content TEXT,
    model_name TEXT,
    specialist_role TEXT,
    confidence_score REAL,
    debate_round INTEGER,
    stage_data JSONB,  -- JSON for stage1/stage2/stage3 data
    metadata JSONB,  -- JSON for additional metadata
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Model presets table
CREATE TABLE IF NOT EXISTS model_presets (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    models JSONB NOT NULL,  -- JSON array of model IDs
    chairman_model TEXT,
    is_default BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Predictions table for tracking advice accuracy
CREATE TABLE IF NOT EXISTS predictions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    message_id UUID REFERENCES messages(id) ON DELETE SET NULL,
    prediction_text TEXT NOT NULL,
    model_name TEXT,
    category TEXT,  -- business, personal, technical, etc.
    outcome TEXT,  -- NULL until recorded
    outcome_notes TEXT,
    accuracy_score REAL,  -- 0-1 scale
    predicted_at TIMESTAMPTZ DEFAULT NOW(),
    outcome_recorded_at TIMESTAMPTZ
);

-- Conversation state for multi-round modes (debate, socratic)
CREATE TABLE IF NOT EXISTS conversation_state (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE UNIQUE,
    mode TEXT NOT NULL,
    query TEXT NOT NULL,
    rounds JSONB,  -- Array of round responses
    current_round INTEGER DEFAULT 1,
    models JSONB,
    chairman_model TEXT,
    council_type TEXT,
    roles_enabled BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id);
CREATE INDEX IF NOT EXISTS idx_messages_created ON messages(created_at);
CREATE INDEX IF NOT EXISTS idx_sessions_created ON sessions(created_at);
CREATE INDEX IF NOT EXISTS idx_sessions_updated ON sessions(updated_at);
CREATE INDEX IF NOT EXISTS idx_predictions_session ON predictions(session_id);
CREATE INDEX IF NOT EXISTS idx_conversation_state_session ON conversation_state(session_id);

-- Full-text search index on messages
CREATE INDEX IF NOT EXISTS idx_messages_content_search ON messages USING GIN (to_tsvector('english', COALESCE(content, '')));

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Triggers for updated_at
DROP TRIGGER IF EXISTS update_sessions_updated_at ON sessions;
CREATE TRIGGER update_sessions_updated_at
    BEFORE UPDATE ON sessions
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_conversation_state_updated_at ON conversation_state;
CREATE TRIGGER update_conversation_state_updated_at
    BEFORE UPDATE ON conversation_state
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Insert default model preset
INSERT INTO model_presets (name, description, models, chairman_model, is_default)
VALUES (
    'Frontier Models',
    'Latest frontier models from major providers',
    '["openai/gpt-5.2", "anthropic/claude-opus-4.5", "google/gemini-3-pro-preview", "x-ai/grok-4"]',
    'anthropic/claude-opus-4.5',
    TRUE
) ON CONFLICT (name) DO NOTHING;

-- Row Level Security (RLS) - Enable for all tables
ALTER TABLE sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE model_presets ENABLE ROW LEVEL SECURITY;
ALTER TABLE predictions ENABLE ROW LEVEL SECURITY;
ALTER TABLE conversation_state ENABLE ROW LEVEL SECURITY;

-- RLS Policies - Allow all operations for authenticated service role
-- These policies allow the backend (using service_role key) full access
CREATE POLICY "Service role has full access to sessions" ON sessions
    FOR ALL USING (true) WITH CHECK (true);

CREATE POLICY "Service role has full access to messages" ON messages
    FOR ALL USING (true) WITH CHECK (true);

CREATE POLICY "Service role has full access to model_presets" ON model_presets
    FOR ALL USING (true) WITH CHECK (true);

CREATE POLICY "Service role has full access to predictions" ON predictions
    FOR ALL USING (true) WITH CHECK (true);

CREATE POLICY "Service role has full access to conversation_state" ON conversation_state
    FOR ALL USING (true) WITH CHECK (true);
