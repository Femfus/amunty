import { useEffect, useState } from 'react';
import { useSettingsStore } from '../../stores/settingsStore';
import styles from './SettingsPanel.module.css';

interface SettingsPanelProps {
  onClose: () => void;
}

/** Color swatches for theme preview cards */
const THEME_SWATCHES: Record<string, { bg: string; panel: string; accent: string }> = {
  dark:     { bg: '#282c34', panel: '#111',    accent: '#e06c75' },
  midnight: { bg: '#0d1117', panel: '#161b22', accent: '#7b68ee' },
  forest:   { bg: '#1a2a1a', panel: '#0f1f0f', accent: '#a8cc8c' },
  ocean:    { bg: '#0a1628', panel: '#0d1f35', accent: '#5fb3f0' },
  retro:    { bg: '#1a1a2e', panel: '#16213e', accent: '#ff6b35' },
  light:    { bg: '#f5f5f5', panel: '#ffffff', accent: '#d63031' },
};

const PERMISSION_KEYS = [
  { key: 'allow_web_search', name: 'Web Search',         desc: 'Allow the AI to search the web for information' },
  { key: 'allow_file_read',  name: 'File Access',        desc: 'Allow reading files from the server workspace' },
  { key: 'allow_shell',      name: 'Shell Commands',     desc: 'Allow executing shell commands on the server' },
  { key: 'allow_memory',     name: 'Memory',             desc: 'Persist context and facts across conversations' },
] as const;

export function SettingsPanel({ onClose }: SettingsPanelProps) {
  const settings = useSettingsStore((s) => s.settings);
  const models = useSettingsStore((s) => s.models);
  const updateSettings = useSettingsStore((s) => s.updateSettings);
  const applyTheme = useSettingsStore((s) => s.applyTheme);
  const availableThemes = useSettingsStore((s) => s.availableThemes);
  const loadSettings = useSettingsStore((s) => s.loadSettings);

  // Local draft state (mirrors server settings)
  const [draft, setDraft] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [dirty, setDirty] = useState(false);

  useEffect(() => {
    loadSettings();
  }, [loadSettings]);

  // Sync draft whenever settings load
  useEffect(() => {
    setDraft({ ...settings });
  }, [settings]);

  const themes = availableThemes();

  /** Update a single key in the draft & mark dirty */
  const set = (key: string, value: string) => {
    setDraft((prev) => ({ ...prev, [key]: value }));
    setDirty(true);
    setSaved(false);
  };

  /** Live-preview theme changes */
  const handleThemeSelect = (theme: string) => {
    set('theme', theme);
    // clear custom overrides when selecting a preset theme
    set('customBg', '');
    set('customPanel', '');
    set('customFg', '');
    set('customBorder', '');
    set('customAccent', '');
    
    // instant preview
    applyTheme(theme, { ...draft, theme, customBg: '', customPanel: '', customFg: '', customBorder: '', customAccent: '' });
  };
  
  const handleCustomColor = (key: string, value: string) => {
    set(key, value);
    applyTheme(currentTheme, { ...draft, [key]: value });
  };

  /** Persist all changed settings to the backend */
  const handleSave = async () => {
    setSaving(true);
    try {
      // Only send keys that actually changed
      const patch: Record<string, string> = {};
      for (const [k, v] of Object.entries(draft)) {
        if (v !== settings[k]) {
          patch[k] = v;
        }
      }
      if (Object.keys(patch).length > 0) {
        await updateSettings(patch);
      }
      setSaved(true);
      setDirty(false);
      setTimeout(() => setSaved(false), 2000);
    } catch (err) {
      console.error('Failed to save settings:', err);
    } finally {
      setSaving(false);
    }
  };

  /** Handle escape key */
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  const currentTheme = draft['theme'] || 'dark';
  const currentModel = draft['default_model'] || '';

  return (
    <div className={styles.overlay} onClick={onClose}>
      <div className={styles.panel} onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <header className={styles.header}>
          <div className={styles.headerLeft}>
            <svg className={styles.headerIcon} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="3" />
              <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
            </svg>
            <h2 className={styles.title}>Settings</h2>
          </div>
          <button className={styles.closeBtn} onClick={onClose} id="close-settings" title="Close">
            ✕
          </button>
        </header>

        {/* Body */}
        <div className={styles.body}>
          {/* ── Network Info ── */}
          <div className={styles.section}>
            <div className={styles.sectionHeader}>
              <span className={styles.sectionIcon}>🌐</span>
              <h3 className={styles.sectionTitle}>Network Access</h3>
            </div>
            <div className={styles.networkBox}>
              <p style={{ margin: '0 0 8px', fontSize: '0.9rem', color: 'color-mix(in srgb, var(--fg) 80%, transparent)' }}>
                Connect other devices on your Wi-Fi using this address:
              </p>
              <div className={styles.ipAddress}>
                http://{settings['local_ip'] || '...'}:5173
              </div>
            </div>
          </div>

          {/* ── Theme ── */}
          <div className={styles.section}>
            <div className={styles.sectionHeader}>
              <span className={styles.sectionIcon}>🎨</span>
              <h3 className={styles.sectionTitle}>Appearance</h3>
            </div>

            <div className={styles.themeGrid}>
              {themes.map((theme) => {
                const sw = THEME_SWATCHES[theme] ?? { bg: '#282c34', panel: '#111', accent: '#e06c75' };
                return (
                  <button
                    key={theme}
                    id={`theme-${theme}`}
                    className={`${styles.themeCard} ${currentTheme === theme ? styles.active : ''}`}
                    onClick={() => handleThemeSelect(theme)}
                    type="button"
                  >
                    <div className={styles.themePreview}>
                      <div className={styles.themeColor} style={{ background: sw.bg }} />
                      <div className={styles.themeColor} style={{ background: sw.panel }} />
                      <div className={styles.themeColor} style={{ background: sw.accent }} />
                    </div>
                    <span className={styles.themeName}>{theme}</span>
                  </button>
                );
              })}
            </div>

            <div className={styles.settingRow} style={{ marginTop: '16px' }}>
              <div className={styles.settingLabel}>
                <span className={styles.settingName}>Background Effect</span>
                <span className={styles.settingDesc}>Dynamic background canvas</span>
              </div>
              <select
                className={styles.select}
                value={draft['bgPattern'] || 'snow'}
                onChange={(e) => set('bgPattern', e.target.value)}
              >
                <option value="none">None</option>
                <option value="snow">Snow</option>
                <option value="synapse">Synapse</option>
                <option value="dots">Dots</option>
                <option value="rain">Rain</option>
              </select>
            </div>

            <div style={{ marginTop: '16px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
              <h4 style={{ fontSize: '0.85rem', color: 'var(--fg)', opacity: 0.8 }}>Custom Colors</h4>
              <div className={styles.settingRow}>
                <label style={{ fontSize: '0.85rem' }}>Background</label>
                <input type="color" value={draft['customBg'] || THEME_SWATCHES[currentTheme]?.bg || '#282c34'} onChange={(e) => handleCustomColor('customBg', e.target.value)} />
              </div>
              <div className={styles.settingRow}>
                <label style={{ fontSize: '0.85rem' }}>Panel</label>
                <input type="color" value={draft['customPanel'] || THEME_SWATCHES[currentTheme]?.panel || '#111'} onChange={(e) => handleCustomColor('customPanel', e.target.value)} />
              </div>
              <div className={styles.settingRow}>
                <label style={{ fontSize: '0.85rem' }}>Text</label>
                <input type="color" value={draft['customFg'] || '#9cdef2'} onChange={(e) => handleCustomColor('customFg', e.target.value)} />
              </div>
              <div className={styles.settingRow}>
                <label style={{ fontSize: '0.85rem' }}>Border</label>
                <input type="color" value={draft['customBorder'] || '#355a66'} onChange={(e) => handleCustomColor('customBorder', e.target.value)} />
              </div>
              <div className={styles.settingRow}>
                <label style={{ fontSize: '0.85rem' }}>Accent</label>
                <input type="color" value={draft['customAccent'] || THEME_SWATCHES[currentTheme]?.accent || '#e06c75'} onChange={(e) => handleCustomColor('customAccent', e.target.value)} />
              </div>
            </div>
          </div>

          {/* ── Default Model ── */}
          <div className={styles.section}>
            <div className={styles.sectionHeader}>
              <span className={styles.sectionIcon}>🤖</span>
              <h3 className={styles.sectionTitle}>Default Model</h3>
            </div>

            <div className={styles.settingRow}>
              <div className={styles.settingLabel}>
                <span className={styles.settingName}>Model</span>
                <span className={styles.settingDesc}>
                  Used for new conversations. {models.length === 0 ? 'No models available — add a backend first.' : `${models.length} model${models.length !== 1 ? 's' : ''} available.`}
                </span>
              </div>
              <select
                id="default-model-select"
                className={styles.select}
                value={currentModel}
                onChange={(e) => set('default_model', e.target.value)}
                disabled={models.length === 0}
              >
                <option value="">— Select a model —</option>
                {models.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.name} ({m.backend})
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* ── Permissions ── */}
          <div className={styles.section}>
            <div className={styles.sectionHeader}>
              <span className={styles.sectionIcon}>🔒</span>
              <h3 className={styles.sectionTitle}>Permissions</h3>
            </div>

            {PERMISSION_KEYS.map(({ key, name, desc }) => (
              <div key={key} className={styles.settingRow}>
                <div className={styles.settingLabel}>
                  <span className={styles.settingName}>{name}</span>
                  <span className={styles.settingDesc}>{desc}</span>
                </div>
                <label className={styles.toggle}>
                  <input
                    id={`perm-${key}`}
                    type="checkbox"
                    checked={draft[key] === 'true'}
                    onChange={(e) => set(key, e.target.checked ? 'true' : 'false')}
                  />
                  <span className={styles.toggleSlider} />
                </label>
              </div>
            ))}
          </div>

          {/* ── System Prompt ── */}
          <div className={styles.section}>
            <div className={styles.sectionHeader}>
              <span className={styles.sectionIcon}>💬</span>
              <h3 className={styles.sectionTitle}>System Prompt</h3>
            </div>

            <div className={styles.textareaWrapper}>
              <textarea
                id="system-prompt-textarea"
                className={styles.textarea}
                value={draft['system_prompt'] || ''}
                onChange={(e) => set('system_prompt', e.target.value)}
                placeholder="You are a helpful AI assistant..."
                rows={4}
              />
            </div>
          </div>
        </div>

        {/* Footer */}
        <footer className={styles.footer}>
          <span className={styles.version}>Amunty v0.1.0</span>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            {saved && <span className={styles.savedToast}>✓ Saved</span>}
            <button
              id="save-settings-btn"
              className={`${styles.saveBtn} ${saved ? styles.saved : ''}`}
              onClick={handleSave}
              disabled={saving || !dirty}
            >
              {saving ? 'Saving...' : saved ? 'Saved ✓' : 'Save Changes'}
            </button>
          </div>
        </footer>
      </div>
    </div>
  );
}
