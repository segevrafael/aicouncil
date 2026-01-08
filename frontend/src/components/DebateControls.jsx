import { useState } from 'react';
import './DebateControls.css';

export default function DebateControls({
  conversationState,
  onContinue,
  onEnd,
  isLoading,
}) {
  const [socraticInput, setSocraticInput] = useState('');

  if (!conversationState?.has_active_session) {
    return null;
  }

  const { mode, current_round, total_rounds } = conversationState;

  const handleContinue = () => {
    if (mode === 'socratic') {
      onContinue(socraticInput);
      setSocraticInput('');
    } else {
      onContinue();
    }
  };

  return (
    <div className="debate-controls">
      <div className="debate-info">
        <span className="debate-mode">{mode.charAt(0).toUpperCase() + mode.slice(1)} Mode</span>
        {mode === 'debate' && (
          <span className="round-counter">Round {current_round} of {total_rounds}</span>
        )}
      </div>

      {mode === 'socratic' && (
        <div className="socratic-input">
          <textarea
            placeholder="Enter your answers to the council's questions..."
            value={socraticInput}
            onChange={(e) => setSocraticInput(e.target.value)}
            disabled={isLoading}
            rows={3}
          />
        </div>
      )}

      <div className="debate-actions">
        <button
          className="continue-button"
          onClick={handleContinue}
          disabled={isLoading || (mode === 'socratic' && !socraticInput.trim())}
        >
          {isLoading ? (
            <>
              <span className="spinner small"></span>
              Processing...
            </>
          ) : mode === 'debate' ? (
            'Continue Debate'
          ) : mode === 'socratic' ? (
            'Submit Answers'
          ) : (
            'Continue'
          )}
        </button>

        <button
          className="end-button"
          onClick={onEnd}
          disabled={isLoading}
        >
          {mode === 'debate' ? 'End & Summarize' : 'End Session'}
        </button>
      </div>

      <p className="controls-hint">
        {mode === 'debate' && 'Continue for another round of discussion, or end to get a summary.'}
        {mode === 'socratic' && 'Answer the questions above to receive tailored advice.'}
      </p>
    </div>
  );
}
