import { useState, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import './Stage1.css';

export default function Stage1({ responses, title, expectedModels, isLoading }) {
  const [activeTab, setActiveTab] = useState(0);

  // Get list of models that have responded (including failed ones)
  const completedModels = responses?.map(r => r.model) || [];

  // Get list of failed models
  const failedModels = responses?.filter(r => r.error)?.map(r => r.model) || [];

  // Build the full tab list: completed + pending
  // Use expectedModels if it has items, otherwise fall back to completedModels
  const allModels = (expectedModels && expectedModels.length > 0) ? expectedModels : completedModels;
  const totalExpected = allModels.length;
  const completedCount = completedModels.length;
  const successCount = completedCount - failedModels.length;

  // Auto-select the first completed tab when streaming
  useEffect(() => {
    if (responses?.length === 1 && activeTab !== 0) {
      setActiveTab(0);
    }
  }, [responses?.length]);

  // Don't render if no responses and not loading
  if ((!responses || responses.length === 0) && !isLoading) {
    return null;
  }

  // Get response for a model (if completed)
  const getResponse = (model) => responses?.find(r => r.model === model);

  // Check if a model has completed (includes failed)
  const isCompleted = (model) => completedModels.includes(model);

  // Check if a model has failed
  const isFailed = (model) => failedModels.includes(model);

  return (
    <div className="stage stage1">
      <h3 className="stage-title">
        {title || 'Stage 1: Individual Responses'}
        {isLoading && totalExpected > 0 && (
          <span className="progress-counter">
            {successCount} of {totalExpected} complete
            {failedModels.length > 0 && <span className="failed-count">, {failedModels.length} failed</span>}
          </span>
        )}
      </h3>

      <div className="tabs">
        {allModels.map((model, index) => {
          const completed = isCompleted(model);
          const failed = isFailed(model);
          const modelName = model.split('/')[1] || model;

          return (
            <button
              key={model}
              className={`tab ${activeTab === index ? 'active' : ''} ${completed ? 'completed' : 'pending'} ${failed ? 'failed' : ''} ${completed ? 'tab-appear' : ''}`}
              onClick={() => completed && setActiveTab(index)}
              disabled={!completed}
            >
              {failed ? (
                <>
                  <span className="failed-text">{modelName}</span>
                  <span className="failed-icon">✗</span>
                </>
              ) : completed ? (
                modelName
              ) : (
                <>
                  <span className="skeleton-text">{modelName}</span>
                  <span className="tab-spinner"></span>
                </>
              )}
            </button>
          );
        })}
      </div>

      <div className="tab-content">
        {responses && responses.length > 0 && activeTab < responses.length ? (
          responses[activeTab].error ? (
            <div className="content-error fade-in">
              <div className="error-icon">⚠</div>
              <div className="error-message">
                <strong>{responses[activeTab].model_name || responses[activeTab].model}</strong> failed to respond.
                <p>The model timed out or encountered an error.</p>
              </div>
            </div>
          ) : (
            <>
              <div className="model-name">{responses[activeTab].model}</div>
              <div className="response-text markdown-content fade-in">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{responses[activeTab].response}</ReactMarkdown>
              </div>
            </>
          )
        ) : isLoading ? (
          <div className="content-loading">
            <div className="content-spinner"></div>
            <span>Waiting for model responses...</span>
          </div>
        ) : null}
      </div>
    </div>
  );
}
