import type { ReactNode } from "react";
import type { RingStatus, RiskLevel } from "../api";
import { attributeLabel, LEVEL_LABELS, score } from "../format";

export function RiskBadge({ level, risk }: { level: RiskLevel; risk?: number }) {
  const icon = level === "high" ? "▲" : level === "medium" ? "◆" : "●";
  return (
    <span className={`badge risk-${level}`} title={`${LEVEL_LABELS[level]} risk`}>
      <span aria-hidden="true">{icon}</span>
      {LEVEL_LABELS[level]}
      {risk !== undefined && <span className="num">· {score(risk)}</span>}
    </span>
  );
}

export function StatusBadge({ status }: { status: RingStatus }) {
  const text = status === "confirmed" ? "Confirmed fraud" : status === "dismissed" ? "Dismissed" : "Awaiting review";
  const icon = status === "confirmed" ? "✕" : status === "dismissed" ? "✓" : "○";
  return (
    <span className={`badge ${status}`}>
      <span aria-hidden="true">{icon}</span>
      {text}
    </span>
  );
}

export function AnalystBadge({ label }: { label: number | null | undefined }) {
  if (label === null || label === undefined) return null;
  return label === 1 ? (
    <span className="badge confirmed" title="Analyst decision">
      <span aria-hidden="true">✕</span> Analyst: fraud
    </span>
  ) : (
    <span className="badge dismissed" title="Analyst decision">
      <span aria-hidden="true">✓</span> Analyst: legitimate
    </span>
  );
}

export function TruthBadge({ label }: { label: number | null | undefined }) {
  if (label === null || label === undefined) return <span className="muted">–</span>;
  return <span className="badge neutral">{label === 1 ? "Fraud" : "Legit"}</span>;
}

export function AttrChip({ type, value, title }: { type: string; value: string; title?: string }) {
  return (
    <span className="attr" title={title ?? `${attributeLabel(type)}: ${value}`}>
      <span className="kind">{attributeLabel(type)}</span>
      <span className="val">{value}</span>
    </span>
  );
}

export function Loading({ text = "Loading…" }: { text?: string }) {
  return (
    <div className="loading" role="status">
      <span className="spinner" /> {text}
    </div>
  );
}

export function ErrorBox({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="notice error" role="alert">
      <span aria-hidden="true">⚠</span>
      <div style={{ flex: 1 }}>{message}</div>
      {onRetry && (
        <button className="btn small" onClick={onRetry}>
          Retry
        </button>
      )}
    </div>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return <div className="empty">{children}</div>;
}

export function Stat({ label, value, sub, hero }: { label: string; value: ReactNode; sub?: ReactNode; hero?: boolean }) {
  return (
    <div className={`stat${hero ? " hero" : ""}`}>
      <span className="label">{label}</span>
      <span className="value">{value}</span>
      {sub && <span className="sub">{sub}</span>}
    </div>
  );
}

/** Horizontal meter: the score against the alert threshold. */
export function ScoreMeter({ risk, threshold, level }: { risk: number; threshold: number; level: RiskLevel }) {
  return (
    <div className="stack tight">
      <div className="meter" role="img" aria-label={`Score ${score(risk)} of 100; alert threshold ${score(threshold)}`}>
        <span style={{ width: `${Math.max(2, risk * 100)}%`, background: `var(--risk-${level})` }} />
        <span className="threshold" style={{ left: `calc(${threshold * 100}% - 1px)` }} title="Alert threshold" />
      </div>
      <div className="row between small muted">
        <span>0</span>
        <span>Alert threshold {score(threshold)}</span>
        <span>100</span>
      </div>
    </div>
  );
}

export function PageHead({ title, subtitle, actions }: { title: ReactNode; subtitle?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="page-head">
      <div className="titles">
        <h1>{title}</h1>
        {subtitle && <p>{subtitle}</p>}
      </div>
      {actions && <div className="toolbar">{actions}</div>}
    </div>
  );
}

export function Segmented<T extends string>({
  value,
  options,
  onChange,
  label,
}: {
  value: T;
  options: { value: T; label: ReactNode }[];
  onChange: (value: T) => void;
  label: string;
}) {
  return (
    <div className="segmented" role="group" aria-label={label}>
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          className={option.value === value ? "on" : ""}
          aria-pressed={option.value === value}
          onClick={() => onChange(option.value)}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}
