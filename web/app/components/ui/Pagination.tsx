"use client";

import { Icon } from "./Icon";
import styles from "./pagination.module.css";

export function Pagination({
  page,
  totalPages,
  onPage,
  ariaLabel,
}: {
  page: number;
  totalPages: number;
  onPage: (page: number) => void;
  ariaLabel: string;
}) {
  if (totalPages <= 1) return null;
  const currentPage = Math.min(Math.max(page, 1), totalPages);

  return (
    <nav className={styles.pager} aria-label={ariaLabel}>
      <button type="button" disabled={currentPage <= 1} onClick={() => onPage(currentPage - 1)} aria-label="Trang trước">
        <Icon name="chevron-left" />
      </button>
      {pageWindow(currentPage, totalPages).map((item, index) =>
        item === null ? (
          <span key={`gap-${index}`} className={styles.pageGap} aria-hidden="true">…</span>
        ) : (
          <button
            key={item}
            type="button"
            className={item === currentPage ? styles.pageActive : ""}
            aria-current={item === currentPage ? "page" : undefined}
            onClick={() => onPage(item)}
          >
            {item}
          </button>
        ),
      )}
      <button type="button" disabled={currentPage >= totalPages} onClick={() => onPage(currentPage + 1)} aria-label="Trang sau">
        <Icon name="chevron-right" />
      </button>
    </nav>
  );
}

function pageWindow(page: number, totalPages: number): Array<number | null> {
  if (totalPages <= 5) return Array.from({ length: totalPages }, (_, index) => index + 1);
  const values = new Set([1, 2, 3, page, totalPages]);
  const sorted = [...values].filter((value) => value >= 1 && value <= totalPages).sort((left, right) => left - right);
  const output: Array<number | null> = [];
  sorted.forEach((value, index) => {
    if (index > 0 && value - sorted[index - 1] > 1) output.push(null);
    output.push(value);
  });
  return output;
}
