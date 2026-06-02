import { create } from 'zustand';
import { api } from '../utils/api';

export interface ModelInfo {
  id: string;
  name: string;
  backend: string;
  context_length: number;
  supports_tools: boolean;
  supports_vision: boolean;
}

export interface Backend {
  id: string;
  backend_type: string;
  name: string;
  base_url: string;
  has_api_key: boolean;
  is_enabled: boolean;
  created_at: string;
}

const THEME_PALETTES: Record<string, {
  red: string; fg: string; bg: string; panel: string; border: string;
  logoFilter: string;
}> = {
  dark: {
    red: '#e06c75', fg: '#9cdef2', bg: '#282c34', panel: '#111', border: '#355a66',
    logoFilter: 'invert(57%) sepia(40%) saturate(550%) hue-rotate(302deg) brightness(97%) contrast(92%)',
  },
  midnight: {
    red: '#7b68ee', fg: '#c8d6e5', bg: '#0d1117', panel: '#161b22', border: '#30363d',
    logoFilter: 'invert(40%) sepia(60%) saturate(2200%) hue-rotate(230deg) brightness(100%) contrast(90%)',
  },
  forest: {
    red: '#a8cc8c', fg: '#b0d6a0', bg: '#1a2a1a', panel: '#0f1f0f', border: '#2d4a2d',
    logoFilter: 'invert(78%) sepia(18%) saturate(550%) hue-rotate(68deg) brightness(95%) contrast(88%)',
  },
  ocean: {
    red: '#5fb3f0', fg: '#a8d8ea', bg: '#0a1628', panel: '#0d1f35', border: '#1a3a5c',
    logoFilter: 'invert(62%) sepia(50%) saturate(600%) hue-rotate(178deg) brightness(102%) contrast(92%)',
  },
  retro: {
    red: '#ff6b35', fg: '#ffd700', bg: '#1a1a2e', panel: '#16213e', border: '#0f3460',
    logoFilter: 'invert(48%) sepia(85%) saturate(1800%) hue-rotate(2deg) brightness(103%) contrast(105%)',
  },
  light: {
    red: '#d63031', fg: '#2d3436', bg: '#f5f5f5', panel: '#ffffff', border: '#bbb',
    logoFilter: 'invert(22%) sepia(85%) saturate(3000%) hue-rotate(348deg) brightness(88%) contrast(95%)',
  },
};

interface SettingsState {
  models: ModelInfo[];
  backends: Backend[];
  settings: Record<string, string>;
  isLoading: boolean;

  loadModels: () => Promise<void>;
  loadBackends: () => Promise<void>;
  loadSettings: () => Promise<void>;
  updateSettings: (patch: Record<string, string>) => Promise<void>;
  addBackend: (config: {
    backend_type: string;
    name: string;
    base_url: string;
    api_key?: string;
  }) => Promise<void>;
  deleteBackend: (id: string) => Promise<void>;
  testBackend: (id: string) => Promise<boolean>;
  autoDiscoverOllama: () => Promise<{ discovered: number; registered: string[] }>;
  applyTheme: (theme: string) => void;
  availableThemes: () => string[];
}

export const useSettingsStore = create<SettingsState>((set, get) => ({
  models: [],
  backends: [],
  settings: {},
  isLoading: false,

  loadModels: async () => {
    try {
      const models = await api.get<ModelInfo[]>('/models');
      set({ models });
    } catch (err) {
      console.error('Failed to load models:', err);
    }
  },

  loadBackends: async () => {
    try {
      const backends = await api.get<Backend[]>('/models/backends');
      set({ backends });
    } catch (err) {
      console.error('Failed to load backends:', err);
    }
  },

  loadSettings: async () => {
    try {
      const data = await api.get<{ settings: Record<string, string> }>('/settings');
      set({ settings: data.settings });
      get().applyTheme(data.settings['theme'] || 'dark', data.settings);
    } catch (err) {
      console.error('Failed to load settings:', err);
    }
  },

  updateSettings: async (patch: Record<string, string>) => {
    const data = await api.put<{ settings: Record<string, string> }>('/settings', {
      settings: patch,
    });
    set({ settings: data.settings });
    get().applyTheme(data.settings['theme'] || 'dark', data.settings);
  },

  addBackend: async (config) => {
    await api.post('/models/backends', config);
    await get().loadBackends();
    await get().loadModels();
  },

  deleteBackend: async (id: string) => {
    await api.delete(`/models/backends/${id}`);
    await get().loadBackends();
    await get().loadModels();
  },

  testBackend: async (id: string) => {
    const result = await api.post<{ healthy: boolean }>(`/models/backends/${id}/test`);
    return result.healthy;
  },

  autoDiscoverOllama: async () => {
    try {
      const result = await api.post<{ discovered: number; registered: string[] }>(
        '/models/auto-discover',
        {}
      );
      if (result.registered.length > 0) {
        await get().loadModels();
        await get().loadBackends();
      }
      return result;
    } catch {
      return { discovered: 0, registered: [] };
    }
  },

  applyTheme: (theme: string, currentSettings?: Record<string, string>) => {
    const palette = THEME_PALETTES[theme] || THEME_PALETTES['dark']!;
    const root = document.documentElement;
    
    // Read from provided settings or fallback to store state
    const s = currentSettings || get().settings;
    
    root.style.setProperty('--red', s['customAccent'] || palette.red);
    root.style.setProperty('--fg', s['customFg'] || palette.fg);
    root.style.setProperty('--bg', s['customBg'] || palette.bg);
    root.style.setProperty('--panel', s['customPanel'] || palette.panel);
    root.style.setProperty('--border', s['customBorder'] || palette.border);
    root.style.setProperty('--brand-color', s['customAccent'] || palette.red);
    root.style.setProperty('--logo-filter', palette.logoFilter);
  },

  availableThemes: () => Object.keys(THEME_PALETTES),
}));

