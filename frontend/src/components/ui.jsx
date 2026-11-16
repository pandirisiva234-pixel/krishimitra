// Small reusable building blocks used across pages.
import { useEffect, useState } from "react";
import { Loader2 } from "lucide-react";
import { assistant } from "../api/endpoints";

export function Spinner({ label = "Loading…", size = 20 }) {
  return (
    <span className="spinner" role="status">
      <Loader2 size={size} className="spin" aria-hidden />
      <span>{label}</span>
    </span>
  );
}

export function PageLoader({ label }) {
  return (
    <div className="page-loader">
      <Spinner label={label} size={28} />
    </div>
  );
}

export function PageHeader({ title, subtitle, actions }) {
  return (
    <header className="page-header">
      <div>
        <h1>{title}</h1>
        {subtitle && <p className="muted">{subtitle}</p>}
      </div>
      {actions && <div className="page-actions">{actions}</div>}
    </header>
  );
}

export function Card({ title, icon: Icon, actions, children, className = "" }) {
  return (
    <section className={`card ${className}`}>
      {(title || actions) && (
        <div className="card-head">
          <h2>
            {Icon && <Icon size={18} aria-hidden />} {title}
          </h2>
          {actions}
        </div>
      )}
      {children}
    </section>
  );
}

export function StatCard({ label, value, hint, icon: Icon, tone = "green" }) {
  return (
    <div className={`stat stat-${tone}`}>
      {Icon && (
        <span className="stat-icon">
          <Icon size={20} aria-hidden />
        </span>
      )}
      <div>
        <div className="stat-value">{value ?? "—"}</div>
        <div className="stat-label">{label}</div>
        {hint && <div className="stat-hint">{hint}</div>}
      </div>
    </div>
  );
}

export function EmptyState({ icon: Icon, title, children }) {
  return (
    <div className="empty">
      {Icon && <Icon size={32} aria-hidden />}
      <p className="empty-title">{title}</p>
      {children && <div className="muted">{children}</div>}
    </div>
  );
}

export function ErrorBanner({ message, onRetry }) {
  if (!message) return null;
  return (
    <div className="banner banner-error" role="alert">
      <span>{message}</span>
      {onRetry && (
        <button className="btn btn-small" onClick={onRetry}>
          Retry
        </button>
      )}
    </div>
  );
}

export function ConfidenceBar({ value }) {
  const pctValue = Math.round((value || 0) * 100);
  const tone = pctValue >= 80 ? "high" : pctValue >= 60 ? "mid" : "low";
  return (
    <div className="confidence" aria-label={`Confidence ${pctValue}%`}>
      <div className={`confidence-fill confidence-${tone}`} style={{ width: `${pctValue}%` }} />
      <span>{pctValue}%</span>
    </div>
  );
}

/** Media files need the auth header, so they are fetched as blobs and shown via object URLs. */
function useAuthBlob(url) {
  const [src, setSrc] = useState(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    if (!url) return undefined;
    let objectUrl;
    let alive = true;
    assistant
      .fetchBlob(url)
      .then((blob) => {
        objectUrl = URL.createObjectURL(blob);
        if (alive) setSrc(objectUrl);
      })
      .catch(() => alive && setFailed(true));
    return () => {
      alive = false;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [url]);
  return { src, failed };
}

export function AuthAudio({ url, autoPlay = false }) {
  const { src, failed } = useAuthBlob(url);
  if (failed) return <span className="muted small">Audio unavailable</span>;
  if (!src) return <Spinner label="Preparing audio…" size={16} />;
  return <audio controls autoPlay={autoPlay} src={src} className="audio" />;
}

export function AuthImage({ url, alt, className }) {
  const { src, failed } = useAuthBlob(url);
  if (failed) return <div className={`img-placeholder ${className || ""}`}>Image unavailable</div>;
  if (!src) return <div className={`img-placeholder ${className || ""}`} />;
  return <img src={src} alt={alt} className={className} />;
}

export function Field({ label, error, hint, children, htmlFor }) {
  return (
    <div className={`field ${error ? "field-error" : ""}`}>
      <label htmlFor={htmlFor}>{label}</label>
      {children}
      {error ? <span className="field-msg">{error}</span> : hint && <span className="field-hint">{hint}</span>}
    </div>
  );
}
