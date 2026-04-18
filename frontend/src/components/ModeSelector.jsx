import { useState } from 'react';
import './ModeSelector.css';

const MODE_ICONS = {
  independent: '|||',
  synthesized: '->',
  debate: '<->',
  adversarial: '!?',
  socratic: '?',
  scenario: '~',
};

export default function ModeSelector({
  modes,
  councilTypes,
  roles,
  enhancements,
  selectedMode,
  selectedCouncilType,
  rolesEnabled,
  selectedEnhancements,
  webSearchEnabled,
  onModeChange,
  onCouncilTypeChange,
  onRolesToggle,
  onEnhancementsChange,
  onWebSearchToggle,
  disabled,
}) {
  const [showAdvanced, setShowAdvanced] = useState(false);

  if (!modes || !councilTypes) {
    return null;
  }

  return (
    <div className="mode-selector">
      {/* Mode Selection */}
      <div className="mode-section">
        <label className="section-label">Mode</label>
        <div className="mode-tabs">
          {Object.entries(modes).map(([key, mode]) => (
            <button
              key={key}
              className={`mode-tab ${selectedMode === key ? 'active' : ''}`}
              onClick={() => onModeChange(key)}
              disabled={disabled}
              title={mode.description}
            >
              <span className="mode-icon">{MODE_ICONS[key] || '?'}</span>
              <span className="mode-name">{mode.name}</span>
              {mode.multi_round && <span className="mode-badge">Multi-round</span>}
            </button>
          ))}
        </div>
        <p className="mode-description">
          {modes[selectedMode]?.description}
        </p>
      </div>

      {/* Council Type Selection */}
      <div className="council-type-section">
        <label className="section-label">Council Type</label>
        <select
          className="council-type-select"
          value={selectedCouncilType}
          onChange={(e) => onCouncilTypeChange(e.target.value)}
          disabled={disabled}
        >
          {Object.entries(councilTypes).map(([key, type]) => (
            <option key={key} value={key}>
              {type.name}
            </option>
          ))}
        </select>
        <p className="type-description">
          {councilTypes[selectedCouncilType]?.description}
        </p>
      </div>

      {/* Advanced Options Toggle */}
      <button
        className="advanced-toggle"
        onClick={() => setShowAdvanced(!showAdvanced)}
      >
        {showAdvanced ? '- Hide Advanced Options' : '+ Show Advanced Options'}
      </button>

      {showAdvanced && (
        <div className="advanced-options">
          {/* Roles Toggle */}
          <div className="roles-section">
            <label className="checkbox-label">
              <input
                type="checkbox"
                checked={rolesEnabled}
                onChange={(e) => onRolesToggle(e.target.checked)}
                disabled={disabled}
              />
              <span>Enable Specialist Roles</span>
            </label>
            {rolesEnabled && roles && (
              <div className="roles-preview">
                {Object.entries(roles).map(([key, role]) => (
                  <span key={key} className={`role-badge role-${key}`}>
                    {role.name}
                  </span>
                ))}
              </div>
            )}
          </div>

          {/* Web Search Toggle */}
          <div className="web-search-section">
            <label className="checkbox-label">
              <input
                type="checkbox"
                checked={webSearchEnabled}
                onChange={(e) => onWebSearchToggle(e.target.checked)}
                disabled={disabled}
              />
              <span>Enable Web Search</span>
            </label>
            <p className="web-search-hint">
              Models will search the web for current information. Adds ~$0.001 per model query.
            </p>
          </div>

          {/* Enhancements */}
          <div className="enhancements-section">
            <label className="section-label">Output Enhancements</label>
            <div className="enhancement-checkboxes">
              {enhancements && Object.entries(enhancements).map(([key, enhancement]) => (
                <label key={key} className="checkbox-label">
                  <input
                    type="checkbox"
                    checked={selectedEnhancements.includes(key)}
                    onChange={(e) => {
                      if (e.target.checked) {
                        onEnhancementsChange([...selectedEnhancements, key]);
                      } else {
                        onEnhancementsChange(selectedEnhancements.filter(k => k !== key));
                      }
                    }}
                    disabled={disabled}
                  />
                  <span title={enhancement.description}>{enhancement.name}</span>
                </label>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
