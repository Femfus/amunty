import { useState } from 'react';
import { api, setToken } from '../../utils/api';
import { AmuntyLogo } from '../common/AmuntyLogo';
import styles from './LoginPage.module.css';

interface LoginPageProps {
  onSuccess: () => void;
}

export function LoginPage({ onSuccess }: LoginPageProps) {
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const data = await api.post<{ token: string }>('/auth/login', { password });
      setToken(data.token);
      onSuccess();
    } catch (err) {
      setError((err as Error).message || 'Login failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className={styles.container}>
      <div className={styles.card}>
        <div className={styles.logo}>
          <AmuntyLogo size={40} className={styles.logoIcon} />
          <h1 className={styles.title}>Amunty</h1>
        </div>
        <p className={styles.subtitle}>self-hosted ai workspace</p>

        <form onSubmit={handleSubmit} className={styles.form}>
          <label htmlFor="login-password">Password</label>
          <input
            id="login-password"
            type="password"
            placeholder="Enter admin password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className={styles.input}
            autoFocus
            disabled={loading}
          />
          {error && <p className={styles.error}>⚠ {error}</p>}
          <button
            id="login-submit"
            type="submit"
            className={styles.button}
            disabled={loading || !password}
          >
            {loading ? 'Authenticating...' : 'Sign In'}
          </button>
        </form>

        <p className={styles.hint}>
          Check your server terminal for the admin password on first login.
        </p>
      </div>
    </div>
  );
}
