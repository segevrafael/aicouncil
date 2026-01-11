import { useState, useEffect } from 'react';
import Sidebar from './components/Sidebar';
import ChatInterface from './components/ChatInterface';
import ModeSelector from './components/ModeSelector';
import DebateControls from './components/DebateControls';
import ConfirmDialog from './components/ConfirmDialog';
import Login from './components/Login';
import { api, setSession, clearSession, signOut } from './api';
import { supabase, onAuthStateChange } from './supabase';
import './App.css';

function App() {
  // Auth state
  const [authenticated, setAuthenticated] = useState(false);
  const [authLoading, setAuthLoading] = useState(true);

  // Check for existing session on mount and subscribe to auth changes
  useEffect(() => {
    // Check for existing session
    supabase.auth.getSession().then(({ data: { session } }) => {
      if (session) {
        setSession(session);
        setAuthenticated(true);
      }
      setAuthLoading(false);
    });

    // Subscribe to auth state changes (login, logout, token refresh)
    const unsubscribe = onAuthStateChange((event, session) => {
      if (event === 'SIGNED_IN' && session) {
        setSession(session);
        setAuthenticated(true);
      } else if (event === 'SIGNED_OUT') {
        clearSession();
        setAuthenticated(false);
      } else if (event === 'TOKEN_REFRESHED' && session) {
        setSession(session);
      }
    });

    return unsubscribe;
  }, []);

  // Conversations state
  const [conversations, setConversations] = useState([]);
  const [currentConversationId, setCurrentConversationId] = useState(null);
  const [currentConversation, setCurrentConversation] = useState(null);
  const [conversationState, setConversationState] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [showArchived, setShowArchived] = useState(false);

  // Track which conversations are loading (for background processing indicator)
  const [loadingConversations, setLoadingConversations] = useState(new Set());

  // Confirmation dialog state for mid-session messages
  const [pendingMessage, setPendingMessage] = useState(null);
  const [showConfirmDialog, setShowConfirmDialog] = useState(false);

  // Config state
  const [config, setConfig] = useState(null);

  // Council settings state
  const [selectedMode, setSelectedMode] = useState('synthesized');
  const [selectedCouncilType, setSelectedCouncilType] = useState('general');
  const [rolesEnabled, setRolesEnabled] = useState(false);
  const [selectedEnhancements, setSelectedEnhancements] = useState([]);

  // Load config and conversations on auth
  useEffect(() => {
    if (authenticated) {
      loadConfig();
      loadConversations();
    }
  }, [authenticated]);

  const handleLogin = (session) => {
    setSession(session);
    setAuthenticated(true);
  };

  const handleLogout = async () => {
    await signOut();
    setAuthenticated(false);
    setConversations([]);
    setCurrentConversationId(null);
    setCurrentConversation(null);
    setConfig(null);
  };

  // Load conversation details when selected
  useEffect(() => {
    if (currentConversationId) {
      loadConversation(currentConversationId);
      loadConversationState(currentConversationId);
    } else {
      setCurrentConversation(null);
      setConversationState(null);
    }
  }, [currentConversationId]);

  const loadConfig = async () => {
    try {
      const cfg = await api.getConfig();
      setConfig(cfg);
      // Set defaults from config
      if (cfg.defaults) {
        setSelectedMode(cfg.defaults.mode || 'synthesized');
        setSelectedCouncilType(cfg.defaults.council_type || 'general');
      }
    } catch (error) {
      console.error('Failed to load config:', error);
    }
  };

  const loadConversations = async (includeArchived = true) => {
    try {
      // Always load all conversations (including archived) so we can show the archived count
      const convs = await api.listConversations(includeArchived);
      setConversations(convs);
    } catch (error) {
      console.error('Failed to load conversations:', error);
    }
  };

  const handleArchiveConversation = async (conversationId, isArchived) => {
    try {
      await api.archiveConversation(conversationId, isArchived);
      // Refresh conversations list
      await loadConversations();
      // If we just archived the current conversation, clear the selection
      if (isArchived && conversationId === currentConversationId) {
        setCurrentConversationId(null);
      }
    } catch (error) {
      console.error('Failed to archive conversation:', error);
    }
  };

  const handleToggleShowArchived = () => {
    setShowArchived(!showArchived);
  };

  const loadConversation = async (id) => {
    try {
      const conv = await api.getConversation(id);

      // Transform messages to extract stage_data into expected format
      if (conv.messages) {
        conv.messages = conv.messages.map(msg => {
          if (msg.role === 'assistant' && msg.stage_data) {
            // Extract stages from stage_data to top level for rendering
            return {
              ...msg,
              // Standard stages
              stage1: msg.stage_data.stage1 || msg.stage_data.responses || msg.stage_data.initial_responses || null,
              stage2: msg.stage_data.stage2 || null,
              stage3: msg.stage_data.stage3 || msg.stage_data.summary || msg.stage_data.synthesis || null,
              mode: msg.stage_data.mode || null,
              metadata: msg.stage_data.metadata || null,
              // Debate mode
              debateRound: msg.stage_data.round || msg.debate_round || null,
              // Adversarial mode
              critique: msg.stage_data.devils_advocate || null,
              // Socratic mode
              questions: msg.stage_data.questions || null,
              // Scenario mode
              scenarios: msg.stage_data.scenarios || null,
            };
          }
          return msg;
        });
      }

      setCurrentConversation(conv);
    } catch (error) {
      console.error('Failed to load conversation:', error);
    }
  };

  const loadConversationState = async (id) => {
    try {
      const state = await api.getConversationState(id);
      setConversationState(state);
    } catch (error) {
      console.error('Failed to load conversation state:', error);
      setConversationState(null);
    }
  };

  const handleNewConversation = async () => {
    try {
      const newConv = await api.createConversation(selectedCouncilType, selectedMode);
      setConversations([
        { id: newConv.id, created_at: newConv.created_at, message_count: 0, title: 'New Conversation' },
        ...conversations,
      ]);
      setCurrentConversationId(newConv.id);
      // New conversation isn't loading anything - clear loading state from previous conversation
      setIsLoading(false);
    } catch (error) {
      console.error('Failed to create conversation:', error);
    }
  };

  const handleSelectConversation = async (id) => {
    // Update isLoading based on whether this conversation is loading in the background
    setIsLoading(loadingConversations.has(id));

    // If switching to a different conversation, explicitly reload it
    // (handles case where background processing completed)
    if (id !== currentConversationId) {
      setCurrentConversationId(id);
      // Force reload the conversation to get latest messages
      await loadConversation(id);
      await loadConversationState(id);
    }
  };

  const handleSendMessage = async (content) => {
    if (!currentConversationId) return;

    // Check if there's an active multi-round session (debate or socratic)
    if (conversationState?.has_active_session) {
      // Store the pending message and show confirmation dialog
      setPendingMessage(content);
      setShowConfirmDialog(true);
      return;
    }

    // No active session, proceed normally
    await sendMessageDirectly(content);
  };

  const sendMessageDirectly = async (content) => {
    // Capture conversation ID at start (for background processing support)
    const targetConvId = currentConversationId;

    setIsLoading(true);
    // Track this conversation as loading (for sidebar indicator)
    setLoadingConversations(prev => new Set(prev).add(targetConvId));

    // Helper to safely update conversation only if it's still current
    const updateConversation = (updateFn) => {
      setCurrentConversation((prev) => {
        // Only update if still viewing the target conversation
        if (prev?.id !== targetConvId) return prev;
        return updateFn(prev);
      });
    };

    try {
      // Optimistically add user message to UI
      const userMessage = { role: 'user', content };
      updateConversation((prev) => ({
        ...prev,
        messages: [...prev.messages, userMessage],
      }));

      // Create a partial assistant message that will be updated progressively
      const assistantMessage = {
        role: 'assistant',
        mode: selectedMode,
        stage1: null,
        stage2: null,
        stage3: null,
        metadata: null,
        loading: {
          stage1: false,
          stage2: false,
          stage3: false,
        },
      };

      // Add the partial assistant message
      updateConversation((prev) => ({
        ...prev,
        messages: [...prev.messages, assistantMessage],
      }));

      // Send message with streaming and options
      const options = {
        mode: selectedMode,
        councilType: selectedCouncilType,
        rolesEnabled,
        enhancements: selectedEnhancements,
      };

      await api.sendMessageStream(targetConvId, content, (eventType, event) => {
        switch (eventType) {
          case 'mode':
            // Mode info received
            break;

          case 'stage1_start':
            updateConversation((prev) => {
              const messages = [...prev.messages];
              const lastIndex = messages.length - 1;
              messages[lastIndex] = {
                ...messages[lastIndex],
                loading: { ...messages[lastIndex].loading, stage1: true },
              };
              return { ...prev, messages };
            });
            break;

          case 'stage1_complete':
            updateConversation((prev) => {
              const messages = [...prev.messages];
              const lastIndex = messages.length - 1;
              messages[lastIndex] = {
                ...messages[lastIndex],
                stage1: event.data,
                loading: { ...messages[lastIndex].loading, stage1: false },
              };
              return { ...prev, messages };
            });
            break;

          case 'stage2_start':
            updateConversation((prev) => {
              const messages = [...prev.messages];
              const lastIndex = messages.length - 1;
              messages[lastIndex] = {
                ...messages[lastIndex],
                loading: { ...messages[lastIndex].loading, stage2: true },
              };
              return { ...prev, messages };
            });
            break;

          case 'stage2_complete':
            updateConversation((prev) => {
              const messages = [...prev.messages];
              const lastIndex = messages.length - 1;
              messages[lastIndex] = {
                ...messages[lastIndex],
                stage2: event.data,
                metadata: event.metadata,
                loading: { ...messages[lastIndex].loading, stage2: false },
              };
              return { ...prev, messages };
            });
            break;

          case 'stage3_start':
            updateConversation((prev) => {
              const messages = [...prev.messages];
              const lastIndex = messages.length - 1;
              messages[lastIndex] = {
                ...messages[lastIndex],
                loading: { ...messages[lastIndex].loading, stage3: true },
              };
              return { ...prev, messages };
            });
            break;

          case 'stage3_complete':
            updateConversation((prev) => {
              const messages = [...prev.messages];
              const lastIndex = messages.length - 1;
              messages[lastIndex] = {
                ...messages[lastIndex],
                stage3: event.data,
                loading: { ...messages[lastIndex].loading, stage3: false },
              };
              return { ...prev, messages };
            });
            break;

          // Debate mode handlers
          case 'debate_round_start':
            updateConversation((prev) => {
              const messages = [...prev.messages];
              const lastIndex = messages.length - 1;
              messages[lastIndex] = {
                ...messages[lastIndex],
                debateRound: event.round,
                loading: { ...messages[lastIndex].loading, stage1: true },
              };
              return { ...prev, messages };
            });
            break;

          case 'debate_round_complete':
            updateConversation((prev) => {
              const messages = [...prev.messages];
              const lastIndex = messages.length - 1;
              messages[lastIndex] = {
                ...messages[lastIndex],
                debateRound: event.round,
                stage1: event.data, // Debate responses render the same as stage1
                loading: { ...messages[lastIndex].loading, stage1: false },
              };
              return { ...prev, messages };
            });
            break;

          case 'debate_can_continue':
            // Conversation state will be loaded on 'complete' event
            break;

          // Adversarial mode handlers
          case 'critique_start':
            updateConversation((prev) => {
              const messages = [...prev.messages];
              const lastIndex = messages.length - 1;
              messages[lastIndex] = {
                ...messages[lastIndex],
                loading: { ...messages[lastIndex].loading, critique: true },
              };
              return { ...prev, messages };
            });
            break;

          case 'critique_complete':
            updateConversation((prev) => {
              const messages = [...prev.messages];
              const lastIndex = messages.length - 1;
              messages[lastIndex] = {
                ...messages[lastIndex],
                critique: event.data,
                loading: { ...messages[lastIndex].loading, critique: false },
              };
              return { ...prev, messages };
            });
            break;

          // Socratic mode handlers
          case 'questions_start':
            updateConversation((prev) => {
              const messages = [...prev.messages];
              const lastIndex = messages.length - 1;
              messages[lastIndex] = {
                ...messages[lastIndex],
                loading: { ...messages[lastIndex].loading, questions: true },
              };
              return { ...prev, messages };
            });
            break;

          case 'questions_complete':
            updateConversation((prev) => {
              const messages = [...prev.messages];
              const lastIndex = messages.length - 1;
              messages[lastIndex] = {
                ...messages[lastIndex],
                questions: event.data,
                loading: { ...messages[lastIndex].loading, questions: false },
              };
              return { ...prev, messages };
            });
            break;

          // Scenario mode handlers
          case 'scenarios_start':
            updateConversation((prev) => {
              const messages = [...prev.messages];
              const lastIndex = messages.length - 1;
              messages[lastIndex] = {
                ...messages[lastIndex],
                loading: { ...messages[lastIndex].loading, scenarios: true },
              };
              return { ...prev, messages };
            });
            break;

          case 'scenarios_complete':
            updateConversation((prev) => {
              const messages = [...prev.messages];
              const lastIndex = messages.length - 1;
              messages[lastIndex] = {
                ...messages[lastIndex],
                scenarios: event.data,
                loading: { ...messages[lastIndex].loading, scenarios: false },
              };
              return { ...prev, messages };
            });
            break;

          case 'title_complete':
            // Reload conversations to get updated title
            loadConversations();
            break;

          case 'complete':
            // Stream complete, reload conversations list and state
            loadConversations();
            loadConversationState(targetConvId);
            // Remove from loading set
            setLoadingConversations(prev => {
              const next = new Set(prev);
              next.delete(targetConvId);
              return next;
            });
            // Only clear isLoading if this was the current conversation
            if (targetConvId === currentConversationId) {
              setIsLoading(false);
            }
            break;

          case 'error':
            console.error('Stream error:', event.message);
            // Remove from loading set
            setLoadingConversations(prev => {
              const next = new Set(prev);
              next.delete(targetConvId);
              return next;
            });
            if (targetConvId === currentConversationId) {
              setIsLoading(false);
            }
            break;

          default:
            // Unknown event type - ignore
        }
      }, options);
    } catch (error) {
      console.error('Failed to send message:', error);
      // Remove optimistic messages on error (only if still viewing this conversation)
      updateConversation((prev) => ({
        ...prev,
        messages: prev.messages.slice(0, -2),
      }));
      // Remove from loading set
      setLoadingConversations(prev => {
        const next = new Set(prev);
        next.delete(targetConvId);
        return next;
      });
      if (targetConvId === currentConversationId) {
        setIsLoading(false);
      }
    }
  };

  const handleContinueDebate = async (userInput = null) => {
    if (!currentConversationId) return;

    setIsLoading(true);
    try {
      const result = await api.continueConversation(currentConversationId, userInput);

      // Add the new round to the conversation
      setCurrentConversation((prev) => ({
        ...prev,
        messages: [
          ...prev.messages,
          {
            role: 'assistant',
            mode: result.mode,
            stage1: result.responses || result.stage1,
            stage2: result.stage2,
            stage3: result.stage3 || result.summary,
            metadata: result.metadata,
          },
        ],
      }));

      // Refresh conversation state
      await loadConversationState(currentConversationId);
    } catch (error) {
      console.error('Failed to continue debate:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleEndDebate = async () => {
    if (!currentConversationId) return;

    setIsLoading(true);
    try {
      const result = await api.endConversation(currentConversationId);

      // Add the summary if available
      if (result.summary) {
        setCurrentConversation((prev) => ({
          ...prev,
          messages: [
            ...prev.messages,
            {
              role: 'assistant',
              mode: 'debate_summary',
              stage3: result.summary,
            },
          ],
        }));
      }

      // Clear conversation state
      setConversationState(null);
    } catch (error) {
      console.error('Failed to end debate:', error);
    } finally {
      setIsLoading(false);
    }
  };

  // Handle confirmation dialog selection
  const handleConfirmDialogSelect = async (choice) => {
    setShowConfirmDialog(false);

    if (!pendingMessage) return;

    if (choice === 'add_to_session') {
      // Add the user's message to the conversation so they can see what they typed
      const userMessage = { role: 'user', content: pendingMessage, isDebateClarification: true };
      setCurrentConversation((prev) => ({
        ...prev,
        messages: [...prev.messages, userMessage],
      }));
      // Continue the debate/socratic session with the user's input as context
      await handleContinueDebate(pendingMessage);
    } else if (choice === 'start_new') {
      // End current session silently and start fresh
      try {
        await api.endConversation(currentConversationId);
        setConversationState(null);
      } catch (error) {
        console.error('Failed to end session:', error);
      }
      // Now send the new message
      await sendMessageDirectly(pendingMessage);
    }

    setPendingMessage(null);
  };

  const handleConfirmDialogCancel = () => {
    setShowConfirmDialog(false);
    setPendingMessage(null);
  };

  // Check if we should show the mode selector (only before first message)
  const showModeSelector = currentConversation && currentConversation.messages.length === 0;

  // Show loading while checking auth state
  if (authLoading) {
    return (
      <div className="auth-loading">
        <div className="auth-loading-spinner" />
      </div>
    );
  }

  // Show login screen if not authenticated
  if (!authenticated) {
    return <Login onLogin={handleLogin} />;
  }

  return (
    <div className="app">
      <Sidebar
        conversations={conversations}
        currentConversationId={currentConversationId}
        loadingConversations={loadingConversations}
        onSelectConversation={handleSelectConversation}
        onNewConversation={handleNewConversation}
        onArchiveConversation={handleArchiveConversation}
        onLogout={handleLogout}
        showArchived={showArchived}
        onToggleShowArchived={handleToggleShowArchived}
      />
      <main className="main-content">
        {showModeSelector && config && (
          <ModeSelector
            modes={config.modes}
            councilTypes={config.council_types}
            roles={config.roles}
            enhancements={config.enhancements}
            selectedMode={selectedMode}
            selectedCouncilType={selectedCouncilType}
            rolesEnabled={rolesEnabled}
            selectedEnhancements={selectedEnhancements}
            onModeChange={setSelectedMode}
            onCouncilTypeChange={setSelectedCouncilType}
            onRolesToggle={setRolesEnabled}
            onEnhancementsChange={setSelectedEnhancements}
            disabled={isLoading}
          />
        )}

        <ChatInterface
          conversation={currentConversation}
          onSendMessage={handleSendMessage}
          isLoading={isLoading}
          selectedMode={selectedMode}
          conversationState={conversationState}
        />

        {conversationState?.has_active_session && (
          <DebateControls
            conversationState={conversationState}
            onContinue={handleContinueDebate}
            onEnd={handleEndDebate}
            isLoading={isLoading}
          />
        )}
      </main>

      <ConfirmDialog
        isOpen={showConfirmDialog}
        title={`Active ${conversationState?.mode === 'debate' ? 'Debate' : 'Session'} in Progress`}
        message={`You have an active ${conversationState?.mode || 'multi-round'} session (Round ${conversationState?.current_round || 1}). What would you like to do with your message?`}
        options={[
          {
            label: `Add to ${conversationState?.mode === 'debate' ? 'Debate' : 'Session'}`,
            value: 'add_to_session',
            variant: 'primary',
          },
          {
            label: 'Start New Conversation',
            value: 'start_new',
            variant: 'warning',
          },
        ]}
        onSelect={handleConfirmDialogSelect}
        onCancel={handleConfirmDialogCancel}
      />
    </div>
  );
}

export default App;
