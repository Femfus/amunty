import { useEffect } from 'react';
import { useChatStore } from '../../stores/chatStore';
import styles from './ChatsPanel.module.css';

interface ChatsPanelProps {
  onClose: () => void;
}

export function ChatsPanel({ onClose }: ChatsPanelProps) {
  const conversations = useChatStore((s) => s.conversations);
  const loadConversations = useChatStore((s) => s.loadConversations);
  const selectConversation = useChatStore((s) => s.selectConversation);
  const deleteConversation = useChatStore((s) => s.deleteConversation);
  const activeConversation = useChatStore((s) => s.activeConversation);

  useEffect(() => {
    loadConversations();
  }, [loadConversations]);

  const handleSelect = async (id: string) => {
    await selectConversation(id);
    onClose();
  };

  const handleDelete = async (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    if (confirm('Are you sure you want to delete this chat?')) {
      await deleteConversation(id);
    }
  };

  return (
    <div className={styles.overlay} onClick={onClose}>
      <div className={styles.panel} onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <header className={styles.header}>
          <div>
            <h2 className={styles.title}>💬 Chat History</h2>
            <p className={styles.subtitle}>Resume your past conversations</p>
          </div>
          <button className={styles.closeBtn} onClick={onClose} title="Close">
            ✕
          </button>
        </header>

        {/* List */}
        <div className={styles.list}>
          {conversations.length === 0 ? (
            <div className={styles.empty}>No chat history found.</div>
          ) : (
            conversations.map((conv) => (
              <div
                key={conv.id}
                className={`${styles.chatItem} ${activeConversation?.id === conv.id ? styles.active : ''}`}
                onClick={() => handleSelect(conv.id)}
              >
                <div className={styles.chatInfo}>
                  <h4 className={styles.chatTitle}>{conv.title || 'New Chat'}</h4>
                  <div className={styles.chatMeta}>
                    <span className={styles.modelBadge}>{conv.model_id}</span>
                    <span className={styles.sessionBadge}>ID: {conv.id.substring(0,8)}</span>
                    <span className={styles.date}>
                      {new Date(conv.created_at).toLocaleDateString()}
                    </span>
                    <span className={styles.msgCount}>{conv.message_count} msgs</span>
                  </div>
                </div>
                <button
                  className={styles.deleteBtn}
                  onClick={(e) => handleDelete(e, conv.id)}
                  title="Delete Chat"
                >
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M3 6h18" />
                    <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
                  </svg>
                </button>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
