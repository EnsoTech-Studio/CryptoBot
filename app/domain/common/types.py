"""Shared value objects and error vocabulary.

Mirrors `server/internal/domain/common/types.go`. The canonical numeric type of
the Python strategy/backtest backend is Python `float` (IEEE 754 double /
float64) — see `blueprint/specs/python-research.md` (rule R1).
"""

from __future__ import annotations

from uuid import UUID

ID = UUID
Decimal = float  # float64 alias — canonical numeric type of this backend

# --- nominal string types (mirror Go `type X string`) ---
Timeframe = str
Action = str
TradeSide = str
RunStatus = str
JobStatus = str
SentimentLabel = str
FillPolicy = str
PositionPolicy = str
OpenPositionPolicy = str
ExitReason = str

# --- Timeframe ---
TIMEFRAME_1M = "1m"
TIMEFRAME_5M = "5m"
TIMEFRAME_15M = "15m"
TIMEFRAME_30M = "30m"
TIMEFRAME_1H = "1h"
TIMEFRAME_2H = "2h"
TIMEFRAME_4H = "4h"
TIMEFRAME_1D = "1d"

# --- Action ---
ACTION_BUY = "BUY"
ACTION_SELL = "SELL"
ACTION_HOLD = "HOLD"

# --- TradeSide ---
TRADE_SIDE_LONG = "LONG"
TRADE_SIDE_SHORT = "SHORT"

# --- RunStatus ---
RUN_QUEUED = "queued"
RUN_RUNNING = "running"
RUN_COMPLETED = "completed"
RUN_FAILED = "failed"
RUN_CANCELLED = "cancelled"

# --- JobStatus ---
JOB_QUEUED = "queued"
JOB_LEASED = "leased"
JOB_COMPLETED = "completed"
JOB_FAILED = "failed"
JOB_CANCELLED = "cancelled"

# --- SentimentLabel ---
SENTIMENT_POSITIVE = "POSITIVE"
SENTIMENT_NEUTRAL = "NEUTRAL"
SENTIMENT_NEGATIVE = "NEGATIVE"

# --- FillPolicy / PositionPolicy / OpenPositionPolicy ---
FILL_POLICY_BBO_LIMIT = "bbo_limit"
POSITION_POLICY_ONE_NET = "one_net_position"
OPEN_POSITION_LAST_EXECUTABLE_BBO = "last_executable_bbo"
OPEN_POSITION_DISCARD = "discard_open_trade"
OPEN_POSITION_MARK_UNREALIZED = "mark_unrealized"

# --- ExitReason ---
EXIT_SIGNAL = "signal"
EXIT_STOP_LOSS = "stop_loss"
EXIT_TAKE_PROFIT = "take_profit"
EXIT_END_OF_SAMPLE = "end_of_sample"


class DomainError(Exception):
    """Domain error carrying a stable, machine-readable code."""

    def __init__(
        self,
        code: str,
        message: str,
        field: str | None = None,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.field = field
        self.cause = cause


ERR_VALIDATION = "validation error"
ERR_UNKNOWN_STRATEGY = "unknown strategy"
ERR_LOOK_AHEAD = "look-ahead access"
ERR_PROVIDER_UNAVAILABLE = "provider unavailable"
ERR_OWNERSHIP = "ownership denied"
ERR_QUOTA = "quota exceeded"
ERR_NOT_IMPLEMENTED = "not implemented"
ERR_LEASE_LOST = "lease lost"

# --- backtest/evaluation error vocabulary (specs/backtest.md, specs/evaluation.md) ---
ERR_INSUFFICIENT_CANDLES = "insufficient_candles"
ERR_DATASET_TOO_LARGE = "dataset_too_large"
ERR_INVALID_BBO_REPLAY = "invalid_bbo_replay"
ERR_MISSING_PRIOR_BBO = "missing_prior_bbo"
ERR_MISSING_FINAL_BBO = "missing_final_bbo"
ERR_INVALID_SIGNAL = "invalid_signal"
ERR_STRATEGY_EXCEPTION = "strategy_exception"
ERR_INCONSISTENT_RESULT = "inconsistent_backtest_result"


class LookAheadError(DomainError):
    """A strategy/context read past the causal cursor (rule R2, specs/python-research.md)."""

    def __init__(self, message: str) -> None:
        super().__init__(ERR_LOOK_AHEAD, message)
