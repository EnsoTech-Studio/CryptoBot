"""Persistence seams for the moved domain. Mirrors `server/internal/ports/persistence.go` subset."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from ..domain.backtest import EquityPoint, ExperimentSnapshot, Result, TradeFact
from ..domain.evaluation import Evaluation
from ..domain.ranking import LeaderboardEntry
from ..domain.search import SearchRun


class DatasetReader(Protocol):
    def load_dataset_candles(self, dataset_id: UUID) -> list: ...


class ExperimentRepository(Protocol):
    def create_snapshot(self, snapshot: ExperimentSnapshot) -> None: ...

    def get_snapshot(self, experiment_id: UUID) -> ExperimentSnapshot: ...


class RunRepository(Protocol):
    def persist_result(self, run_id: UUID, result: Result) -> None: ...

    def owns_run(self, run_id: UUID, owner_id: UUID) -> bool: ...


class SearchRunRepository(Protocol):
    def create(self, run: SearchRun) -> None: ...

    def get(self, run_id: UUID) -> SearchRun: ...

    def apply_action(self, run_id: UUID, action: str, operator_id: UUID) -> None: ...


class TradeReader(Protocol):
    def list_trades(self, run_id: UUID, limit: int, offset: int) -> list[TradeFact]: ...


class EquityReader(Protocol):
    def list_equity(self, run_id: UUID, max_points: int) -> list[EquityPoint]: ...


class EvaluationReader(Protocol):
    def get_evaluation(self, run_id: UUID, version: str) -> Evaluation: ...


class LeaderboardRepository(Protocol):
    def list(self, timeframe: str, symbol: str, top_k: int) -> list[LeaderboardEntry]: ...

    def insert(self, entry: LeaderboardEntry) -> None: ...
