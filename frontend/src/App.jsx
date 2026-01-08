import { useState, useEffect } from 'react';
import Sidebar from './components/Sidebar';
import ChatInterface from './components/ChatInterface';
import ModeSelector from './components/ModeSelector';
import DebateControls from './components/DebateControls';
import Login from './components/Login';
import { api, isAuthenticated, clearAuthToken } from './api';
import './App.css';

function App() {
  // Auth state
  const [authenticated, setAuthenticated] = useState(isAuthenticated());

  // Conversations state
  const [conversations, setConversations] = useState([]);
  const [currentConversationId, setCurrentConversationId] = useState(null);
  const [currentConversation, setCurrentConversation] = useState(null);
  const [conversationState, setConversationState] = useState(null);
  const [isLoading, setIsLoading] = useState(false);

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

  const handleLogin = () => {
    setAuthenticated(true);
  };

  const handleLogout = () => {
    clearAuthToken();
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

  const loadConversations = async () => {
    try {
      const convs = await api.listConversations();
      setConversations(convs);
    } catch (error) {
      console.error('Failed to load conversations:', error);
    }
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
              stage1: msg.stage_data.stage1 || msg.stage_data.responses || null,
              stage2: msg.stage_data.stage2 || null,
              stage3: msg.stage_data.stage3 || msg.stage_data.summary || null,
              mode: msg.stage_data.mode || null,
              metadata: msg.stage_data.metadata || null,
              debateRound: msg.stage_data.round || msg.debate_round || null,
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
    } catch (error) {
      console.error('Failed to create conversation:', error);
    }
  };

  const handleSelectConversation = (id) => {
    setCurrentConversationId(id);
  };

  const handleSendMessage = async (content) => {
    if (!currentConversationId) return;

    setIsLoading(true);
    try {
      // Optimistically add user message to UI
      const userMessage = { role: 'user', content };
      setCurrentConversation((prev) => ({
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
      setCurrentConversation((prev) => {
        console.log('Adding assistant message, current messages:', prev.messages.length);
        return {
          ...prev,
          messages: [...prev.messages, assistantMessage],
        };
      });

      console.log('Starting SSE stream with mode:', selectedMode);
      // Send message with streaming and options
      const options = {
        mode: selectedMode,
        councilType: selectedCouncilType,
        rolesEnabled,
        enhancements: selectedEnhancements,
      };

      await api.sendMessageStream(currentConversationId, content, (eventType, event) => {
        console.log('SSE Event:', eventType, event);
        switch (eventType) {
          case 'mode':
            // Mode info received
            break;

          case 'stage1_start':
            setCurrentConversation((prev) => {
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
            setCurrentConversation((prev) => {
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
            setCurrentConversation((prev) => {
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
            setCurrentConversation((prev) => {
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
            setCurrentConversation((prev) => {
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
            setCurrentConversation((prev) => {
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
            setCurrentConversation((prev) => {
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
            setCurrentConversation((prev) => {
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

          case 'title_complete':
            // Reload conversations to get updated title
            loadConversations();
            break;

          case 'complete':
            // Stream complete, reload conversations list and state
            loadConversations();
            loadConversationState(currentConversationId);
            setIsLoading(false);
            break;

          case 'error':
            console.error('Stream error:', event.message);
            setIsLoading(false);
            break;

          default:
            console.log('Unknown event type:', eventType);
        }
      }, options);
    } catch (error) {
      console.error('Failed to send message:', error);
      // Remove optimistic messages on error
      setCurrentConversation((prev) => ({
        ...prev,
        messages: prev.messages.slice(0, -2),
      }));
      setIsLoading(false);
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

  // Check if we should show the mode selector (only before first message)
  const showModeSelector = currentConversation && currentConversation.messages.length === 0;

  // Show login screen if not authenticated
  if (!authenticated) {
    return <Login onLogin={handleLogin} />;
  }

  return (
    <div className="app">
      <Sidebar
        conversations={conversations}
        currentConversationId={currentConversationId}
        onSelectConversation={handleSelectConversation}
        onNewConversation={handleNewConversation}
        onLogout={handleLogout}
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
    </div>
  );
}

export default App;
