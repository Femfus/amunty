import { useCallback, useEffect, useRef, useState } from 'react';
import styles from './SkillsPanel.module.css';

/* ── Types ── */

interface Skill {
  id: string;
  name: string;
  description: string;
  emoji: string;
  triggers: string[];
  tool_name: string;
  tool_args: Record<string, any>;
  enabled: boolean;
  source: 'built-in' | 'user' | 'learned';
  created_at: string;
}

interface SkillsPanelProps {
  onClose: () => void;
}

/* ── Constants ── */

const AVAILABLE_TOOLS = [
  'get_current_time',
  'set_reminder',
  'show_notification',
  'open_application',
  'open_url',
  'get_system_info',
  'list_directory',
  'read_file',
  'search_files',
  'get_clipboard',
  'set_clipboard',
  'run_command',
  'get_running_processes',
  'get_weather',
] as const;

const EMPTY_FORM = {
  name: '',
  description: '',
  emoji: '⚡',
  triggers: '',
  tool_name: '' as string,
  tool_args: '',
};

/* ── Component ── */

export function SkillsPanel({ onClose }: SkillsPanelProps) {
  const [skills, setSkills] = useState<Skill[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);
  const [submitting, setSubmitting] = useState(false);
  const searchRef = useRef<HTMLInputElement>(null);

  /* ── Fetch skills ── */
  const fetchSkills = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch('/api/skills');
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data: Skill[] = await res.json();
      setSkills(data);
    } catch (err) {
      console.error('Failed to fetch skills:', err);
      setError('Failed to load skills.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchSkills();
  }, [fetchSkills]);

  /* ── Escape key ── */
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  /* ── Toggle skill ── */
  const toggleSkill = async (skill: Skill) => {
    const next = !skill.enabled;
    // Optimistic update
    setSkills((prev) =>
      prev.map((s) => (s.id === skill.id ? { ...s, enabled: next } : s)),
    );
    try {
      const res = await fetch(`/api/skills/${skill.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled: next }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
    } catch (err) {
      console.error('Failed to toggle skill:', err);
      // Revert on failure
      setSkills((prev) =>
        prev.map((s) => (s.id === skill.id ? { ...s, enabled: !next } : s)),
      );
    }
  };

  /* ── Delete skill ── */
  const deleteSkill = async (id: string) => {
    const prev = skills;
    setSkills((s) => s.filter((sk) => sk.id !== id));
    try {
      const res = await fetch(`/api/skills/${id}`, { method: 'DELETE' });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
    } catch (err) {
      console.error('Failed to delete skill:', err);
      setSkills(prev);
    }
  };

  /* ── Add skill ── */
  const handleSubmit = async () => {
    if (!form.name.trim() || !form.tool_name) return;
    setSubmitting(true);
    try {
      let parsedArgs: Record<string, any> = {};
      if (form.tool_args.trim()) {
        try {
          parsedArgs = JSON.parse(form.tool_args);
        } catch {
          parsedArgs = {};
        }
      }

      const body = {
        name: form.name.trim(),
        description: form.description.trim(),
        emoji: form.emoji.trim() || '⚡',
        triggers: form.triggers
          .split(',')
          .map((t) => t.trim())
          .filter(Boolean),
        tool_name: form.tool_name,
        tool_args: parsedArgs,
      };

      const res = await fetch('/api/skills', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);

      const created: Skill = await res.json();
      setSkills((prev) => [created, ...prev]);
      setForm(EMPTY_FORM);
      setShowForm(false);
    } catch (err) {
      console.error('Failed to create skill:', err);
    } finally {
      setSubmitting(false);
    }
  };

  /* ── Filter skills ── */
  const filtered = skills.filter((s) => {
    if (!search.trim()) return true;
    const q = search.toLowerCase();
    return (
      s.name.toLowerCase().includes(q) ||
      s.description.toLowerCase().includes(q) ||
      s.triggers.some((t) => t.toLowerCase().includes(q)) ||
      s.tool_name.toLowerCase().includes(q)
    );
  });

  const enabledCount = skills.filter((s) => s.enabled).length;

  return (
    <div className={styles.overlay} onClick={onClose}>
      <div className={styles.panel} onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <header className={styles.header}>
          <div className={styles.headerLeft}>
            <span className={styles.headerIcon}>🧠</span>
            <h2 className={styles.title}>Skills</h2>
          </div>
          <div className={styles.headerActions}>
            <button className={styles.closeBtn} onClick={onClose} title="Close">
              ✕
            </button>
          </div>
        </header>

        {/* Toolbar */}
        <div className={styles.toolbar}>
          <div className={styles.searchWrapper}>
            <svg
              className={styles.searchIcon}
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <circle cx="11" cy="11" r="8" />
              <line x1="21" y1="21" x2="16.65" y2="16.65" />
            </svg>
            <input
              ref={searchRef}
              className={styles.searchInput}
              type="text"
              placeholder="Search skills..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
          <button
            className={styles.addBtn}
            onClick={() => setShowForm((v) => !v)}
          >
            <span className={styles.addBtnIcon}>{showForm ? '✕' : '+'}</span>
            {showForm ? 'Cancel' : 'Add Skill'}
          </button>
        </div>

        {/* Body */}
        <div className={styles.body}>
          {/* Add Skill Form */}
          {showForm && (
            <div className={styles.addForm}>
              <div className={styles.addFormTitle}>
                <span>✨</span> New Skill
              </div>
              <div className={styles.formGrid}>
                <div className={styles.formGroup}>
                  <label className={styles.formLabel}>Emoji</label>
                  <input
                    className={styles.formInput}
                    type="text"
                    value={form.emoji}
                    onChange={(e) =>
                      setForm((f) => ({ ...f, emoji: e.target.value }))
                    }
                    placeholder="⚡"
                    maxLength={4}
                  />
                </div>
                <div className={styles.formGroup}>
                  <label className={styles.formLabel}>Name</label>
                  <input
                    className={styles.formInput}
                    type="text"
                    value={form.name}
                    onChange={(e) =>
                      setForm((f) => ({ ...f, name: e.target.value }))
                    }
                    placeholder="My Skill"
                  />
                </div>
                <div className={styles.formGroupFull}>
                  <label className={styles.formLabel}>Description</label>
                  <textarea
                    className={styles.formTextarea}
                    value={form.description}
                    onChange={(e) =>
                      setForm((f) => ({ ...f, description: e.target.value }))
                    }
                    placeholder="What does this skill do?"
                    rows={2}
                  />
                </div>
                <div className={styles.formGroupFull}>
                  <label className={styles.formLabel}>
                    Trigger Phrases (comma separated)
                  </label>
                  <input
                    className={styles.formInput}
                    type="text"
                    value={form.triggers}
                    onChange={(e) =>
                      setForm((f) => ({ ...f, triggers: e.target.value }))
                    }
                    placeholder="what time, current time, clock"
                  />
                </div>
                <div className={styles.formGroup}>
                  <label className={styles.formLabel}>Tool</label>
                  <select
                    className={styles.formSelect}
                    value={form.tool_name}
                    onChange={(e) =>
                      setForm((f) => ({ ...f, tool_name: e.target.value }))
                    }
                  >
                    <option value="">— Select a tool —</option>
                    {AVAILABLE_TOOLS.map((t) => (
                      <option key={t} value={t}>
                        {t}
                      </option>
                    ))}
                  </select>
                </div>
                <div className={styles.formGroup}>
                  <label className={styles.formLabel}>Tool Args (JSON)</label>
                  <input
                    className={styles.formInput}
                    type="text"
                    value={form.tool_args}
                    onChange={(e) =>
                      setForm((f) => ({ ...f, tool_args: e.target.value }))
                    }
                    placeholder='{"key": "value"}'
                  />
                </div>
                <div className={styles.formActions}>
                  <button
                    className={styles.formCancelBtn}
                    onClick={() => {
                      setForm(EMPTY_FORM);
                      setShowForm(false);
                    }}
                    type="button"
                  >
                    Cancel
                  </button>
                  <button
                    className={styles.formSubmitBtn}
                    onClick={handleSubmit}
                    disabled={submitting || !form.name.trim() || !form.tool_name}
                    type="button"
                  >
                    {submitting ? 'Creating...' : 'Create Skill'}
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* Loading */}
          {loading && (
            <div className={styles.loading}>
              <div className={styles.loadingDots}>
                <div className={styles.loadingDot} />
                <div className={styles.loadingDot} />
                <div className={styles.loadingDot} />
              </div>
              <span className={styles.loadingText}>Loading skills…</span>
            </div>
          )}

          {/* Error */}
          {!loading && error && (
            <div className={styles.error}>
              <span className={styles.errorIcon}>⚠️</span>
              <span className={styles.errorText}>{error}</span>
              <button className={styles.retryBtn} onClick={fetchSkills}>
                Retry
              </button>
            </div>
          )}

          {/* Empty */}
          {!loading && !error && filtered.length === 0 && (
            <div className={styles.emptyState}>
              <span className={styles.emptyIcon}>
                {search ? '🔍' : '🧩'}
              </span>
              <span className={styles.emptyTitle}>
                {search ? 'No skills match your search' : 'No skills yet'}
              </span>
              <span className={styles.emptyDesc}>
                {search
                  ? 'Try a different search term.'
                  : 'Click "Add Skill" to create your first skill.'}
              </span>
            </div>
          )}

          {/* Skills Grid */}
          {!loading && !error && filtered.length > 0 && (
            <div className={styles.skillsGrid}>
              {filtered.map((skill) => (
                <div
                  key={skill.id}
                  className={`${styles.skillCard} ${
                    !skill.enabled ? styles.disabled : ''
                  }`}
                >
                  <div className={styles.cardHeader}>
                    <div className={styles.cardIdentity}>
                      <div className={styles.cardEmoji}>{skill.emoji}</div>
                      <div className={styles.cardNameRow}>
                        <span className={styles.cardName}>{skill.name}</span>
                        <span className={styles.cardBadge}>
                          {skill.source === 'built-in' && (
                            <>
                              <span>🔒</span> Built-in
                            </>
                          )}
                          {skill.source === 'learned' && (
                            <>
                              <span>🎓</span> Learned
                            </>
                          )}
                          {skill.source === 'user' && (
                            <>
                              <span>👤</span> Custom
                            </>
                          )}
                        </span>
                      </div>
                    </div>
                    <div className={styles.cardControls}>
                      {skill.source !== 'built-in' && (
                        <button
                          className={styles.deleteBtn}
                          onClick={() => deleteSkill(skill.id)}
                          title="Delete skill"
                        >
                          🗑️
                        </button>
                      )}
                      <label className={styles.toggle}>
                        <input
                          type="checkbox"
                          checked={skill.enabled}
                          onChange={() => toggleSkill(skill)}
                        />
                        <span className={styles.toggleSlider} />
                      </label>
                    </div>
                  </div>

                  <p className={styles.cardDesc}>{skill.description}</p>

                  <div className={styles.cardTool}>
                    tool:{' '}
                    <span className={styles.cardToolName}>
                      {skill.tool_name}
                    </span>
                  </div>

                  {skill.triggers.length > 0 && (
                    <div className={styles.cardTriggers}>
                      {skill.triggers.map((trigger) => (
                        <span key={trigger} className={styles.triggerTag}>
                          {trigger}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Footer */}
        <footer className={styles.footer}>
          <span className={styles.footerCount}>
            <strong>{enabledCount}</strong> of {skills.length} skills active
          </span>
        </footer>
      </div>
    </div>
  );
}
