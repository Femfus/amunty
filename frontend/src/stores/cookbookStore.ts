import { create } from 'zustand';
import { api } from '../utils/api';
import { useToastStore } from './toastStore';

export interface HardwareInfo {
  cpu_name: string;
  cpu_cores: number;
  cpu_threads: number;
  ram_total_gb: number;
  ram_available_gb: number;
  accelerator: string;
  gpu_name: string;
  vram_total_gb: number;
  vram_available_gb: number;
  max_model_params_b: number;
  tier: string;
}

export interface CatalogModel {
  name: string;
  display_name: string;
  description: string;
  parameter_count_b: number;
  quantization: string;
  disk_size_gb: number;
  ram_required_gb: number;
  min_tier: string;
  category: string;
  supports_tools: boolean;
  supports_vision: boolean;
  context_length: number;
  recommended: boolean;
  tags: string[];
  can_run: boolean;
  performance_note: string;
  installed?: boolean;
}

export interface InstalledModel {
  name: string;
  size_gb: number;
  modified_at: string;
}

interface PullProgress {
  status: string;
  percent: number;
  total_bytes: number;
  completed_bytes: number;
}

interface CookbookState {
  hardware: HardwareInfo | null;
  catalog: CatalogModel[];
  installed: InstalledModel[];
  ollamaAvailable: boolean;
  isLoading: boolean;
  pullingModel: string | null;
  pullProgress: PullProgress | null;
  pullError: string | null;

  loadCatalog: () => Promise<void>;
  loadInstalled: () => Promise<void>;
  pullModel: (modelName: string) => Promise<void>;
  deleteModel: (modelName: string) => Promise<void>;
  clearPullError: () => void;
}

export const useCookbookStore = create<CookbookState>((set, get) => ({
  hardware: null,
  catalog: [],
  installed: [],
  ollamaAvailable: false,
  isLoading: false,
  pullingModel: null,
  pullProgress: null,
  pullError: null,

  loadCatalog: async () => {
    set({ isLoading: true });
    try {
      const data = await api.get<{
        hardware: HardwareInfo;
        models: CatalogModel[];
        ollama_available: boolean;
      }>('/cookbook/catalog');
      set({
        hardware: data.hardware,
        catalog: data.models,
        ollamaAvailable: data.ollama_available,
        isLoading: false,
      });
    } catch (err) {
      console.error('Failed to load catalog:', err);
      set({ isLoading: false });
    }
  },

  loadInstalled: async () => {
    try {
      const installed = await api.get<InstalledModel[]>('/cookbook/installed');
      set({ installed });
    } catch (err) {
      console.error('Failed to load installed models:', err);
    }
  },

  pullModel: async (modelName: string) => {
    set({ pullingModel: modelName, pullProgress: null, pullError: null });

    const token = localStorage.getItem('amunty_token');
    const toastId = useToastStore.getState().addToast(`Installing ${modelName}...`, 'loading', 0);

    try {
      const response = await fetch('/api/cookbook/pull', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ model_name: modelName }),
      });

      if (!response.ok) {
        const errBody = await response.json().catch(() => ({ detail: `HTTP ${response.status}` }));
        throw new Error(errBody.detail || `Pull failed: ${response.status}`);
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
            try {
              const event = JSON.parse(trimmed.slice(6));
              set({ pullProgress: event as PullProgress });

              if (event.status === 'error') {
                const errMsg = event.error || 'Download failed. Is Ollama running?';
                set({ pullingModel: null, pullProgress: null, pullError: errMsg });
                useToastStore.getState().updateToast(toastId, {
                  message: `Failed to install ${modelName}: ${errMsg}`,
                  type: 'error',
                });
                // Remove the error toast after a delay
                setTimeout(() => useToastStore.getState().removeToast(toastId), 5000);
                return;
              }

              // Update the toast with actual progress status and percentage
              const percentText = typeof event.percent === 'number' ? ` [${event.percent.toFixed(1)}%]` : '';
              useToastStore.getState().updateToast(toastId, {
                message: `Model installing: ${event.status}${percentText}`,
                progress: event.percent ?? 0,
              });

              if (event.status === 'complete') {
                set({ pullingModel: null, pullProgress: null, pullError: null });
                useToastStore.getState().updateToast(toastId, {
                  message: `Model Finished installing: ${modelName}`,
                  type: 'success',
                });
                // Remove the success toast after a delay
                setTimeout(() => useToastStore.getState().removeToast(toastId), 4000);

                // Refresh catalog and installed list
                await get().loadCatalog();
                await get().loadInstalled();
                // Refresh the global model list so chat model selectors update
                const { useSettingsStore } = await import('./settingsStore');
                await useSettingsStore.getState().loadModels();
              }
            } catch {
              // skip malformed
            }
          }
        }
      }
    } catch (err) {
      const message = (err as Error).message || 'Failed to connect to the server.';
      console.error('Pull error:', err);
      set({
        pullingModel: null,
        pullProgress: null,
        pullError: `Download failed: ${message}`,
      });
      useToastStore.getState().updateToast(toastId, {
        message: `Download failed: ${message}`,
        type: 'error',
      });
      setTimeout(() => useToastStore.getState().removeToast(toastId), 5000);
    }
  },

  deleteModel: async (modelName: string) => {
    try {
      const token = localStorage.getItem('amunty_token');
      const resp = await fetch('/api/cookbook/model', {
        method: 'DELETE',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ model_name: modelName }),
      });
      if (!resp.ok) {
        console.error('Delete failed:', resp.status);
      }
      await get().loadCatalog();
      await get().loadInstalled();
    } catch (err) {
      console.error('Delete error:', err);
    }
  },

  clearPullError: () => {
    set({ pullError: null });
  },
}));
