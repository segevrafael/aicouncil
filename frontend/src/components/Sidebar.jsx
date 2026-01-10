import './Sidebar.css';

export default function Sidebar({
  conversations,
  currentConversationId,
  onSelectConversation,
  onNewConversation,
  onArchiveConversation,
  onLogout,
  showArchived,
  onToggleShowArchived,
}) {
  const handleArchive = (e, convId, isArchived) => {
    e.stopPropagation(); // Prevent selecting the conversation
    e.preventDefault();
    if (onArchiveConversation) {
      onArchiveConversation(convId, !isArchived);
    } else {
      console.error('onArchiveConversation is not defined!');
    }
  };

  // Separate archived and active conversations
  const activeConversations = conversations.filter((c) => !c.is_archived);
  const archivedConversations = conversations.filter((c) => c.is_archived);

  return (
    <div className="sidebar">
      <div className="sidebar-header">
        <h1>AI Council</h1>
        <button type="button" className="new-conversation-btn" onClick={onNewConversation}>
          + New
        </button>
      </div>

      <div className="conversation-list">
        {activeConversations.length === 0 && !showArchived ? (
          <div className="no-conversations">No conversations yet</div>
        ) : (
          <>
            {activeConversations.map((conv) => (
              <div
                key={conv.id}
                className={`conversation-item ${
                  conv.id === currentConversationId ? 'active' : ''
                }`}
                onClick={() => onSelectConversation(conv.id)}
              >
                <div className="conversation-content">
                  <div className="conversation-title">
                    {conv.title || 'New Conversation'}
                  </div>
                  <div className="conversation-meta">
                    {conv.message_count} messages
                  </div>
                </div>
                <button
                  type="button"
                  className="archive-btn"
                  onClick={(e) => handleArchive(e, conv.id, conv.is_archived)}
                  title="Archive conversation"
                >
                  📦
                </button>
              </div>
            ))}

            {/* Archived section */}
            {archivedConversations.length > 0 && (
              <div className="archived-section">
                <button
                  type="button"
                  className="toggle-archived-btn"
                  onClick={onToggleShowArchived}
                >
                  {showArchived ? '▼' : '▶'} Archived ({archivedConversations.length})
                </button>

                {showArchived && (
                  <div className="archived-list">
                    {archivedConversations.map((conv) => (
                      <div
                        key={conv.id}
                        className={`conversation-item archived ${
                          conv.id === currentConversationId ? 'active' : ''
                        }`}
                        onClick={() => onSelectConversation(conv.id)}
                      >
                        <div className="conversation-content">
                          <div className="conversation-title">
                            {conv.title || 'New Conversation'}
                          </div>
                          <div className="conversation-meta">
                            {conv.message_count} messages
                          </div>
                        </div>
                        <button
                          type="button"
                          className="archive-btn unarchive"
                          onClick={(e) => handleArchive(e, conv.id, conv.is_archived)}
                          title="Unarchive conversation"
                        >
                          📤
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </>
        )}
      </div>

      <div className="sidebar-footer">
        <button type="button" className="logout-btn" onClick={onLogout}>
          Logout
        </button>
      </div>
    </div>
  );
}
