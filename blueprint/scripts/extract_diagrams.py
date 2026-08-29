"""Trích mermaid source từ Markdown ra blueprint/assets/diagrams/*.mmd.

Bộ sơ đồ thống nhất có hai nguồn gốc (xem `diagrams/index.json`):

- ``origin: doc`` — mermaid nhúng trong ``design.md`` / ``specs/*.md`` là nguồn
  sự thật; script trích ra ``.mmd``. Chỉ những slug này được trích lại.
- ``origin: target`` — sơ đồ kiến trúc đích (gộp từ bộ target cũ); file ``.mmd``
  CHÍNH LÀ nguồn sự thật và script không được ghi đè lên nó. Chúng chỉ thay đổi
  khi tài liệu narrative tương ứng được cập nhật mermaid trước.

Chạy lại script này sau khi sửa mermaid trong design.md hoặc specs/, rồi render
lại SVG/PNG — xem blueprint/assets/README.md.

    py blueprint/scripts/extract_diagrams.py
"""

import json
import pathlib
import re

root = pathlib.Path(__file__).resolve().parent.parent
index_path = root / "assets" / "diagrams" / "index.json"
out = root / "assets" / "diagrams"

# (file, mermaid block index within file 0-based, slug) — chỉ cho origin: doc
WANT = [
    ("design.md", 8, "09-realtime-reconnect-backfill-flow"),
    ("design.md", 9, "10-strategy-flow"),
]

BLOCK = re.compile(r"```mermaid\n(.*?)```", re.S)

index = json.loads(index_path.read_text(encoding="utf-8"))
by_slug = {e["slug"]: e for e in index}

for fname, idx, slug in WANT:
    src = root / fname
    blocks = BLOCK.findall(src.read_text(encoding="utf-8"))
    if idx >= len(blocks):
        print(f"SKIP {slug}: {fname} has only {len(blocks)} blocks")
        continue
    (out / f"{slug}.mmd").write_text(blocks[idx].rstrip() + "\n", encoding="utf-8")
    by_slug[slug]["source"] = fname
    by_slug[slug]["block_index"] = idx
    print(f"extracted {slug} from {fname}#{idx}")

index_path.write_text(json.dumps(index, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print(f"index.json: {len(index)} diagrams, {sum(1 for e in index if e['origin'] == 'doc')} doc-extracted")
