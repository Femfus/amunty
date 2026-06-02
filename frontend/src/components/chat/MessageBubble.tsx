import { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import type { Message } from '../../stores/chatStore';
import styles from './MessageBubble.module.css';

interface MessageBubbleProps {
  message: Message;
  isStreaming?: boolean;
}

const COPY_ICON = (
  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <rect x="9" y="9" width="13" height="13" rx="2" />
    <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
  </svg>
);

const CHECK_ICON = (
  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="20 6 9 17 4 12" />
  </svg>
);

function shortModel(name?: string | null): string {
  if (!name) return 'Amunty';
  const short = name.split('/').pop() || name;
  return short.length > 25 ? short.substring(0, 22) + '…' : short;
}

function modelColor(name?: string | null): string | null {
  if (!name) return null;
  const key = name.toLowerCase();
  let hash = 0;
  for (let i = 0; i < key.length; i++) {
    hash = ((hash << 5) - hash + key.charCodeAt(i)) | 0;
  }
  const hue = ((hash % 360) + 360) % 360;
  return `hsl(${hue}, 55%, 65%)`;
}

export function MessageBubble({ message, isStreaming = false }: MessageBubbleProps) {
  const isUser = message.role === 'user';
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(message.content);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // fallback
    }
  };

  const color = modelColor(message.model_id);
  const dotStyle = color ? { '--model-dot': color } as React.CSSProperties : undefined;

  let userText = message.content;
  const images: {name: string, url: string}[] = [];
  const files: {name: string}[] = [];

  if (isUser) {
    const imgRegex = /!\[Attached Image: (.*?)\]\((data:image\/[^;]+;base64,[^\)]+)\)/g;
    let match;
    while ((match = imgRegex.exec(userText)) !== null) {
      images.push({ name: match[1], url: match[2] });
    }
    userText = userText.replace(imgRegex, '');

    const fileRegex = /--- Attached File: (.*?) ---\n```\n[\s\S]*?\n```\n/g;
    while ((match = fileRegex.exec(userText)) !== null) {
      files.push({ name: match[1] });
    }
    userText = userText.replace(fileRegex, '').trim();
  }

  return (
    <div
      className={`${styles.bubble} ${isUser ? styles.user : styles.assistant} ${
        isStreaming ? styles.streaming : ''
      }`}
      id={`msg-${message.id}`}
    >
      {/* Role header */}
      <div
        className={`${styles.role} ${isUser ? styles.roleUser : styles.roleAssistant}`}
        style={!isUser && color ? { color } : undefined}
      >
        <span style={!isUser && dotStyle ? dotStyle : undefined} />
        {isUser ? 'You' : shortModel(message.model_id)}
        <span className={styles.roleTimestamp}>
          {new Date(message.created_at).toLocaleTimeString([], {
            hour: '2-digit',
            minute: '2-digit',
          })}
        </span>
      </div>

      {/* Content */}
      <div className={styles.content}>
        {isUser ? (
          <div className={styles.userContent}>
            {(images.length > 0 || files.length > 0) && (
              <div className={styles.messageAttachments}>
                {images.map((img, i) => (
                  <img key={`img-${i}`} src={img.url} alt={img.name} className={styles.messageImg} title={img.name} />
                ))}
                {files.map((f, i) => (
                  <div key={`file-${i}`} className={styles.messageDoc}>
                     <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
                     <span>{f.name}</span>
                  </div>
                ))}
              </div>
            )}
            {userText && <p className={styles.userText}>{userText}</p>}
          </div>
        ) : (
          <div className={styles.markdown}>
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{
                code({ className, children, ...props }) {
                  const isInline = !className;
                  if (isInline) {
                    return <code className={styles.inlineCode} {...props}>{children}</code>;
                  }
                  return (
                    <pre className={styles.codeBlock}>
                      <code className={className} {...props}>
                        {children}
                      </code>
                    </pre>
                  );
                },
                table({ children }) {
                  return (
                    <div className={styles.tableWrapper}>
                      <table className={styles.table}>{children}</table>
                    </div>
                  );
                },
              }}
            >
              {message.content}
            </ReactMarkdown>
            {isStreaming && <span className={styles.cursor}>▊</span>}
          </div>
        )}

        {/* Footer — copy actions (hover reveal) */}
        {!isStreaming && message.content && (
          <div className={styles.footer}>
            <button
              className={styles.footerBtn}
              onClick={handleCopy}
              title={copied ? 'Copied!' : 'Copy message'}
            >
              {copied ? CHECK_ICON : COPY_ICON}
              <span>{copied ? 'Copied' : 'Copy'}</span>
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
