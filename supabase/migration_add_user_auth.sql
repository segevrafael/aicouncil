-- Migration: Add user authentication with per-user data isolation
-- Run this in Supabase SQL Editor AFTER enabling Supabase Auth

-- =============================================================================
-- ADD USER_ID COLUMNS
-- =============================================================================

-- Add user_id to sessions
ALTER TABLE sessions ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE;

-- Add user_id to model_presets  
ALTER TABLE model_presets ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE;

-- Add user_id to predictions
ALTER TABLE predictions ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE;

-- Create indexes for user_id columns
CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_model_presets_user ON model_presets(user_id);
CREATE INDEX IF NOT EXISTS idx_predictions_user ON predictions(user_id);

-- =============================================================================
-- UPDATE RLS POLICIES FOR PER-USER ACCESS
-- =============================================================================

-- Drop old "allow all" policies
DROP POLICY IF EXISTS "Service role has full access to sessions" ON sessions;
DROP POLICY IF EXISTS "Service role has full access to messages" ON messages;
DROP POLICY IF EXISTS "Service role has full access to model_presets" ON model_presets;
DROP POLICY IF EXISTS "Service role has full access to predictions" ON predictions;
DROP POLICY IF EXISTS "Service role has full access to conversation_state" ON conversation_state;

-- Sessions: Users can only access their own sessions
CREATE POLICY "Users can view own sessions" ON sessions
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can create own sessions" ON sessions
    FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own sessions" ON sessions
    FOR UPDATE USING (auth.uid() = user_id);

CREATE POLICY "Users can delete own sessions" ON sessions
    FOR DELETE USING (auth.uid() = user_id);

-- Messages: Users can access messages in their sessions
CREATE POLICY "Users can view messages in own sessions" ON messages
    FOR SELECT USING (
        EXISTS (SELECT 1 FROM sessions WHERE sessions.id = messages.session_id AND sessions.user_id = auth.uid())
    );

CREATE POLICY "Users can create messages in own sessions" ON messages
    FOR INSERT WITH CHECK (
        EXISTS (SELECT 1 FROM sessions WHERE sessions.id = messages.session_id AND sessions.user_id = auth.uid())
    );

CREATE POLICY "Users can update messages in own sessions" ON messages
    FOR UPDATE USING (
        EXISTS (SELECT 1 FROM sessions WHERE sessions.id = messages.session_id AND sessions.user_id = auth.uid())
    );

CREATE POLICY "Users can delete messages in own sessions" ON messages
    FOR DELETE USING (
        EXISTS (SELECT 1 FROM sessions WHERE sessions.id = messages.session_id AND sessions.user_id = auth.uid())
    );

-- Model presets: Users see default presets + their own
CREATE POLICY "Users can view default and own presets" ON model_presets
    FOR SELECT USING (is_default = TRUE OR auth.uid() = user_id);

CREATE POLICY "Users can create own presets" ON model_presets
    FOR INSERT WITH CHECK (auth.uid() = user_id AND is_default = FALSE);

CREATE POLICY "Users can update own presets" ON model_presets
    FOR UPDATE USING (auth.uid() = user_id AND is_default = FALSE);

CREATE POLICY "Users can delete own presets" ON model_presets
    FOR DELETE USING (auth.uid() = user_id AND is_default = FALSE);

-- Predictions: Users can only access their own predictions
CREATE POLICY "Users can view own predictions" ON predictions
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can create own predictions" ON predictions
    FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own predictions" ON predictions
    FOR UPDATE USING (auth.uid() = user_id);

CREATE POLICY "Users can delete own predictions" ON predictions
    FOR DELETE USING (auth.uid() = user_id);

-- Conversation state: Users can access state for their sessions
CREATE POLICY "Users can view own conversation state" ON conversation_state
    FOR SELECT USING (
        EXISTS (SELECT 1 FROM sessions WHERE sessions.id = conversation_state.session_id AND sessions.user_id = auth.uid())
    );

CREATE POLICY "Users can create own conversation state" ON conversation_state
    FOR INSERT WITH CHECK (
        EXISTS (SELECT 1 FROM sessions WHERE sessions.id = conversation_state.session_id AND sessions.user_id = auth.uid())
    );

CREATE POLICY "Users can update own conversation state" ON conversation_state
    FOR UPDATE USING (
        EXISTS (SELECT 1 FROM sessions WHERE sessions.id = conversation_state.session_id AND sessions.user_id = auth.uid())
    );

CREATE POLICY "Users can delete own conversation state" ON conversation_state
    FOR DELETE USING (
        EXISTS (SELECT 1 FROM sessions WHERE sessions.id = conversation_state.session_id AND sessions.user_id = auth.uid())
    );

-- =============================================================================
-- SERVICE ROLE BYPASS (for backend operations)
-- =============================================================================
-- Note: The service_role key bypasses RLS by default in Supabase,
-- so the backend can still perform operations on behalf of users.
-- The backend will extract user_id from the JWT and include it in queries.

