"""Trích mermaid source từ Markdown ra blueprint/assets/diagrams/*.mmd.

Markdown là nguồn sự thật; .mmd là bản trích. Chạy lại script này sau khi sửa
mermaid trong design.md hoặc specs/, rồi render lại SVG/PNG — xem
blueprint/assets/README.md.

    py blueprint/scripts/extract_diagrams.py
"""

import json
import pathlib
import re

root = pathlib.Path(__file__).resolve().parent.parent
out = root / "assets" / "diagrams"
out.mkdir(parents=True, exist_ok=True)

# (file, mermaid block index within file 0-based, slug)
WANT = [
    ("design.md", 0, "01-c4-l1-system-context"),
    ("design.md", 1, "02-c4-l2-container"),
    ("design.md", 2, "03-c4-l3-component-strategy-lab"),
    ("design.md", 3, "04-high-level-architecture"),
    ("design.md", 4, "05-candle-path-binance-to-pixel"),
    ("design.md", 5, "06-erd"),
    ("design.md", 6, "07-outbox-scenarios"),
    ("design.md", 7, "08-outbox-event-state"),
    ("design.md", 8, "09-realtime-reconnect-backfill-flow"),
    ("design.md", 9, "10-strategy-flow"),
    ("design.md", 10, "11-search-backtest-flow"),
    ("design.md", 11, "12-search-run-state"),
    ("design.md", 12, "13-news-sentiment-flow"),
    ("design.md", 13, "14-defense-in-depth"),
    ("design.md", 14, "15-job-queue-scale"),
    ("specs/experiment.md", 0, "16-experiment-create-transaction"),
    ("specs/experiment.md", 1, "17-experiment-worker-execution"),
    ("specs/experiment.md", 2, "18-experiment-lease-takeover"),
    ("specs/experiment.md", 3, "19-backtest-run-state"),
]

BLOCK = re.compile(r"```mermaid\n(.*?)```", re.S)

manifest = []
for fname, idx, slug in WANT:
    src = root / fname
    blocks = BLOCK.findall(src.read_text(encoding="utf-8"))
    if idx >= len(blocks):
        print(f"SKIP {slug}: {fname} has only {len(blocks)} blocks")
        continue
    (out / f"{slug}.mmd").write_text(blocks[idx].rstrip() + "\n", encoding="utf-8")
    manifest.append({"slug": slug, "source": fname, "block_index": idx})

(out / "index.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"extracted {len(manifest)} diagrams to {out}")
