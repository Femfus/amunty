/* ── API client — typed fetch wrapper ── */

const BASE_URL = '/api';

function getToken(): string | null {
  return localStorage.getItem('amunty_token');
}

export function setToken(token: string): void {
  localStorage.setItem('amunty_token', token);
}

export function clearToken(): void {
  localStorage.removeItem('amunty_token');
}

export function isAuthenticated(): boolean {
  return getToken() !== null;
}

async function request<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string> || {}),
  };

  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const response = await fetch(`${BASE_URL}${path}`, {
    ...options,
    headers,
  });

  if (response.status === 401) {
    clearToken();
    window.location.href = '/login';
    throw new Error('Unauthorized');
  }

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json();
}

export const api = {
  get: <T>(path: string) => request<T>(path),

  post: <T>(path: string, body?: unknown) =>
    request<T>(path, {
      method: 'POST',
      body: body ? JSON.stringify(body) : undefined,
    }),

  put: <T>(path: string, body?: unknown) =>
    request<T>(path, {
      method: 'PUT',
      body: body ? JSON.stringify(body) : undefined,
    }),

  delete: <T>(path: string) =>
    request<T>(path, { method: 'DELETE' }),

  /** Create an EventSource for SSE streaming with auth. */
  stream: (path: string, body: unknown): EventSource | ReadableStreamDefaultReader<string> => {
    // EventSource doesn't support POST or auth headers,
    // so we use fetch with streaming instead.
    const token = getToken();
    const controller = new AbortController();

    const fetchStream = async function* (): AsyncGenerator<string> {
      const response = await fetch(`${BASE_URL}${path}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
        },
        body: JSON.stringify(body),
        signal: controller.signal,
      });

      if (!response.ok) {
        throw new Error(`Stream error: ${response.status}`);
      }

      const reader = response.body?.getReader();
      if (!reader) throw new Error('No response body');

      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          const trimmed = line.trim();
          if (trimmed.startsWith('data: ')) {
            yield trimmed.slice(6);
          }
        }
      }
    };

    return { [Symbol.asyncIterator]: fetchStream, abort: () => controller.abort() } as any;
  },
};

/** Helper to consume an SSE stream from the chat endpoint. */
export async function streamChat(
  sessionId: string,
  message: string,
  modelId: string | null,
  onEvent: (event: ChatEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const token = getToken();

  const response = await fetch(`${BASE_URL}/chat/send`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({
      session_id: sessionId,
      message,
      model_id: modelId,
    }),
    signal,
  });

  if (!response.ok) {
    const err = await response.json().catch(() => ({ detail: 'Stream failed' }));
    onEvent({ type: 'error', content: err.detail });
    return;
  }

  const reader = response.body?.getReader();
  if (!reader) return;

  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop() || '';

    for (const line of lines) {
      const trimmed = line.trim();
      if (trimmed.startsWith('data: ')) {
        try {
          const event = JSON.parse(trimmed.slice(6)) as ChatEvent;
          onEvent(event);
        } catch {
          // Skip malformed JSON
        }
      }
    }
  }
}

export interface ChatEvent {
  type: 'token' | 'tool_call' | 'tool_result' | 'done' | 'error' | 'clear';
  content?: string;
  name?: string;
  params?: string;
  output?: string;
  message_id?: string;
}
