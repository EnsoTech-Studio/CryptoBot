/* Three visually distinct states, because collapsing them is exactly what
   PRODUCT.md principle 1 forbids:
     - Skeleton     work is in flight; shape mirrors the eventual content.
     - EmptyState   the request succeeded but there is nothing yet.
     - Unavailable  a dependency is down. Per ADR-013 we never fake data, so
                    this must look different from "empty", not like a bug.  */

export function Skeleton({ lines = 3 }: { lines?: number }) {
  return (
    <div className="skeleton-block" aria-hidden="true">
      {Array.from({ length: lines }).map((_, index) => (
        <span key={index} className="skeleton-line" />
      ))}
    </div>
  );
}

export function ChartSkeleton({ size }: { size: "primary" | "context" }) {
  return (
    <div className={`chart-skeleton ${size}`} role="status" aria-label="Loading market data">
      <span className="skeleton-shimmer" />
    </div>
  );
}

export function TableSkeleton({ rows = 5, cols = 5 }: { rows?: number; cols?: number }) {
  return (
    <div className="table-skeleton" role="status" aria-label="Loading table">
      {Array.from({ length: rows }).map((_, r) => (
        <div key={r} className="table-skeleton-row">
          {Array.from({ length: cols }).map((_, c) => (
            <span key={c} className="skeleton-line" />
          ))}
        </div>
      ))}
    </div>
  );
}

export function EmptyState({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="empty-state">
      <span>{title}</span>
      <p>{children}</p>
    </div>
  );
}

export function Unavailable({ title = "Service unavailable", children }: { title?: string; children: React.ReactNode }) {
  return (
    <div className="unavailable-state" role="status">
      <span>{title}</span>
      <p>{children}</p>
    </div>
  );
}

export function ErrorState({ title = "Không thể hoàn tất", children }: { title?: string; children: React.ReactNode }) {
  return (
    <div className="error-state" role="alert">
      <span>{title}</span>
      <p>{children}</p>
    </div>
  );
}
