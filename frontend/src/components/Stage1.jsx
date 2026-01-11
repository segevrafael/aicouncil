import { useState, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import './Stage1.css';

export default function Stage1({ responses, title, expectedModels, isLoading }) {
  const [activeTab, setActiveTab] = useState(0);

  // Get list of models that have responded
  const completedModels = responses?.map(r => r.model) || [];

  // Build the full tab list: completed + pending
  const allModels = expectedModels || completedModels;
  const totalExpected = allModels.length;
  const completedCount = completedModels.length;

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

  // Check if a model has completed
  const isCompleted = (model) => completedModels.includes(model);

  return (
    <div className="stage stage1">
      <h3 className="stage-title">
        {title || 'Stage 1: Individual Responses'}
        {isLoading && totalExpected > 0 && (
          <span className="progress-counter">
            {completedCount} of {totalExpected} complete
          </span>
        )}
      </h3>

      <div className="tabs">
        {allModels.map((model, index) => {
          const completed = isCompleted(model);
          const modelName = model.split('/')[1] || model;

          return (
            <button
              key={model}
              className={`tab ${activeTab === index ? 'active' : ''} ${completed ? 'completed' : 'pending'} ${completed ? 'tab-appear' : ''}`}
              onClick={() => completed && setActiveTab(index)}
              disabled={!completed}
            >
              {completed ? (
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
          <>
            <div className="model-name">{responses[activeTab].model}</div>
            <div className="response-text markdown-content fade-in">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{responses[activeTab].response}</ReactMarkdown>
            </div>
          </>
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
