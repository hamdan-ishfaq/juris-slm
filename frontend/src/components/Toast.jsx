export default function Toast({ message, type = 'error', onClose }) {
  if (!message) return null
  return (
    <div className={`toast toast-${type}`} role="alert">
      <span>{message}</span>
      <button type="button" className="toast-close" onClick={onClose} aria-label="Dismiss">×</button>
    </div>
  )
}
