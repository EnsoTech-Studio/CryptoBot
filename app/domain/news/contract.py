"""Pure news collection value objects.

Only server-owned :class:`ApprovedSource` values may reach an outbound adapter.
There is deliberately no public-request URL field in the collection command.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class ApprovedSource:
    id: UUID
    source_key: str
    display_name: str
    kind: str
    allowed_origin: str
    url_template: str
    is_active: bool = True


@dataclass(frozen=True)
class CollectedItem:
    source_id: UUID
    canonical_url: str
    url_hash: str
    title: str
    content: str
    content_hash: str
    published_at: datetime
    related_coins: tuple[str, ...] = field(default_factory=tuple)
    extraction_version: str = "rss-v1"
    tagging_version: str = "aliases-v1"
