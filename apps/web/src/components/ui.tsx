"use client";

import type { ReactNode } from "react";

export function Badge({
  children,
  tone = "info",
}: {
  children: ReactNode;
  tone?: "info" | "warn" | "ok" | "muted";
}) {
  return <span className={`badge badge-${tone}`}>{children}</span>;
}

export function Button({
  children,
  onClick,
  disabled,
  variant = "primary",
  type = "button",
  className = "",
}: {
  children: ReactNode;
  onClick?: () => void;
  disabled?: boolean;
  variant?: "primary" | "secondary" | "danger" | "ghost";
  type?: "button" | "submit";
  className?: string;
}) {
  return (
    <button
      type={type}
      className={`btn btn-${variant} ${className}`.trim()}
      onClick={onClick}
      disabled={disabled}
    >
      {children}
    </button>
  );
}

export function Spinner({ label = "处理中…" }: { label?: string }) {
  return (
    <span className="spinner-wrap">
      <span className="spinner" aria-hidden />
      {label}
    </span>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return <div className="empty">{children}</div>;
}

export function Field({
  label,
  children,
  hint,
}: {
  label: string;
  children: ReactNode;
  hint?: string;
}) {
  return (
    <label className="field">
      <span className="field-label">{label}</span>
      {children}
      {hint ? <span className="field-hint">{hint}</span> : null}
    </label>
  );
}

export function StatusDot({
  status,
}: {
  status: "pending" | "running" | "succeeded" | "failed" | string;
}) {
  const map: Record<string, string> = {
    pending: "muted",
    running: "warn",
    succeeded: "ok",
    failed: "danger",
  };
  const tone = map[status] ?? "muted";
  return <span className={`status-dot status-${tone}`} title={status} />;
}
