import { useEffect } from 'react';
import { useSettingsStore } from '../../stores/settingsStore';
import { Snow } from './Snow';
import { Synapse } from './Synapse';
import { Rain } from './Rain';

export function BackgroundManager() {
  const settings = useSettingsStore((s) => s.settings);
  const pattern = settings['bgPattern'] || 'snow';

  useEffect(() => {
    // Remove previous patterns
    document.body.classList.remove('bg-pattern-dots', 'bg-pattern-synapse', 'bg-pattern-rain');
    
    // Add current pattern class if it relies on CSS (like dots/synapse grid)
    if (pattern !== 'none') {
      document.body.classList.add(`bg-pattern-${pattern}`);
    }
  }, [pattern]);

  switch (pattern) {
    case 'synapse':
      return <Synapse />;
    case 'snow':
      return <Snow />;
    case 'rain':
      return <Rain />;
    case 'none':
    case 'dots':
    default:
      return null;
  }
}
