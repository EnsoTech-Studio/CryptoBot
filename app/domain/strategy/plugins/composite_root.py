from __future__ import annotations

from ...common import ACTION_HOLD
from ..contract import AnalysisContext, Definition, Signal


class CompositeRoot:
    def definition(self) -> Definition:
        return Definition(
            strategy_id="composite",
            version="v1",
            family=None,
            parameters_schema={"type": "object"},
            input_requirements=[],
            overlay_types=["composite_signal"],
            warm_up_candles=lambda _params: 0,
            is_composite=True,
            display_name="Composite Strategy",
            description="Virtual provenance root; execution resolves immutable child definitions.",
        )

    def analyze(self, _context: AnalysisContext) -> Signal:
        return Signal(action=ACTION_HOLD)

