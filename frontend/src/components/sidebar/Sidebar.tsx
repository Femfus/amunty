import { useState } from 'react';
import { useChatStore } from '../../stores/chatStore';
import { useSettingsStore } from '../../stores/settingsStore';
import { CookbookPanel } from '../cookbook/CookbookPanel';
import { SettingsPanel } from '../settings/SettingsPanel';
import { ChatsPanel } from '../chat/ChatsPanel';
import { AmuntyLogo } from '../common/AmuntyLogo';
import styles from './Sidebar.module.css';

export function Sidebar() {
  const [showCookbook, setShowCookbook] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [showChats, setShowChats] = useState(false);
  const [isCollapsed, setIsCollapsed] = useState(false);
  
  const createConversation = useChatStore((s) => s.createConversation);
  const isMobileOpen = useChatStore((s) => s.isMobileSidebarOpen);
  const setMobileOpen = useChatStore((s) => s.setMobileSidebarOpen);
  const settings = useSettingsStore((s) => s.settings);
  const models = useSettingsStore((s) => s.models);

  const handleNewChat = async () => {
    const defaultModel = settings['default_model'] || models[0]?.id || '';
    if (!defaultModel) {
      alert('Please configure a model backend in Settings first.');
      return;
    }
    await createConversation(defaultModel);
  };

  return (
    <>
      {isMobileOpen && (
        <div className={styles.mobileBackdrop} onClick={() => setMobileOpen(false)} />
      )}
      <aside className={`${styles.sidebar} ${isCollapsed ? styles.collapsed : ''} ${isMobileOpen ? styles.mobileOpen : ''}`} id="sidebar">
        <div className={styles.header}>
          <button className={styles.hamburgerBtn} onClick={() => setIsCollapsed(!isCollapsed)}>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="18" x2="21" y2="18"/></svg>
          </button>
          <div className={styles.brand}>
            <AmuntyLogo size={48} className={styles.brandIcon} />
          </div>
        </div>

        <div className={styles.navRail} onClick={() => setMobileOpen(false)}>
          <button className={`${styles.navItem} ${styles.desktopOnly}`}>
            <svg className={styles.navIcon} width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
            <span className={styles.navLabel}>Search</span>
          </button>
          <button className={styles.navItem} onClick={handleNewChat}>
            <svg className={styles.navIcon} width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
            <span className={styles.navLabel}>New</span>
          </button>
          <button className={styles.navItem} onClick={() => setShowChats(true)}>
            <svg className={styles.navIcon} width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
            <span className={styles.navLabel}>Chats</span>
            <svg className={styles.desktopOnly} width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" opacity="0.5"><polyline points="9 18 15 12 9 6"/></svg>
          </button>
          <button className={`${styles.navItem} ${styles.active}`} onClick={() => setShowCookbook(true)}>
            <svg className={styles.navIcon} width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg>
            <span className={styles.navLabel}>Cookbook</span>
            <span className={`${styles.dot} ${styles.desktopOnly}`}>done</span>
          </button>
          <button className={`${styles.navItem} ${styles.desktopOnly}`} onClick={() => setShowSettings(true)}>
            <svg className={styles.navIcon} width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 2.69l5.66 4.2c.38.28.61.73.61 1.2v7.82c0 .47-.23.92-.61 1.2L12 21.31l-5.66-4.2a1.5 1.5 0 0 1-.61-1.2V8.09c0-.47.23-.92.61-1.2L12 2.69z"/><circle cx="12" cy="12" r="3"/></svg>
            <span className={styles.navLabel}>Theme</span>
          </button>
          <button className={`${styles.navItem} ${styles.mobileOnly}`} onClick={() => setShowSettings(true)}>
            <svg className={styles.navIcon} width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>
            <span className={styles.navLabel}>Settings</span>
          </button>
        </div>

        <div className={styles.footer}>
          <button className={styles.settingsBtn} onClick={() => setShowSettings(true)}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>
          </button>
        </div>
      </aside>

      {showCookbook && <CookbookPanel onClose={() => setShowCookbook(false)} />}
      {showSettings && <SettingsPanel onClose={() => setShowSettings(false)} />}
      {showChats && <ChatsPanel onClose={() => setShowChats(false)} />}
    </>
  );
}
