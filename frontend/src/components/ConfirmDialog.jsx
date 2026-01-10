import './ConfirmDialog.css';

export default function ConfirmDialog({
  isOpen,
  title,
  message,
  options,
  onSelect,
  onCancel,
}) {
  if (!isOpen) return null;

  return (
    <div className="confirm-dialog-overlay" onClick={onCancel}>
      <div className="confirm-dialog" onClick={(e) => e.stopPropagation()}>
        <h3 className="confirm-dialog-title">{title}</h3>
        <p className="confirm-dialog-message">{message}</p>

        <div className="confirm-dialog-options">
          {options.map((option, index) => (
            <button
              key={index}
              type="button"
              className={`confirm-dialog-btn ${option.variant || ''}`}
              onClick={() => onSelect(option.value)}
            >
              {option.label}
            </button>
          ))}
        </div>

        <button
          type="button"
          className="confirm-dialog-cancel"
          onClick={onCancel}
        >
          Cancel
        </button>
      </div>
    </div>
  );
}
