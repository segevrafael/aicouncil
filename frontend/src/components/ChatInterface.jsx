import { useState, useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import Stage1 from './Stage1';
import Stage2 from './Stage2';
import Stage3 from './Stage3';
import './ChatInterface.css';

export default function ChatInterface({
  conversation,
  onSendMessage,
  isLoading,
  selectedMode,
  conversationState,
}) {
  // Hide main input when Socratic mode is active (uses dedicated input in DebateControls)
  const hideChatInput = conversationState?.has_active_session && conversationState?.mode === 'socratic';
  const [input, setInput] = useState('');
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [conversation]);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (input.trim() && !isLoading) {
      onSendMessage(input);
      setInput('');
    }
  };

  const handleKeyDown = (e) => {
    // Submit on Enter (without Shift)
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  if (!conversation) {
    return (
      <div className="chat-interface">
        <div className="empty-state">
          <h2>Welcome to LLM Council</h2>
          <p>Create a new conversation to get started</p>
        </div>
      </div>
    );
  }

  return (
    <div className="chat-interface">
      <div className="messages-container">
        {conversation.messages.length === 0 ? (
          <div className="empty-state">
            <h2>Start a conversation</h2>
            <p>Ask a question to consult the LLM Council</p>
          </div>
        ) : (
          conversation.messages.map((msg, index) => (
            <div key={index} className="message-group">
              {msg.role === 'user' ? (
                <div className="user-message">
                  <div className="message-label">You</div>
                  <div className="message-content">
                    <div className="markdown-content">
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.content}</ReactMarkdown>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="assistant-message">
                  <div className="message-label">
                    LLM Council
                    {msg.debateRound && (
                      <span className="debate-round-badge">Round {msg.debateRound}</span>
                    )}
                  </div>

                  {/* Stage 1 / Debate Round */}
                  {msg.loading?.stage1 && (
                    <div className="stage-loading">
                      <div className="spinner"></div>
                      <span>
                        {msg.debateRound
                          ? `Running Debate Round ${msg.debateRound}...`
                          : 'Running Stage 1: Collecting individual responses...'}
                      </span>
                    </div>
                  )}
                  {msg.stage1 && (
                    <Stage1
                      responses={msg.stage1}
                      title={msg.debateRound ? `Debate Round ${msg.debateRound}` : undefined}
                    />
                  )}

                  {/* Stage 2 */}
                  {msg.loading?.stage2 && (
                    <div className="stage-loading">
                      <div className="spinner"></div>
                      <span>Running Stage 2: Peer rankings...</span>
                    </div>
                  )}
                  {msg.stage2 && (
                    <Stage2
                      rankings={msg.stage2}
                      labelToModel={msg.metadata?.label_to_model}
                      aggregateRankings={msg.metadata?.aggregate_rankings}
                    />
                  )}

                  {/* Stage 3 / Debate Summary */}
                  {msg.loading?.stage3 && (
                    <div className="stage-loading">
                      <div className="spinner"></div>
                      <span>Running Stage 3: Final synthesis...</span>
                    </div>
                  )}
                  {msg.stage3 && <Stage3 finalResponse={msg.stage3} />}

                  {/* Adversarial Mode: Devil's Advocate Critique */}
                  {msg.loading?.critique && (
                    <div className="stage-loading">
                      <div className="spinner"></div>
                      <span>Devil's Advocate is preparing critique...</span>
                    </div>
                  )}
                  {msg.critique && (
                    <div className="stage critique-section">
                      <h3 className="stage-title">Devil's Advocate</h3>
                      <div className="critique-content">
                        <div className="model-name">{msg.critique.model_name || msg.critique.model}</div>
                        <div className="response-text markdown-content">
                          <ReactMarkdown>{msg.critique.response}</ReactMarkdown>
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Socratic Mode: Council Questions */}
                  {msg.loading?.questions && (
                    <div className="stage-loading">
                      <div className="spinner"></div>
                      <span>Council is formulating questions...</span>
                    </div>
                  )}
                  {msg.questions && (
                    <Stage1
                      responses={msg.questions}
                      title="Council Questions"
                    />
                  )}

                  {/* Scenario Mode: Scenarios */}
                  {msg.loading?.scenarios && (
                    <div className="stage-loading">
                      <div className="spinner"></div>
                      <span>Generating scenarios...</span>
                    </div>
                  )}
                  {msg.scenarios && (
                    <Stage1
                      responses={msg.scenarios}
                      title="Scenario Analysis"
                    />
                  )}
                </div>
              )}
            </div>
          ))
        )}

        {isLoading && (
          <div className="loading-indicator">
            <div className="spinner"></div>
            <span>Consulting the council...</span>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {!hideChatInput && (
        <form className="input-form" onSubmit={handleSubmit} autoComplete="off">
          <textarea
            className="message-input"
            placeholder="Ask your question... (Shift+Enter for new line, Enter to send)"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={isLoading}
            rows={3}
            autoComplete="off"
            data-form-type="other"
          />
          <button
            type="submit"
            className="send-button"
            disabled={!input.trim() || isLoading}
          >
            Send
          </button>
        </form>
      )}
    </div>
  );
}
