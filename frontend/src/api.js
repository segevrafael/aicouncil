/**
 * API client for the LLM Council backend.
 * Supports authentication via Supabase JWT tokens.
 */

import { supabase, getSessionToken } from './supabase';

// API base URL - can be overridden in production
const API_BASE = import.meta.env.VITE_API_URL || '';

// Cache the current session
let currentSession = null;

/**
 * Set the current session (called after login).
 * @param {Object} session - Supabase session object
 */
export function setSession(session) {
  currentSession = session;
}

/**
 * Clear the current session.
 */
export function clearSession() {
  currentSession = null;
}

/**
 * Check if user is authenticated.
 */
export function isAuthenticated() {
  return !!currentSession;
}

/**
 * Sign out the current user.
 */
export async function signOut() {
  await supabase.auth.signOut();
  currentSession = null;
}

/**
 * Get headers for authenticated requests.
 */
async function getHeaders(includeContentType = true) {
  const headers = {};

  // Get fresh token from Supabase (handles token refresh automatically)
  const token = await getSessionToken();
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  if (includeContentType) {
    headers['Content-Type'] = 'application/json';
  }

  return headers;
}

/**
 * Handle API response, including auth errors.
 */
async function handleResponse(response) {
  if (response.status === 401) {
    clearSession();
    throw new Error('Session expired. Please log in again.');
  }
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(error.detail || `HTTP error ${response.status}`);
  }
  return response.json();
}

export const api = {
  // =============================================================================
  // CONFIGURATION
  // =============================================================================

  /**
   * Get all configuration options (modes, types, roles, enhancements).
   */
  async getConfig() {
    const response = await fetch(`${API_BASE}/api/config`, {
      headers: await getHeaders(false),
    });
    return handleResponse(response);
  },

  /**
   * Get available models from OpenRouter.
   */
  async getModels() {
    const response = await fetch(`${API_BASE}/api/models`, {
      headers: await getHeaders(false),
    });
    return handleResponse(response);
  },

  /**
   * Force refresh the models cache.
   */
  async refreshModels() {
    const response = await fetch(`${API_BASE}/api/models/refresh`, {
      method: 'POST',
      headers: await getHeaders(),
    });
    return handleResponse(response);
  },

  // =============================================================================
  // CONVERSATIONS
  // =============================================================================

  /**
   * List all conversations.
   * @param {boolean} includeArchived - Include archived conversations (default: false)
   */
  async listConversations(includeArchived = false) {
    const params = includeArchived ? '?include_archived=true' : '';
    const response = await fetch(`${API_BASE}/api/conversations${params}`, {
      headers: await getHeaders(false),
    });
    return handleResponse(response);
  },

  /**
   * Create a new conversation.
   */
  async createConversation(councilType = 'general', mode = 'synthesized') {
    const response = await fetch(`${API_BASE}/api/conversations`, {
      method: 'POST',
      headers: await getHeaders(),
      body: JSON.stringify({ council_type: councilType, mode }),
    });
    return handleResponse(response);
  },

  /**
   * Get a specific conversation.
   */
  async getConversation(conversationId) {
    const response = await fetch(
      `${API_BASE}/api/conversations/${conversationId}`,
      {
        headers: await getHeaders(false),
      }
    );
    return handleResponse(response);
  },

  /**
   * Delete a conversation.
   */
  async deleteConversation(conversationId) {
    const response = await fetch(
      `${API_BASE}/api/conversations/${conversationId}`,
      {
        method: 'DELETE',
        headers: await getHeaders(false),
      }
    );
    return handleResponse(response);
  },

  /**
   * Archive or unarchive a conversation.
   * @param {string} conversationId - The conversation ID
   * @param {boolean} isArchived - True to archive, false to unarchive
   */
  async archiveConversation(conversationId, isArchived) {
    const response = await fetch(
      `${API_BASE}/api/conversations/${conversationId}/archive`,
      {
        method: 'PATCH',
        headers: await getHeaders(),
        body: JSON.stringify({ is_archived: isArchived }),
      }
    );
    return handleResponse(response);
  },

  /**
   * Get the state of a multi-round conversation.
   */
  async getConversationState(conversationId) {
    const response = await fetch(
      `${API_BASE}/api/conversations/${conversationId}/state`,
      {
        headers: await getHeaders(false),
      }
    );
    return handleResponse(response);
  },

  // =============================================================================
  // FILE UPLOADS
  // =============================================================================

  /**
   * Upload a file attachment for a conversation.
   * @param {string} conversationId - The conversation ID
   * @param {File} file - The file to upload
   * @returns {Promise<object>} Upload result with storage_path, category, etc.
   */
  async uploadFile(conversationId, file) {
    const formData = new FormData();
    formData.append('file', file);

    const headers = await getHeaders(false); // No Content-Type — browser sets multipart boundary
    const response = await fetch(
      `${API_BASE}/api/conversations/${conversationId}/upload`,
      {
        method: 'POST',
        headers,
        body: formData,
      }
    );
    return handleResponse(response);
  },

  // =============================================================================
  // MESSAGES
  // =============================================================================

  /**
   * Send a message in a conversation.
   * @param {string} conversationId - The conversation ID
   * @param {string} content - The message content
   * @param {object} options - Optional parameters
   * @param {string} options.mode - Council mode (independent|synthesized|debate|adversarial|socratic|scenario)
   * @param {string} options.councilType - Council type for domain-specific prompts
   * @param {string[]} options.models - Override default models (list of 4 model IDs)
   * @param {string} options.chairmanModel - Override chairman model for synthesis
   * @param {boolean} options.rolesEnabled - Enable specialist roles
   * @param {string[]} options.enhancements - Output enhancements
   */
  async sendMessage(conversationId, content, options = {}) {
    const response = await fetch(
      `${API_BASE}/api/conversations/${conversationId}/message`,
      {
        method: 'POST',
        headers: await getHeaders(),
        body: JSON.stringify({
          content,
          mode: options.mode || 'synthesized',
          council_type: options.councilType || 'general',
          models: options.models || null,
          chairman_model: options.chairmanModel || null,
          roles_enabled: options.rolesEnabled || false,
          enhancements: options.enhancements || [],
          web_search: options.webSearch || false,
          attachments: options.attachments || [],
        }),
      }
    );
    return handleResponse(response);
  },

  /**
   * Send a message and receive streaming updates.
   * @param {string} conversationId - The conversation ID
   * @param {string} content - The message content
   * @param {function} onEvent - Callback function for each event: (eventType, data) => void
   * @param {object} options - Optional parameters (same as sendMessage)
   * @returns {Promise<void>}
   */
  async sendMessageStream(conversationId, content, onEvent, options = {}) {
    const response = await fetch(
      `${API_BASE}/api/conversations/${conversationId}/message/stream`,
      {
        method: 'POST',
        headers: await getHeaders(),
        body: JSON.stringify({
          content,
          mode: options.mode || 'synthesized',
          council_type: options.councilType || 'general',
          models: options.models || null,
          chairman_model: options.chairmanModel || null,
          roles_enabled: options.rolesEnabled || false,
          enhancements: options.enhancements || [],
          web_search: options.webSearch || false,
          attachments: options.attachments || [],
        }),
      }
    );

    if (response.status === 401) {
      clearSession();
      throw new Error('Session expired. Please log in again.');
    }

    if (!response.ok) {
      throw new Error('Failed to send message');
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) {
        break;
      }

      // Append new data to buffer
      buffer += decoder.decode(value, { stream: true });

      // Process complete SSE messages (separated by double newlines)
      const messages = buffer.split('\n\n');

      // Keep the last incomplete message in the buffer
      buffer = messages.pop() || '';

      for (const message of messages) {
        const lines = message.split('\n');
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = line.slice(6);
            try {
              const event = JSON.parse(data);
              onEvent(event.type, event);
            } catch (e) {
              console.error('Failed to parse SSE event:', e, 'Raw data:', data.substring(0, 200) + '...');
            }
          }
        }
      }
    }

    // Process any remaining data in buffer
    if (buffer.trim()) {
      const lines = buffer.split('\n');
      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const data = line.slice(6);
          try {
            const event = JSON.parse(data);
            onEvent(event.type, event);
          } catch (e) {
            console.error('Failed to parse final SSE event:', e);
          }
        }
      }
    }
  },

  // =============================================================================
  // MULTI-ROUND MODES (DEBATE, SOCRATIC)
  // =============================================================================

  /**
   * Continue a multi-round conversation.
   * @param {string} conversationId - The conversation ID
   * @param {string} userInput - Optional user input (required for socratic mode)
   */
  async continueConversation(conversationId, userInput = null) {
    const response = await fetch(
      `${API_BASE}/api/conversations/${conversationId}/continue`,
      {
        method: 'POST',
        headers: await getHeaders(),
        body: JSON.stringify({ user_input: userInput }),
      }
    );
    return handleResponse(response);
  },

  /**
   * End a multi-round conversation and get summary.
   * @param {string} conversationId - The conversation ID
   */
  async endConversation(conversationId) {
    const response = await fetch(
      `${API_BASE}/api/conversations/${conversationId}/end`,
      {
        method: 'POST',
        headers: await getHeaders(),
      }
    );
    return handleResponse(response);
  },

  // =============================================================================
  // MODEL PRESETS
  // =============================================================================

  /**
   * List all model presets.
   */
  async listPresets() {
    const response = await fetch(`${API_BASE}/api/presets`, {
      headers: await getHeaders(false),
    });
    return handleResponse(response);
  },

  /**
   * Create a new model preset.
   */
  async createPreset(name, models, chairmanModel = null, description = null) {
    const response = await fetch(`${API_BASE}/api/presets`, {
      method: 'POST',
      headers: await getHeaders(),
      body: JSON.stringify({
        name,
        models,
        chairman_model: chairmanModel,
        description,
      }),
    });
    return handleResponse(response);
  },

  /**
   * Delete a model preset.
   */
  async deletePreset(presetId) {
    const response = await fetch(`${API_BASE}/api/presets/${presetId}`, {
      method: 'DELETE',
      headers: await getHeaders(false),
    });
    return handleResponse(response);
  },

  // =============================================================================
  // SEARCH
  // =============================================================================

  /**
   * Search across all conversations.
   */
  async search(query, limit = 20) {
    const response = await fetch(
      `${API_BASE}/api/search?q=${encodeURIComponent(query)}&limit=${limit}`,
      {
        headers: await getHeaders(false),
      }
    );
    return handleResponse(response);
  },

  // =============================================================================
  // PREDICTIONS
  // =============================================================================

  /**
   * Log a prediction for accuracy tracking.
   */
  async createPrediction(sessionId, predictionText, modelName = null, category = null) {
    const response = await fetch(`${API_BASE}/api/predictions`, {
      method: 'POST',
      headers: await getHeaders(),
      body: JSON.stringify({
        session_id: sessionId,
        prediction_text: predictionText,
        model_name: modelName,
        category,
      }),
    });
    return handleResponse(response);
  },

  /**
   * Record the outcome of a prediction.
   */
  async recordOutcome(predictionId, outcome, accuracyScore = null, notes = null) {
    const response = await fetch(
      `${API_BASE}/api/predictions/${predictionId}/outcome`,
      {
        method: 'PUT',
        headers: await getHeaders(),
        body: JSON.stringify({
          outcome,
          accuracy_score: accuracyScore,
          notes,
        }),
      }
    );
    return handleResponse(response);
  },

  /**
   * Get prediction accuracy statistics.
   */
  async getPredictionStats() {
    const response = await fetch(`${API_BASE}/api/predictions/stats`, {
      headers: await getHeaders(false),
    });
    return handleResponse(response);
  },
};
