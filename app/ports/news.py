from __future__ import annotations

from datetime import datetime
from typing import Protocol

from ..domain.news import ApprovedSource, CollectedItem


class NewsProvider(Protocol):
    def collect(self, source: ApprovedSource, since: datetime | None) -> list[CollectedItem]: ...
