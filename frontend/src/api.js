/**
 * API client for the LLM Council backend.
 * Supports authentication via Bearer token.
 */

// API base URL - can be overridden in production
const API_BASE = import.meta.env.VITE_API_URL || '';

// Store auth token in memory (can be enhanced with localStorage)
let authToken = null;

/**
 * Set the authentication token for API requests.
 * @param {string} token - The password/token for authentication
 */
export function setAuthToken(token) {
  authToken = token;
  // Persist to localStorage for convenience
  if (token) {
    localStorage.setItem('council_auth_token', token);
  } else {
    localStorage.removeItem('council_auth_token');
  }
}

/**
 * Get the current auth token (from memory or localStorage).
 */
export function getAuthToken() {
  if (!authToken) {
    authToken = localStorage.getItem('council_auth_token');
  }
  return authToken;
}

/**
 * Clear the auth token.
 */
export function clearAuthToken() {
  authToken = null;
  localStorage.removeItem('council_auth_token');
}

/**
 * Check if user is authenticated.
 */
export function isAuthenticated() {
  return !!getAuthToken();
}

/**
 * Get headers for authenticated requests.
 */
function getHeaders(includeContentType = true) {
  const headers = {};

  const token = getAuthToken();
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
    clearAuthToken();
    throw new Error('Authentication required. Please log in.');
  }
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(error.detail || `HTTP error ${response.status}`);
  }
  return response.json();
}

export const api = {
  // =============================================================================
  // AUTHENTICATION
  // =============================================================================

  /**
   * Verify the password by making a test request.
   * @param {string} password - The password to verify
   * @returns {Promise<boolean>} - True if password is valid
   */
  async verifyPassword(password) {
    const response = await fetch(`${API_BASE}/api/config`, {
      headers: {
        'Authorization': `Bearer ${password}`,
      },
    });
    return response.ok;
  },

  // =============================================================================
  // CONFIGURATION
  // =============================================================================

  /**
   * Get all configuration options (modes, types, roles, enhancements).
   */
  async getConfig() {
    const response = await fetch(`${API_BASE}/api/config`, {
      headers: getHeaders(false),
    });
    return handleResponse(response);
  },

  /**
   * Get available models from OpenRouter.
   */
  async getModels() {
    const response = await fetch(`${API_BASE}/api/models`, {
      headers: getHeaders(false),
    });
    return handleResponse(response);
  },

  /**
   * Force refresh the models cache.
   */
  async refreshModels() {
    const response = await fetch(`${API_BASE}/api/models/refresh`, {
      method: 'POST',
      headers: getHeaders(),
    });
    return handleResponse(response);
  },

  // =============================================================================
  // CONVERSATIONS
  // =============================================================================

  /**
   * List all conversations.
   */
  async listConversations() {
    const response = await fetch(`${API_BASE}/api/conversations`, {
      headers: getHeaders(false),
    });
    return handleResponse(response);
  },

  /**
   * Create a new conversation.
   */
  async createConversation(councilType = 'general', mode = 'synthesized') {
    const response = await fetch(`${API_BASE}/api/conversations`, {
      method: 'POST',
      headers: getHeaders(),
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
        headers: getHeaders(false),
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
        headers: getHeaders(false),
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
        headers: getHeaders(false),
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
        headers: getHeaders(),
        body: JSON.stringify({
          content,
          mode: options.mode || 'synthesized',
          council_type: options.councilType || 'general',
          models: options.models || null,
          chairman_model: options.chairmanModel || null,
          roles_enabled: options.rolesEnabled || false,
          enhancements: options.enhancements || [],
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
        headers: getHeaders(),
        body: JSON.stringify({
          content,
          mode: options.mode || 'synthesized',
          council_type: options.councilType || 'general',
          models: options.models || null,
          chairman_model: options.chairmanModel || null,
          roles_enabled: options.rolesEnabled || false,
          enhancements: options.enhancements || [],
        }),
      }
    );

    if (response.status === 401) {
      clearAuthToken();
      throw new Error('Authentication required. Please log in.');
    }

    if (!response.ok) {
      throw new Error('Failed to send message');
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      const chunk = decoder.decode(value);
      const lines = chunk.split('\n');

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const data = line.slice(6);
          try {
            const event = JSON.parse(data);
            onEvent(event.type, event);
          } catch (e) {
            console.error('Failed to parse SSE event:', e);
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
        headers: getHeaders(),
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
        headers: getHeaders(),
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
      headers: getHeaders(false),
    });
    return handleResponse(response);
  },

  /**
   * Create a new model preset.
   */
  async createPreset(name, models, chairmanModel = null, description = null) {
    const response = await fetch(`${API_BASE}/api/presets`, {
      method: 'POST',
      headers: getHeaders(),
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
      headers: getHeaders(false),
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
        headers: getHeaders(false),
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
      headers: getHeaders(),
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
        headers: getHeaders(),
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
      headers: getHeaders(false),
    });
    return handleResponse(response);
  },
};
