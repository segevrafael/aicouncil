import { useState, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import './Stage2.css';

function deAnonymizeText(text, labelToModel) {
  if (!labelToModel) return text;

  let result = text;
  // Replace each "Response X" with the actual model name
  Object.entries(labelToModel).forEach(([label, model]) => {
    const modelShortName = model.split('/')[1] || model;
    result = result.replace(new RegExp(label, 'g'), `**${modelShortName}**`);
  });
  return result;
}

export default function Stage2({ rankings, labelToModel, aggregateRankings, expectedModels, isLoading }) {
  const [activeTab, setActiveTab] = useState(0);

  // Get list of models that have responded (including failed ones)
  const completedModels = rankings?.map(r => r.model) || [];

  // Get list of failed models
  const failedModels = rankings?.filter(r => r.error)?.map(r => r.model) || [];

  // Build the full tab list: completed + pending
  const allModels = expectedModels || completedModels;
  const totalExpected = allModels.length;
  const completedCount = completedModels.length;
  const successCount = completedCount - failedModels.length;

  // Auto-select the first completed tab when streaming
  useEffect(() => {
    if (rankings?.length === 1 && activeTab !== 0) {
      setActiveTab(0);
    }
  }, [rankings?.length]);

  // Check if a model has completed (includes failed)
  const isCompleted = (model) => completedModels.includes(model);

  // Check if a model has failed
  const isFailed = (model) => failedModels.includes(model);

  // Get ranking for a model (if completed)
  const getRanking = (model) => rankings?.find(r => r.model === model);

  // Don't render if no rankings and not loading
  if ((!rankings || rankings.length === 0) && !isLoading) {
    return null;
  }

  return (
    <div className="stage stage2">
      <h3 className="stage-title">
        Stage 2: Peer Rankings
        {isLoading && totalExpected > 0 && (
          <span className="progress-counter">
            {successCount} of {totalExpected} complete
            {failedModels.length > 0 && <span className="failed-count">, {failedModels.length} failed</span>}
          </span>
        )}
      </h3>

      <h4>Raw Evaluations</h4>
      <p className="stage-description">
        Each model evaluated all responses (anonymized as Response A, B, C, etc.) and provided rankings.
        Below, model names are shown in <strong>bold</strong> for readability, but the original evaluation used anonymous labels.
      </p>

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
        {rankings && rankings.length > 0 && activeTab < rankings.length ? (
          rankings[activeTab].error ? (
            <div className="content-error fade-in">
              <div className="error-icon">⚠</div>
              <div className="error-message">
                <strong>{rankings[activeTab].model_name || rankings[activeTab].model}</strong> failed to submit rankings.
                <p>The model timed out or encountered an error.</p>
              </div>
            </div>
          ) : (
            <>
              <div className="ranking-model">
                {rankings[activeTab].model}
              </div>
              <div className="ranking-content markdown-content fade-in">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {deAnonymizeText(rankings[activeTab].ranking, labelToModel)}
                </ReactMarkdown>
              </div>

              {rankings[activeTab].parsed_ranking &&
               rankings[activeTab].parsed_ranking.length > 0 && (
                <div className="parsed-ranking fade-in">
                  <strong>Extracted Ranking:</strong>
                  <ol>
                    {rankings[activeTab].parsed_ranking.map((label, i) => (
                      <li key={i}>
                        {labelToModel && labelToModel[label]
                          ? labelToModel[label].split('/')[1] || labelToModel[label]
                          : label}
                      </li>
                    ))}
                  </ol>
                </div>
              )}
            </>
          )
        ) : isLoading ? (
          <div className="content-loading">
            <div className="content-spinner"></div>
            <span>Waiting for peer rankings...</span>
          </div>
        ) : null}
      </div>

      {aggregateRankings && aggregateRankings.length > 0 && (
        <div className="aggregate-rankings fade-in">
          <h4>Aggregate Rankings (Street Cred)</h4>
          <p className="stage-description">
            Combined results across all peer evaluations (lower score is better):
          </p>
          <div className="aggregate-list">
            {aggregateRankings.map((agg, index) => (
              <div key={index} className="aggregate-item">
                <span className="rank-position">#{index + 1}</span>
                <span className="rank-model">
                  {agg.model.split('/')[1] || agg.model}
                </span>
                <span className="rank-score">
                  Avg: {agg.average_rank.toFixed(2)}
                </span>
                <span className="rank-count">
                  ({agg.rankings_count} votes)
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
