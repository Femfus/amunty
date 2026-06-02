import { create } from 'zustand';
import { api, streamChat, type ChatEvent } from '../utils/api';

export interface ToolCall {
  id: string;
  name: string;
  params: string;
  output?: string;
  status: 'running' | 'done' | 'error';
}

export interface Message {
  id: string;
  role: 'user' | 'assistant' | 'system' | 'tool';
  content: string;
  tool_calls?: string | null;
  tool_call_id?: string | null;
  model_id?: string | null;
  token_count?: number | null;
  created_at: string;
}

export interface Conversation {
  id: string;
  title: string;
  model_id: string;
  system_prompt: string | null;
  is_archived: boolean;
  created_at: string;
  updated_at: string;
  message_count: number;
}

interface ChatState {
  conversations: Conversation[];
  activeConversation: Conversation | null;
  messages: Message[];
  isStreaming: boolean;
  streamingContent: string;
  streamingToolCalls: ToolCall[];
  abortController: AbortController | null;
  isMobileSidebarOpen: boolean;

  setMobileSidebarOpen: (isOpen: boolean) => void;
  loadConversations: () => Promise<void>;
  selectConversation: (id: string) => Promise<void>;
  createConversation: (modelId: string) => Promise<Conversation>;
  deleteConversation: (id: string) => Promise<void>;
  sendMessage: (content: string, modelId?: string) => Promise<void>;
  stopGeneration: () => void;
  updateTitle: (id: string, title: string) => Promise<void>;
}

export const useChatStore = create<ChatState>((set, get) => ({
  conversations: [],
  activeConversation: null,
  messages: [],
  isStreaming: false,
  streamingContent: '',
  streamingToolCalls: [],
  abortController: null,
  isMobileSidebarOpen: false,

  setMobileSidebarOpen: (isOpen: boolean) => set({ isMobileSidebarOpen: isOpen }),

  loadConversations: async () => {
    try {
      const conversations = await api.get<Conversation[]>('/conversations');
      set({ conversations });
    } catch (err) {
      console.error('Failed to load conversations:', err);
    }
  },

  selectConversation: async (id: string) => {
    try {
      const data = await api.get<{
        conversation: Conversation;
        messages: Message[];
      }>(`/conversations/${id}`);
      set({
        activeConversation: data.conversation,
        messages: data.messages,
        streamingContent: '',
      });
      window.location.hash = `/chat/${id}`;
    } catch (err) {
      console.error('Failed to load conversation:', err);
    }
  },

  createConversation: async (modelId: string) => {
    const conv = await api.post<Conversation>('/conversations', {
      title: 'New Chat',
      model_id: modelId,
    });
    set((state) => ({
      conversations: [conv, ...state.conversations],
      activeConversation: conv,
      messages: [],
      streamingContent: '',
    }));
    window.location.hash = `/chat/${conv.id}`;
    return conv;
  },

  deleteConversation: async (id: string) => {
    await api.delete(`/conversations/${id}`);
    const state = get();
    const remaining = state.conversations.filter((c) => c.id !== id);
    set({
      conversations: remaining,
      activeConversation: state.activeConversation?.id === id ? null : state.activeConversation,
      messages: state.activeConversation?.id === id ? [] : state.messages,
    });
    if (state.activeConversation?.id === id) {
      window.location.hash = '';
    }
  },

  sendMessage: async (content: string, modelId?: string) => {
    const state = get();
    if (!state.activeConversation || state.isStreaming) return;

    const abortController = new AbortController();

    // Optimistic UI — add user message immediately
    const userMessage: Message = {
      id: `temp-${Date.now()}`,
      role: 'user',
      content,
      created_at: new Date().toISOString(),
    };

    set((s) => ({
      messages: [...s.messages, userMessage],
      isStreaming: true,
      streamingContent: '',
      abortController,
    }));

    let fullContent = '';

    try {
      await streamChat(
        state.activeConversation.id,
        content,
        modelId || null,
        (event: ChatEvent) => {
          switch (event.type) {
            case 'token':
              fullContent += event.content || '';
              set({ streamingContent: fullContent });
              break;
            case 'clear':
              // Model outputted text that was actually a tool call — wipe it
              fullContent = '';
              set({ streamingContent: '' });
              break;
            case 'tool_call': {
              const tc: ToolCall = {
                id: `tc-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
                name: event.name || 'unknown',
                params: event.params || '{}',
                status: 'running',
              };
              set((s) => ({
                streamingToolCalls: [...s.streamingToolCalls, tc],
              }));
              break;
            }
            case 'tool_result': {
              set((s) => ({
                streamingToolCalls: s.streamingToolCalls.map((tc) =>
                  tc.name === event.name && tc.status === 'running'
                    ? { ...tc, output: event.output, status: 'done' as const }
                    : tc
                ),
              }));
              break;
            }
            case 'done':
              // Replace streaming content with final message
              const assistantMessage: Message = {
                id: event.message_id || `msg-${Date.now()}`,
                role: 'assistant',
                content: fullContent,
                model_id: modelId || state.activeConversation?.model_id || '',
                created_at: new Date().toISOString(),
              };
              set((s) => ({
                messages: [...s.messages, assistantMessage],
                isStreaming: false,
                streamingContent: '',
                streamingToolCalls: [],
                abortController: null,
              }));
              // Refresh conversation list to update timestamps/titles
              get().loadConversations();
              break;
            case 'error': {
              // Show error as a visible message so the user knows what happened
              const errorMessage: Message = {
                id: `error-${Date.now()}`,
                role: 'assistant',
                content: `⚠️ **Error:** ${event.content || 'Something went wrong. Check that a model is selected and the backend is running.'}`,
                created_at: new Date().toISOString(),
              };
              set((s) => ({
                messages: [...s.messages, errorMessage],
                isStreaming: false,
                streamingContent: '',
                streamingToolCalls: [],
                abortController: null,
              }));
              console.error('Chat error:', event.content);
              break;
            }
          }
        },
        abortController.signal,
      );
    } catch (err) {
      if ((err as Error).name !== 'AbortError') {
        console.error('Stream error:', err);
        // Show connection errors to the user
        const errorMessage: Message = {
          id: `error-${Date.now()}`,
          role: 'assistant',
          content: `⚠️ **Connection error:** ${(err as Error).message || 'Could not reach the server. Is the backend running?'}`,
          created_at: new Date().toISOString(),
        };
        set((s) => ({
          messages: [...s.messages, errorMessage],
          isStreaming: false,
          streamingContent: '',
          abortController: null,
        }));
      } else {
        set({ isStreaming: false, streamingContent: '', abortController: null });
      }
    }
  },

  stopGeneration: () => {
    const { abortController, streamingContent } = get();
    if (abortController) {
      abortController.abort();
    }
    // Keep whatever was streamed so far as the assistant message
    if (streamingContent) {
      const assistantMessage: Message = {
        id: `stopped-${Date.now()}`,
        role: 'assistant',
        content: streamingContent + '\n\n*[Generation stopped]*',
        created_at: new Date().toISOString(),
      };
      set((s) => ({
        messages: [...s.messages, assistantMessage],
        isStreaming: false,
        streamingContent: '',
        abortController: null,
      }));
    } else {
      set({ isStreaming: false, streamingContent: '', abortController: null });
    }
  },

  updateTitle: async (id: string, title: string) => {
    await api.put(`/conversations/${id}`, { title });
    set((s) => ({
      conversations: s.conversations.map((c) =>
        c.id === id ? { ...c, title } : c
      ),
      activeConversation:
        s.activeConversation?.id === id
          ? { ...s.activeConversation, title }
          : s.activeConversation,
    }));
  },
}));
