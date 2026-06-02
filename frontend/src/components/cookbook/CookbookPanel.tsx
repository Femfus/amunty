import { useEffect, useState } from 'react';
import { useCookbookStore, type CatalogModel } from '../../stores/cookbookStore';
import styles from './CookbookPanel.module.css';

interface CookbookPanelProps {
  onClose: () => void;
}

const TIER_LABELS: Record<string, string> = {
  minimal: '🔋 Minimal',
  low: '💡 Low',
  mid: '⚙️ Mid',
  high: '🚀 High',
  ultra: '🔥 Ultra',
};

const CATEGORY_ICONS: Record<string, string> = {
  installed: '✅',
  general: '💬',
  coding: '💻',
  vision: '👁️',
  reasoning: '🧠',
  small: '🪶',
};

const CATEGORY_FILTERS = ['all', 'installed', 'general', 'coding', 'vision', 'reasoning', 'small'] as const;

export function CookbookPanel({ onClose }: CookbookPanelProps) {
  const {
    hardware,
    catalog,
    ollamaAvailable,
    isLoading,
    pullingModel,
    pullProgress,
    pullError,
    loadCatalog,
    pullModel,
    deleteModel,
    clearPullError,
  } = useCookbookStore();

  const [categoryFilter, setCategoryFilter] = useState<string>('all');
  const [showOnlyRunnable, setShowOnlyRunnable] = useState(true);

  useEffect(() => {
    loadCatalog();
  }, [loadCatalog]);

  const installedCount = catalog.filter((m) => m.installed).length;

  const filteredModels = catalog
    .filter((m) => {
      if (categoryFilter === 'installed') return m.installed;
      if (categoryFilter !== 'all' && m.category !== categoryFilter) return false;
      if (showOnlyRunnable && !m.can_run) return false;
      return true;
    })
    .sort((a, b) => {
      // Installed models always come first
      if (a.installed && !b.installed) return -1;
      if (!a.installed && b.installed) return 1;
      return 0;
    });

  return (
    <div className={styles.overlay} onClick={onClose}>
      <div className={styles.panel} onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <header className={styles.header}>
          <div>
            <h2 className={styles.title}>📚 Model Cookbook</h2>
            <p className={styles.subtitle}>
              Find and download AI models matched to your hardware
              {installedCount > 0 && (
                <span style={{ marginLeft: '6px', color: 'var(--green, #a8cc8c)' }}>
                  — {installedCount} installed
                </span>
              )}
            </p>
          </div>
          <button className={styles.closeBtn} onClick={onClose} id="close-cookbook">
            ✕
          </button>
        </header>

        {isLoading ? (
          <div className={styles.loading}>
            <div className={styles.spinner} />
            <p>Detecting hardware...</p>
          </div>
        ) : (
          <>
            {/* Hardware Profile Card */}
            {hardware && (
              <div className={styles.hardwareCard}>
                <div className={styles.hardwareHeader}>
                  <h3>Your Hardware</h3>
                  <span className={styles.tierBadge} data-tier={hardware.tier}>
                    {TIER_LABELS[hardware.tier] || hardware.tier}
                  </span>
                </div>
                <div className={styles.hardwareGrid}>
                  <div className={styles.hardwareStat}>
                    <span className={styles.statLabel}>CPU</span>
                    <span className={styles.statValue}>
                      {hardware.cpu_name} ({hardware.cpu_cores} cores)
                    </span>
                  </div>
                  <div className={styles.hardwareStat}>
                    <span className={styles.statLabel}>RAM</span>
                    <span className={styles.statValue}>
                      {hardware.ram_available_gb} / {hardware.ram_total_gb} GB
                    </span>
                  </div>
                  {hardware.gpu_name && (
                    <div className={styles.hardwareStat}>
                      <span className={styles.statLabel}>GPU</span>
                      <span className={styles.statValue}>{hardware.gpu_name}</span>
                    </div>
                  )}
                  {hardware.vram_total_gb > 0 && (
                    <div className={styles.hardwareStat}>
                      <span className={styles.statLabel}>VRAM</span>
                      <span className={styles.statValue}>
                        {hardware.vram_available_gb} / {hardware.vram_total_gb} GB
                      </span>
                    </div>
                  )}
                  <div className={styles.hardwareStat}>
                    <span className={styles.statLabel}>Max Model</span>
                    <span className={styles.statValue}>
                      ~{hardware.max_model_params_b}B parameters
                    </span>
                  </div>
                </div>
              </div>
            )}

            {/* Ollama Status */}
            {!ollamaAvailable && (
              <div className={styles.warning}>
                ⚠️ Ollama is not reachable. Install it from{' '}
                <a href="https://ollama.com" target="_blank" rel="noreferrer">
                  ollama.com
                </a>{' '}
                and start it to download models.
              </div>
            )}

            {/* Filters */}
            <div className={styles.filters}>
              <div className={styles.categoryTabs}>
                {CATEGORY_FILTERS.map((cat) => (
                  <button
                    key={cat}
                    className={`${styles.categoryTab} ${
                      categoryFilter === cat ? styles.activeTab : ''
                    }`}
                    onClick={() => setCategoryFilter(cat)}
                  >
                    {cat === 'all' ? '🌐 All' : `${CATEGORY_ICONS[cat] || ''} ${cat}`}
                  </button>
                ))}
              </div>
              <label className={styles.filterToggle}>
                <input
                  type="checkbox"
                  checked={showOnlyRunnable}
                  onChange={(e) => setShowOnlyRunnable(e.target.checked)}
                />
                Only show models my hardware can run
              </label>
            </div>

            {/* Pull Error */}
            {pullError && (
              <div className={styles.warning} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '8px' }}>
                <span>❌ {pullError}</span>
                <button
                  onClick={clearPullError}
                  style={{ background: 'none', border: 'none', color: 'inherit', cursor: 'pointer', fontSize: '1rem', padding: '0 4px', opacity: 0.7 }}
                  title="Dismiss"
                >
                  ✕
                </button>
              </div>
            )}

            {/* Model List */}
            <div className={styles.modelList}>
              {filteredModels.length === 0 && (
                <p className={styles.noModels}>
                  No models match your filters. Try unchecking "Only show runnable" to see all.
                </p>
              )}

              {filteredModels.map((model) => (
                <ModelCard
                  key={model.name}
                  model={model}
                  isPulling={pullingModel === model.name}
                  pullProgress={pullingModel === model.name ? pullProgress : null}
                  ollamaAvailable={ollamaAvailable}
                  onPull={() => pullModel(model.name)}
                  onDelete={() => deleteModel(model.name)}
                />
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  );
}


function ModelCard({
  model,
  isPulling,
  pullProgress,
  ollamaAvailable,
  onPull,
  onDelete,
}: {
  model: CatalogModel;
  isPulling: boolean;
  pullProgress: { status: string; percent: number } | null;
  ollamaAvailable: boolean;
  onPull: () => void;
  onDelete: () => void;
}) {
  return (
    <div
      className={`${styles.modelCard} ${!model.can_run ? styles.cantRun : ''}`}
      id={`model-${model.name.replace(/[:/]/g, '-')}`}
    >
      <div className={styles.modelHeader}>
        <div className={styles.modelNameRow}>
          <h4 className={styles.modelName}>
            {CATEGORY_ICONS[model.category] || '🤖'} {model.display_name}
          </h4>
          {model.recommended && <span className={styles.recommendedBadge}>★ Recommended</span>}
        </div>
        <p className={styles.modelDesc}>{model.description}</p>
      </div>

      <div className={styles.modelMeta}>
        <span className={styles.metaChip}>{model.parameter_count_b}B</span>
        <span className={styles.metaChip}>{model.quantization}</span>
        <span className={styles.metaChip}>📦 {model.disk_size_gb} GB</span>
        <span className={styles.metaChip}>🧠 {model.ram_required_gb} GB RAM</span>
        {model.supports_tools && <span className={styles.metaChip}>🔧 Tools</span>}
        {model.supports_vision && <span className={styles.metaChip}>👁️ Vision</span>}
        <span className={styles.metaChip}>📏 {(model.context_length / 1024).toFixed(0)}K ctx</span>
      </div>

      <div className={styles.modelPerformance}>
        <span>{model.performance_note}</span>
      </div>

      {model.tags.length > 0 && (
        <div className={styles.tagList}>
          {model.tags.map((tag) => (
            <span key={tag} className={styles.tag}>
              {tag}
            </span>
          ))}
        </div>
      )}

      <div className={styles.modelActions}>
        {isPulling ? (
          <div className={styles.pullProgress}>
            <div
              className={styles.progressBar}
              style={{ width: `${pullProgress?.percent ?? 0}%` }}
            />
            <span className={styles.progressText}>
              {pullProgress?.status || 'Starting...'} ({pullProgress?.percent?.toFixed(1) ?? 0}%)
            </span>
          </div>
        ) : model.installed ? (
          <>
            <span className={styles.installedBadge}>✅ Installed</span>
            <button className={styles.deleteBtn} onClick={onDelete}>
              Remove
            </button>
          </>
        ) : (
          <button
            className={styles.pullBtn}
            onClick={onPull}
            disabled={!ollamaAvailable || !model.can_run}
          >
            ⬇️ Download ({model.disk_size_gb} GB)
          </button>
        )}
      </div>
    </div>
  );
}
