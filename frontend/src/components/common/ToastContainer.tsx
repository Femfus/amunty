import { useToastStore, type Toast } from '../../stores/toastStore';
import styles from './ToastContainer.module.css';

export function ToastContainer() {
  const toasts = useToastStore((s) => s.toasts);

  if (toasts.length === 0) return null;

  return (
    <div className={styles.container}>
      {toasts.map((toast) => (
        <ToastItem key={toast.id} toast={toast} />
      ))}
    </div>
  );
}

function ToastItem({ toast }: { toast: Toast }) {
  const removeToast = useToastStore((s) => s.removeToast);

  const getIcon = () => {
    switch (toast.type) {
      case 'success':
        return '✅';
      case 'error':
        return '❌';
      case 'loading':
        return '⏳';
      default:
        return 'ℹ️';
    }
  };

  return (
    <div className={`${styles.toast} ${styles[toast.type]}`} id={`toast-${toast.id}`}>
      <div className={styles.content}>
        <span className={styles.icon}>{getIcon()}</span>
        <div className={styles.body}>
          <p className={styles.message}>{toast.message}</p>
          {toast.type === 'loading' && typeof toast.progress === 'number' && (
            <div className={styles.progressContainer}>
              <div
                className={styles.progressBar}
                style={{ width: `${toast.progress}%` }}
              />
            </div>
          )}
        </div>
        <button className={styles.closeBtn} onClick={() => removeToast(toast.id)}>
          ✕
        </button>
      </div>
    </div>
  );
}
