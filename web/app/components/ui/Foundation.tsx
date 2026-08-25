"use client";

import { useEffect, useId, useRef, type ButtonHTMLAttributes, type ReactNode } from "react";

import { Icon } from "./Icon";
import styles from "./foundation.module.css";

type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";

export function Button({ variant = "secondary", className = "", ...props }: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: ButtonVariant }) {
  const variants: Record<ButtonVariant, string> = {
    primary: styles.buttonPrimary,
    secondary: styles.buttonSecondary,
    ghost: styles.buttonGhost,
    danger: styles.buttonDanger,
  };
  return <button className={`${styles.button} ${variants[variant]} ${className}`} {...props} />;
}

export function SegmentedControl<T extends string>({
  label,
  options,
  value,
  onChange,
}: {
  label: string;
  options: Array<{ label: string; value: T }>;
  value: T;
  onChange: (value: T) => void;
}) {
  return (
    <div className={styles.segmented} role="group" aria-label={label}>
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          className={`${styles.segment} ${value === option.value ? styles.segmentActive : ""}`}
          aria-pressed={value === option.value}
          onClick={() => onChange(option.value)}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}

export function Toggle({ checked, label, onChange }: { checked: boolean; label: string; onChange: (checked: boolean) => void }) {
  return (
    <button
      type="button"
      className={`${styles.toggle} ${checked ? styles.toggleOn : ""}`}
      role="switch"
      aria-checked={checked}
      onClick={() => onChange(!checked)}
    >
      <span className={styles.toggleTrack} aria-hidden="true"><span className={styles.toggleThumb} /></span>
      <span>{label}</span>
    </button>
  );
}

export type StatusTone = "live" | "syncing" | "error" | "neutral";

export function StatusDot({ tone = "neutral" }: { tone?: StatusTone }) {
  const toneClass = tone === "live" ? styles.statusLive : tone === "syncing" ? styles.statusSyncing : tone === "error" ? styles.statusError : "";
  return <span className={`${styles.statusDot} ${toneClass}`} aria-hidden="true" />;
}

export function StatusMessage({ children, tone = "neutral" }: { children: ReactNode; tone?: StatusTone }) {
  const toneClass = tone === "error" ? styles.statusMessageError : tone === "syncing" ? styles.statusMessageWarn : "";
  return (
    <div className={`${styles.statusMessage} ${toneClass}`} role="status" aria-live="polite">
      <StatusDot tone={tone} />
      <span>{children}</span>
    </div>
  );
}

export function Dialog({ open, title, children, onClose }: { open: boolean; title: string; children: ReactNode; onClose: () => void }) {
  const titleId = useId();
  const dialogRef = useRef<HTMLElement>(null);

  useEffect(() => {
    if (!open) return;
    const focusFrame = window.requestAnimationFrame(() => dialogRef.current?.focus());
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", closeOnEscape);
    return () => {
      window.cancelAnimationFrame(focusFrame);
      window.removeEventListener("keydown", closeOnEscape);
    };
  }, [onClose, open]);

  if (!open) return null;
  return (
    <div className={styles.dialogBackdrop} role="presentation" onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
      <section ref={dialogRef} className={styles.dialog} role="dialog" aria-modal="true" aria-labelledby={titleId} tabIndex={-1}>
        <div className={styles.dialogHead}>
          <h2 id={titleId}>{title}</h2>
          <button type="button" className={styles.dialogClose} onClick={onClose} aria-label="Đóng hộp thoại">
            <Icon name="close" />
          </button>
        </div>
        {children}
      </section>
    </div>
  );
}
