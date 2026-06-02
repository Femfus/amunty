import { useState } from 'react';
import type { ToolCall } from '../../stores/chatStore';
import styles from './ToolCallCard.module.css';

interface ToolCallCardProps {
  toolCall: ToolCall;
}

const TOOL_ICONS: Record<string, string> = {
  get_current_time: '🕐',
  set_reminder: '⏰',
  show_notification: '🔔',
  open_application: '🚀',
  open_url: '🌐',
  get_system_info: '💻',
  list_directory: '📁',
  read_file: '📄',
  search_files: '🔍',
  get_clipboard: '📋',
  set_clipboard: '📋',
  run_command: '⚡',
  get_running_processes: '📊',
  get_weather: '🌤️',
};

function formatToolName(name: string): string {
  return name.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

function formatParams(params: string): string {
  try {
    const parsed = JSON.parse(params);
    return Object.entries(parsed)
      .map(([k, v]) => `${k}: ${JSON.stringify(v)}`)
      .join(', ');
  } catch {
    return params;
  }
}

function formatOutput(output: string): string {
  try {
    const parsed = JSON.parse(output);
    return JSON.stringify(parsed, null, 2);
  } catch {
    return output;
  }
}

export function ToolCallCard({ toolCall }: ToolCallCardProps) {
  const [expanded, setExpanded] = useState(false);

  const icon = TOOL_ICONS[toolCall.name] || '🔧';
  const statusIcon =
    toolCall.status === 'running' ? (
      <span className={styles.spinner} />
    ) : toolCall.status === 'done' ? (
      '✓'
    ) : (
      '✗'
    );

  return (
    <div
      className={`${styles.card} ${styles[toolCall.status]}`}
      id={`tool-${toolCall.id}`}
    >
      <div className={styles.body}>
        <div className={styles.header} onClick={() => setExpanded(!expanded)}>
          <span className={`${styles.icon} ${styles[toolCall.status]}`}>
            {statusIcon}
          </span>
          <span className={styles.toolName}>
            {icon} {formatToolName(toolCall.name)}
          </span>
          <span className={styles.status}>
            {toolCall.status === 'running'
              ? 'executing...'
              : toolCall.status === 'done'
              ? 'done'
              : 'failed'}
          </span>
          <span className={`${styles.chevron} ${expanded ? styles.open : ''}`}>
            ▶
          </span>
        </div>

        <div className={`${styles.content} ${expanded ? styles.open : ''}`}>
          {toolCall.params && toolCall.params !== '{}' && (
            <div className={styles.params}>{formatParams(toolCall.params)}</div>
          )}
          {toolCall.output && (
            <div className={styles.output}>{formatOutput(toolCall.output)}</div>
          )}
        </div>
      </div>
    </div>
  );
}
