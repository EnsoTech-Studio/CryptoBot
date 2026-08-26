"use client";

import { useEffect, useId, useRef, type ButtonHTMLAttributes, type ReactNode } from "react";

import { Icon, type IconName } from "./Icon";
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

/* --- shared screen furniture ---------------------------------------------- */

/* Every reference screen frames its content in the same bordered white panel
   with an icon-led title. One component keeps the border, radius and heading
   scale identical across Discovery, Backtest, News and Strategy Engine. */
export function Panel({
  title,
  icon,
  info,
  action,
  className = "",
  bodyClassName = "",
  children,
}: {
  title?: string;
  icon?: IconName;
  info?: string;
  action?: ReactNode;
  className?: string;
  bodyClassName?: string;
  children: ReactNode;
}) {
  return (
    <section className={`${styles.panel} ${className}`}>
      {title ? (
        <header className={styles.panelHead}>
          <h2 className={styles.panelTitle}>
            {icon ? <Icon name={icon} aria-hidden="true" /> : null}
            {title}
            {info ? <InfoHint text={info} /> : null}
          </h2>
          {action}
        </header>
      ) : null}
      <div className={`${styles.panelBody} ${bodyClassName}`}>{children}</div>
    </section>
  );
}

export function InfoHint({ text }: { text: string }) {
  return (
    <span className={styles.infoHint} title={text}>
      <Icon name="info" aria-hidden="true" />
      <span className={styles.srOnly}>{text}</span>
    </span>
  );
}

export function Field({ label, hint, children }: { label: string; hint?: string; children: ReactNode }) {
  return (
    <label className={styles.field}>
      <span className={styles.fieldLabel}>{label}{hint ? <InfoHint text={hint} /> : null}</span>
      {children}
    </label>
  );
}

export function Select({ className = "", ...props }: React.SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <span className={styles.selectShell}>
      <select className={`${styles.control} ${styles.select} ${className}`} {...props} />
      <Icon name="chevron-down" aria-hidden="true" />
    </span>
  );
}

export function TextInput({ className = "", suffix, ...props }: React.InputHTMLAttributes<HTMLInputElement> & { suffix?: string }) {
  return (
    <span className={styles.inputShell}>
      <input className={`${styles.control} ${styles.input} ${className}`} {...props} />
      {suffix ? <em className={styles.inputSuffix}>{suffix}</em> : null}
    </span>
  );
}

/* Range plus a paired numeric input, because plan 03 §7 requires the weight
   editor to be operable and announced without a mouse. */
export function WeightSlider({
  label,
  value,
  onChange,
  disabled = false,
  step = 0.01,
  min = 0,
  max = 1,
}: {
  label: string;
  value: number;
  onChange: (value: number) => void;
  disabled?: boolean;
  step?: number;
  min?: number;
  max?: number;
}) {
  return (
    <span className={styles.weightRow}>
      <input
        type="range"
        className={styles.range}
        aria-label={`Trọng số ${label}`}
        min={min}
        max={max}
        step={step}
        value={value}
        disabled={disabled}
        onChange={(event) => onChange(Number(event.target.value))}
      />
      <input
        type="number"
        className={`${styles.control} ${styles.weightNumber}`}
        aria-label={`Trọng số ${label} dạng số`}
        min={min}
        max={max}
        step={step}
        value={value.toFixed(2)}
        disabled={disabled}
        onChange={(event) => onChange(Number(event.target.value))}
      />
    </span>
  );
}

export function Chip({ label, tone = "brand", onRemove }: { label: string; tone?: "brand" | "amber" | "green" | "violet" | "neutral"; onRemove?: () => void }) {
  return (
    <span className={`${styles.chip} ${styles[`chip${tone[0].toUpperCase()}${tone.slice(1)}`] ?? ""}`}>
      {label}
      {onRemove ? (
        <button type="button" onClick={onRemove} aria-label={`Bỏ ${label}`}>
          <Icon name="close" />
        </button>
      ) : null}
    </span>
  );
}

/* A stage rail (Generate → Backtest → …) appears on three reference screens.
   `current` marks the active step with aria-current="step" per plan 03 §7. */
export function StepFlow({
  steps,
  current,
  variant = "circle",
}: {
  steps: Array<{ icon?: IconName; label: string; detail?: string; badge?: string }>;
  current?: number;
  variant?: "circle" | "numbered";
}) {
  return (
    <ol className={styles.stepFlow} data-variant={variant}>
      {steps.map((step, index) => (
        <li key={step.label} aria-current={current === index ? "step" : undefined}>
          <span className={styles.stepMark}>
            {variant === "numbered" ? index + 1 : step.icon ? <Icon name={step.icon} /> : index + 1}
          </span>
          <strong>{step.label}</strong>
          {step.detail ? <span className={styles.stepDetail}>{step.detail}</span> : null}
          {step.badge ? <em className={styles.stepBadge}>{step.badge}</em> : null}
        </li>
      ))}
    </ol>
  );
}

/* Plan-mandated state for a control the reference shows but no API backs.
   Visually distinct from "empty" so nobody reads it as a bug. */
export function PlannedNotice({ children }: { children: ReactNode }) {
  return (
    <p className={styles.plannedNotice} role="note">
      <Icon name="info" aria-hidden="true" />
      <span>{children}</span>
    </p>
  );
}

export function ProgressBar({ value, max = 100, label }: { value: number; max?: number; label?: string }) {
  const pct = max > 0 ? Math.min(100, Math.max(0, (value / max) * 100)) : 0;
  return (
    <span
      className={styles.progressTrack}
      role="progressbar"
      aria-valuenow={value}
      aria-valuemin={0}
      aria-valuemax={max}
      aria-label={label}
    >
      <span className={styles.progressFill} style={{ width: `${pct}%` }} />
    </span>
  );
}
