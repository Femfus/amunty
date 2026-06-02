import { useEffect, useRef, useState } from 'react';
import { useChatStore, type Message } from '../../stores/chatStore';
import { useSettingsStore } from '../../stores/settingsStore';
import { MessageBubble } from './MessageBubble';
import { ToolCallCard } from './ToolCallCard';
import { AmuntyLogo } from '../common/AmuntyLogo';
import styles from './ChatPanel.module.css';

export function ChatPanel() {
  const messages = useChatStore((s) => s.messages);
  const activeConversation = useChatStore((s) => s.activeConversation);
  const isStreaming = useChatStore((s) => s.isStreaming);
  const streamingContent = useChatStore((s) => s.streamingContent);
  const streamingToolCalls = useChatStore((s) => s.streamingToolCalls);
  const setMobileOpen = useChatStore((s) => s.setMobileSidebarOpen);
  const sendMessage = useChatStore((s) => s.sendMessage);
  const stopGeneration = useChatStore((s) => s.stopGeneration);
  const models = useSettingsStore((s) => s.models);
  const settings = useSettingsStore((s) => s.settings);

  const [input, setInput] = useState('');
  const [selectedModel, setSelectedModel] = useState('');
  const [attachments, setAttachments] = useState<{ file: File; base64?: string; text?: string; type: 'image' | 'text' }[]>([]);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const processFiles = async (files: File[]) => {
    const newAttachments: typeof attachments = [];
    for (const file of files) {
      if (file.type.startsWith('image/')) {
        try {
          const base64 = await new Promise<string>((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = (e) => resolve(e.target?.result as string);
            reader.onerror = reject;
            reader.readAsDataURL(file);
          });
          newAttachments.push({ file, base64, type: 'image' });
        } catch (err) {
          alert(`Failed to read image: ${file.name}`);
        }
        continue;
      }
      try {
        const text = await file.text();
        newAttachments.push({ file, text, type: 'text' });
      } catch (err) {
        alert(`Failed to read file: ${file.name}`);
      }
    }
    setAttachments((prev) => [...prev, ...newAttachments]);
  };

  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files) return;
    await processFiles(Array.from(e.target.files));
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const handleDrop = async (e: React.DragEvent) => {
    e.preventDefault();
    if (!e.dataTransfer.files || e.dataTransfer.files.length === 0) return;
    await processFiles(Array.from(e.dataTransfer.files));
  };

  // Auto-scroll on new messages/tokens
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, streamingContent]);

  // Set default model
  useEffect(() => {
    if (!selectedModel && settings['default_model']) {
      setSelectedModel(settings['default_model']);
    } else if (!selectedModel && models.length > 0) {
      setSelectedModel(models[0]!.id);
    }
  }, [models, settings, selectedModel]);

  // Auto-resize textarea
  useEffect(() => {
    const ta = textareaRef.current;
    if (ta) {
      ta.style.height = 'auto';
      ta.style.height = `${Math.min(ta.scrollHeight, 200)}px`;
    }
  }, [input]);

  const handleSend = async () => {
    const trimmed = input.trim();
    if ((!trimmed && attachments.length === 0) || isStreaming) return;

    let finalContent = trimmed;
    for (const att of attachments) {
      if (att.type === 'image' && att.base64) {
        finalContent += `\n\n![Attached Image: ${att.file.name}](${att.base64})\n`;
      } else if (att.type === 'text' && att.text) {
        finalContent += `\n\n--- Attached File: ${att.file.name} ---\n\`\`\`\n${att.text}\n\`\`\`\n`;
      }
    }

    setInput('');
    setAttachments([]);
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
    await sendMessage(finalContent, selectedModel || undefined);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const msgCount = messages.length;

  if (!activeConversation) {
    return (
      <main className={styles.panel} id="chat-panel">
        <header className={styles.header}>
          <button className={styles.mobileHamburgerBtn} onClick={() => setMobileOpen(true)}>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="18" x2="21" y2="18"/></svg>
          </button>
        </header>
        <div className={styles.emptyState}>
          <AmuntyLogo size={56} className={styles.welcomeBoat} />
          <div className={styles.emptyTitle}>Amunty</div>
          <p className={styles.emptySubtitle}>
            Select a conversation or click + to start chatting.
          </p>
          {models.length === 0 && (
            <p className={styles.emptyWarning}>
              ⚠ No models configured. Add a backend in Settings to get started.
            </p>
          )}
        </div>
      </main>
    );
  }

  return (
    <main 
      className={styles.panel} 
      id="chat-panel"
      onDragOver={(e) => e.preventDefault()}
      onDrop={handleDrop}
    >
      {/* Header */}
      <header className={styles.header}>
        <button className={styles.mobileHamburgerBtn} onClick={() => setMobileOpen(true)}>
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="18" x2="21" y2="18"/></svg>
        </button>
        <div className={styles.headerCenter}>
          <div className={styles.sessionBadge} title="Session ID">ID: {activeConversation.id.substring(0,8)}</div>
          <select
            id="model-selector"
            className={styles.modelPill}
            value={selectedModel}
            onChange={(e) => setSelectedModel(e.target.value)}
          >
            {models.map((m) => (
              <option key={m.id} value={m.id}>
                {m.name}
              </option>
            ))}
          </select>
          {msgCount > 0 && <span className={styles.headerTime}>9:55 AM <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="6 9 12 15 18 9"/></svg></span>}
        </div>
      </header>

      {/* Messages */}
      <div className={styles.messages} id="messages-container">
        <div className={styles.messagesInner}>
          {messages.filter(m => m.role !== 'tool').map((msg) => (
            <MessageBubble key={msg.id} message={msg} />
          ))}

          {/* Tool call cards during streaming */}
          {isStreaming && streamingToolCalls.length > 0 && (
            <div>
              {streamingToolCalls.map((tc) => (
                <ToolCallCard key={tc.id} toolCall={tc} />
              ))}
            </div>
          )}

          {/* Streaming indicator */}
          {isStreaming && streamingContent && (
            <MessageBubble
              message={{
                id: 'streaming',
                role: 'assistant',
                content: streamingContent,
                created_at: new Date().toISOString(),
                model_id: selectedModel || undefined,
              }}
              isStreaming
            />
          )}

          {isStreaming && !streamingContent && streamingToolCalls.length === 0 && (
            <div className={styles.typingIndicator}>
              <span className={styles.dot} />
              <span className={styles.dot} />
              <span className={styles.dot} />
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* Input Area */}
      <div className={styles.inputArea}>
        <div className={styles.inputWrapper}>
          {attachments.length > 0 && (
            <div className={styles.attachmentsTray}>
              {attachments.map((att, i) => (
                <div key={i} className={styles.attachmentThumb}>
                  {att.type === 'image' ? (
                    <img src={att.base64} alt={att.file.name} className={styles.attachmentImg} />
                  ) : (
                    <div className={styles.attachmentDoc}>
                      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
                      <span className={styles.attachmentName}>{att.file.name}</span>
                    </div>
                  )}
                  <button 
                    className={styles.removeAttachment}
                    onClick={() => setAttachments(a => a.filter((_, idx) => idx !== i))}
                  >
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
                  </button>
                </div>
              ))}
            </div>
          )}
          <div className={styles.inputTop}>
            <textarea
              id="chat-input"
              ref={textareaRef}
              className={styles.textarea}
              placeholder="Message Amunty..."
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              rows={1}
              disabled={isStreaming}
            />
          </div>
          <div className={styles.inputBottom}>
            <div className={styles.inputActions}>
              <button className={styles.attachBtn} title="Attach files or images" onClick={() => fileInputRef.current?.click()}>
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48"/>
                </svg>
              </button>
              <input type="file" ref={fileInputRef} hidden onChange={handleFileSelect} multiple accept="image/png,image/jpeg,image/jpg,image/svg+xml,image/webp,image/gif,text/*,.json,.md,.csv,.log" />
            </div>
            <div className={styles.inputRight}>
              <div className={styles.modeToggle}>
                <button className={styles.modeBtn}>Agent</button>
                <button className={`${styles.modeBtn} ${styles.modeActive}`}>Chat</button>
              </div>
              {isStreaming ? (
                <button
                  id="stop-btn"
                  className={styles.stopBtn}
                  onClick={stopGeneration}
                  title="Stop generation"
                >
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
                    <rect x="6" y="6" width="12" height="12" rx="2" />
                  </svg>
                </button>
              ) : (
                <button
                  id="send-btn"
                  className={styles.sendBtn}
                  onClick={handleSend}
                  disabled={!input.trim()}
                  title="Send (Enter)"
                >
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <line x1="22" y1="2" x2="11" y2="13" />
                    <polygon points="22 2 15 22 11 13 2 9 22 2" />
                  </svg>
                </button>
              )}
            </div>
          </div>
        </div>
      </div>
    </main>
  );
}
