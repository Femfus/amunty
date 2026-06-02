import { useEffect, useState } from 'react';
import { LoginPage } from './components/auth/LoginPage';
import { Sidebar } from './components/sidebar/Sidebar';
import { ChatPanel } from './components/chat/ChatPanel';
import { BackgroundManager } from './components/effects/BackgroundManager';
import { ToastContainer } from './components/common/ToastContainer';
import { useChatStore } from './stores/chatStore';
import { useSettingsStore } from './stores/settingsStore';

export function App() {
  const [loggedIn, setLoggedIn] = useState(true);
  const loadConversations = useChatStore((s) => s.loadConversations);
  const loadModels = useSettingsStore((s) => s.loadModels);
  const loadBackends = useSettingsStore((s) => s.loadBackends);
  const loadSettings = useSettingsStore((s) => s.loadSettings);

  useEffect(() => {
    if (loggedIn) {
      loadConversations();
      loadModels();
      loadBackends();
      loadSettings();

      const hash = window.location.hash;
      if (hash && hash.startsWith('#/chat/')) {
        const chatId = hash.replace('#/chat/', '');
        useChatStore.getState().selectConversation(chatId);
      }
    }
  }, [loggedIn]);

  useEffect(() => {
    const loader = document.getElementById('app-loader');
    if (loader) {
      loader.style.opacity = '0';
      setTimeout(() => loader.remove(), 300);
    }
    
    // Fallback for phones with very high CSS pixel densities
    if (/Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent)) {
      document.body.classList.add('is-mobile');
    }
  }, []);

  if (!loggedIn) {
    return (
      <>
        <BackgroundManager />
        <LoginPage onSuccess={() => setLoggedIn(true)} />
      </>
    );
  }

  return (
    <div style={{ display: 'flex', height: '100dvh', width: '100vw', position: 'relative' }}>
      <BackgroundManager />
      <ToastContainer />
      <Sidebar />
      <ChatPanel />
    </div>
  );
}

