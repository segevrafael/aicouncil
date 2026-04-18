import { useState, useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { markdownComponents } from '../markdownConfig.jsx';
import Stage1 from './Stage1';
import Stage2 from './Stage2';
import Stage3 from './Stage3';
import './ChatInterface.css';

export default function ChatInterface({
  conversation,
  onSendMessage,
  isLoading,
  queueLength = 0,
  selectedMode,
  conversationState,
}) {
  // Hide main input when Socratic mode is active (uses dedicated input in DebateControls)
  const hideChatInput = conversationState?.has_active_session && conversationState?.mode === 'socratic';
  const [input, setInput] = useState('');
  const [attachedFiles, setAttachedFiles] = useState([]);
  const [uploading, setUploading] = useState(false);
  const fileInputRef = useRef(null);
  const messagesEndRef = useRef(null);

  // Check if any message has stage-specific loading (to avoid duplicate spinners)
  const hasStageLoading = conversation?.messages?.some(msg =>
    msg.loading && Object.values(msg.loading).some(Boolean)
  );

  // Show default spinner only when loading AND no stage-specific spinners are active
  const showDefaultSpinner = isLoading && !hasStageLoading;

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [conversation]);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (input.trim() || attachedFiles.length > 0) {
      onSendMessage(input, attachedFiles.length > 0 ? attachedFiles : undefined);
      setInput('');
      setAttachedFiles([]);
    }
  };

  const handleFileSelect = (e) => {
    const files = Array.from(e.target.files || []);
    for (const file of files) {
      const preview = file.type.startsWith('image/') ? URL.createObjectURL(file) : null;
      setAttachedFiles(prev => [...prev, { file, preview, name: file.name }]);
    }
    // Reset input so selecting the same file again works
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const removeFile = (index) => {
    setAttachedFiles(prev => {
      const updated = [...prev];
      if (updated[index].preview) URL.revokeObjectURL(updated[index].preview);
      updated.splice(index, 1);
      return updated;
    });
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
                      <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>{msg.content}</ReactMarkdown>
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

                  {/* Stage 1 / Debate Round - now shows inline loading with skeleton tabs */}
                  {(msg.stage1 || msg.loading?.stage1) && (
                    <Stage1
                      responses={msg.stage1}
                      title={msg.debateRound ? `Debate Round ${msg.debateRound}` : undefined}
                      expectedModels={msg.expectedModels}
                      isLoading={msg.loading?.stage1}
                    />
                  )}

                  {/* Stage 2 - now shows inline loading with skeleton tabs */}
                  {(msg.stage2 || msg.loading?.stage2) && (
                    <Stage2
                      rankings={msg.stage2}
                      labelToModel={msg.metadata?.label_to_model}
                      aggregateRankings={msg.metadata?.aggregate_rankings}
                      expectedModels={msg.expectedModels}
                      isLoading={msg.loading?.stage2}
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
                          <ReactMarkdown components={markdownComponents}>{msg.critique.response}</ReactMarkdown>
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Socratic Mode: Council Questions - shows inline with skeleton tabs */}
                  {(msg.questions || msg.loading?.questions) && (
                    <Stage1
                      responses={msg.questions}
                      title="Council Questions"
                      expectedModels={msg.expectedModels}
                      isLoading={msg.loading?.questions}
                    />
                  )}

                  {/* Scenario Mode: Scenarios - shows inline with skeleton tabs */}
                  {(msg.scenarios || msg.loading?.scenarios) && (
                    <Stage1
                      responses={msg.scenarios}
                      title="Scenario Analysis"
                      expectedModels={msg.expectedModels?.slice(0, 4)}
                      isLoading={msg.loading?.scenarios}
                    />
                  )}
                </div>
              )}
            </div>
          ))
        )}

        {showDefaultSpinner && (
          <div className="loading-indicator">
            <div className="spinner"></div>
            <span>Consulting the council...</span>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {!hideChatInput && (
        <form className="input-form" onSubmit={handleSubmit} autoComplete="off">
          {attachedFiles.length > 0 && (
            <div className="attached-files">
              {attachedFiles.map((af, i) => (
                <div key={i} className="attached-file">
                  {af.preview ? (
                    <img src={af.preview} alt={af.name} className="attached-file-thumb" />
                  ) : (
                    <span className="attached-file-icon">
                      {af.name.match(/\.pdf$/i) ? 'PDF' : af.name.match(/\.docx?$/i) ? 'DOC' : af.name.match(/\.xlsx?$/i) ? 'XLS' : 'FILE'}
                    </span>
                  )}
                  <span className="attached-file-name">{af.name}</span>
                  <button type="button" className="attached-file-remove" onClick={() => removeFile(i)}>x</button>
                </div>
              ))}
            </div>
          )}
          <div className="input-row">
            <button
              type="button"
              className="attach-button"
              onClick={() => fileInputRef.current?.click()}
              disabled={uploading}
              title="Attach file"
            >
              +
            </button>
            <input
              ref={fileInputRef}
              type="file"
              multiple
              accept="image/*,.pdf,.docx,.xlsx,.txt,.md,.csv,.json,.xml,.html,.py,.js,.ts,.jsx,.tsx,.css,.sql,.sh,.yaml,.yml"
              onChange={handleFileSelect}
              style={{ display: 'none' }}
            />
            <textarea
              className="message-input"
              placeholder={isLoading ? "Type your next question — it will be sent when the current response completes..." : "Ask your question... (Shift+Enter for new line, Enter to send)"}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              rows={3}
              autoComplete="off"
              data-form-type="other"
            />
            <button
              type="submit"
              className="send-button"
              disabled={!input.trim() && attachedFiles.length === 0}
            >
              {isLoading ? `Queue${queueLength > 0 ? ` (${queueLength})` : ''}` : 'Send'}
            </button>
          </div>
        </form>
      )}
    </div>
  );
}
