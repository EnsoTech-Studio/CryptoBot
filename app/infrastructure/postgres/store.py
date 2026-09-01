"""PostgreSQL repositories for the research HTTP application."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from ...domain.common import hash_canonical_json
from ...domain.news import ApprovedSource, CollectedItem
from ...domain.sentiment import Result as SentimentResult
from ...errors import conflict, not_found, validation
from ..news.security import canonical_url, sha256_text
from ...schemas import (
    ExperimentCreateIn,
    ScorePolicyCreateIn,
    SearchActionIn,
    SearchRunCreateIn,
    StrategyApprovalIn,
    StrategyDraftCreateIn,
)
from ...services.search import generate_candidates


def _float(value: Any) -> float | None:
    return None if value is None else float(value)


def _as_float_fields(row: dict[str, Any], fields: Iterable[str]) -> dict[str, Any]:
    for field in fields:
        if field in row:
            row[field] = _float(row[field])
    return row


class Store:
    """Short-transaction repository.

    A connection is opened per operation so sync FastAPI handlers can run in
    separate worker threads without sharing transaction state.
    """

    def __init__(self, conninfo: str) -> None:
        if not conninfo.strip():
            raise ValueError("database connection string is required")
        self._conninfo = conninfo

    def _connect(self) -> psycopg.Connection[dict[str, Any]]:
        return psycopg.connect(self._conninfo, connect_timeout=3, row_factory=dict_row)

    def ready(self) -> dict[str, bool]:
        with self._connect() as connection:
            connection.execute("SELECT 1").fetchone()
            active = connection.execute(
                "SELECT count(*) AS count FROM score_policies WHERE is_active"
            ).fetchone()
        return {"database": True, "active_score_policy": active["count"] == 1}

    def operational_metrics(self) -> dict[str, float]:
        """Return bounded queue/search/outbox gauges for the internal metrics route."""
        metrics: dict[str, float] = {}
        with self._connect() as connection:
            for row in connection.execute(
                "SELECT status::text AS status,count(*) AS count FROM backtest_jobs GROUP BY status"
            ).fetchall():
                metrics[f"research_jobs_{row['status']}"] = float(row["count"])
            queue_age = connection.execute(
                """
                SELECT COALESCE(extract(epoch FROM now()-min(enqueued_at)),0) AS age
                FROM backtest_jobs WHERE status='queued'
                """
            ).fetchone()
            metrics["research_queue_oldest_seconds"] = float(queue_age["age"])
            for row in connection.execute(
                "SELECT status,count(*) AS count FROM search_runs GROUP BY status"
            ).fetchall():
                metrics[f"research_search_runs_{row['status']}"] = float(row["count"])
            for row in connection.execute(
                """
                SELECT dispatch_status::text AS status,count(*) AS count
                FROM domain_events GROUP BY dispatch_status
                """
            ).fetchall():
                metrics[f"research_outbox_{row['status']}"] = float(row["count"])
            outbox_age = connection.execute(
                """
                SELECT COALESCE(extract(epoch FROM now()-min(occurred_at)),0) AS age
                FROM domain_events WHERE dispatch_status IN ('pending','claimed')
                """
            ).fetchone()
            metrics["research_outbox_oldest_seconds"] = float(outbox_age["age"])
            coverage = connection.execute(
                """
                SELECT count(*) AS total,
                       count(*) FILTER (WHERE EXISTS (
                           SELECT 1 FROM sentiment_results result
                           WHERE result.news_item_id=item.id
                       )) AS analyzed
                FROM news_items item
                """
            ).fetchone()
            total = float(coverage["total"])
            metrics["research_sentiment_coverage_ratio"] = (
                float(coverage["analyzed"]) / total if total else 0.0
            )
        return metrics

    def sync_strategies(self, definitions: list[dict[str, Any]]) -> None:
        with self._connect() as connection:
            for item in definitions:
                connection.execute(
                    """
                    INSERT INTO strategy_definitions(
                        strategy_id, display_name, family, description, is_composite
                    ) VALUES (%s,%s,%s,%s,%s)
                    ON CONFLICT(strategy_id) DO UPDATE SET
                        display_name = EXCLUDED.display_name,
                        description = EXCLUDED.description
                    """,
                    (
                        item["strategy_id"],
                        item["display_name"],
                        item["family"],
                        item["description"],
                        item["is_composite"],
                    ),
                )
                existing = connection.execute(
                    """
                    SELECT code_fingerprint FROM strategy_versions
                    WHERE strategy_id=%s AND version=%s
                    """,
                    (item["strategy_id"], item["version"]),
                ).fetchone()
                if existing and existing["code_fingerprint"].strip() != item["code_fingerprint"]:
                    raise conflict(
                        "strategy_fingerprint_changed",
                        f"{item['strategy_id']}@{item['version']} changed; bump version",
                    )
                connection.execute(
                    """
                    INSERT INTO strategy_versions(
                        strategy_id, version, parameters_schema, default_params,
                        input_requirements, overlay_types, code_fingerprint
                    ) VALUES (%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT(strategy_id, version) DO NOTHING
                    """,
                    (
                        item["strategy_id"],
                        item["version"],
                        Jsonb(item["parameters_schema"]),
                        Jsonb(item.get("default_params", {})),
                        Jsonb(item["input_requirements"]),
                        Jsonb(item["overlay_types"]),
                        item["code_fingerprint"],
                    ),
                )

    def list_strategies(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT d.strategy_id,v.version,d.family,d.display_name,d.description,d.is_composite,
                       v.parameters_schema,v.default_params,v.input_requirements,
                       v.overlay_types,v.code_fingerprint,
                       COALESCE((runtime.spec_json->>'warmup_bars')::integer, 0) AS warm_up_candles
                FROM strategy_definitions d
                JOIN strategy_versions v ON v.strategy_id=d.strategy_id
                LEFT JOIN strategy_runtime_specs runtime
                  ON runtime.strategy_id=v.strategy_id AND runtime.version=v.version
                ORDER BY d.strategy_id,v.version
                """
            ).fetchall()
        return [
            {
                "strategy_id": row["strategy_id"],
                "version": row["version"],
                "family": row["family"],
                "display_name": row["display_name"],
                "description": row["description"] or "",
                "parameters_schema": row["parameters_schema"],
                "default_params": row["default_params"],
                "input_requirements": row["input_requirements"],
                "overlay_types": row["overlay_types"],
                "warm_up_candles": row["warm_up_candles"],
                "is_composite": row["is_composite"],
                "code_fingerprint": row["code_fingerprint"].strip(),
            }
            for row in rows
        ]
    def create_strategy_draft(
        self,
        *,
        request: StrategyDraftCreateIn,
        source_hash: str,
        spec: dict[str, Any],
        artifact: str,
        artifact_hash: str,
        report: dict[str, Any],
        report_hash: str,
        model: str,
        model_version: str,
        prompt_hash: str,
        attempts_used: int,
        correlation_id: str | None = None,
    ) -> dict[str, Any]:
        spec_hash = hash_canonical_json(spec)
        existing_id: UUID | None = None
        with self._connect() as connection:
            if request.idempotency_key:
                existing = connection.execute(
                    "SELECT id FROM strategy_drafts WHERE owner_id=%s AND idempotency_key=%s",
                    (request.owner_id, request.idempotency_key),
                ).fetchone()
                if existing:
                    existing_id = existing["id"]
            if existing_id is None:
                draft = connection.execute(
                """
                INSERT INTO strategy_drafts(
                    owner_id,source_type,source_ref,source_hash,mode,name_hint,
                    current_revision,status,idempotency_key
                ) VALUES (%s,%s,%s,%s,%s,%s,1,'REVIEW_REQUIRED',%s) RETURNING id
                """,
                (
                    request.owner_id,
                    request.source.type,
                    request.source.text or request.source.url or "dsl",
                    source_hash,
                    request.mode,
                    request.name_hint,
                    request.idempotency_key,
                ),
                ).fetchone()
                draft_id = draft["id"]
                connection.execute(
                """
                INSERT INTO strategy_draft_revisions(draft_id,revision,spec_json,spec_hash,created_by)
                VALUES (%s,1,%s,%s,'designer')
                """,
                (draft_id, Jsonb(spec), spec_hash),
                )
                agent = connection.execute(
                """
                INSERT INTO agent_runs(
                    draft_id,agent_type,state,model,model_version,prompt_hash,tool_policy_version,attempts_used
                ) VALUES (%s,'StrategyDesignerAgent','review_required',%s,%s,%s,'typed-tools-v1',%s)
                RETURNING id
                """,
                (draft_id, model, model_version, prompt_hash, attempts_used),
                ).fetchone()
                artifact_row = connection.execute(
                """
                INSERT INTO strategy_artifacts(
                    draft_id,revision,language,source_text,artifact_hash,compiler_version
                ) VALUES (%s,1,'python',%s,%s,'dsl-compiler-v1') RETURNING id
                """,
                (draft_id, artifact, artifact_hash),
                ).fetchone()
                connection.execute(
                """
                INSERT INTO sandbox_runs(
                    artifact_id,policy_version,fixture_version,status,report_json
                ) VALUES (%s,'dsl-policy-v1','strategy-contract-v1','passed',%s)
                """,
                (artifact_row["id"], Jsonb({**report, "report_hash": report_hash})),
                )
                connection.execute(
                """
                INSERT INTO domain_events(event_type,aggregate_type,aggregate_id,correlation_id,payload)
                VALUES ('StrategyDraftReviewRequired','strategy_draft',%s,%s,%s)
                """,
                (draft_id, correlation_id, Jsonb({"agent_run_id": str(agent["id"]), "spec_hash": spec_hash})),
                )
        if existing_id is not None:
            return self.get_strategy_draft(existing_id, request.owner_id)
        return self.get_strategy_draft(draft_id, request.owner_id)

    def get_strategy_draft(self, draft_id: UUID, owner_id: UUID | None = None) -> dict[str, Any]:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT d.*,r.spec_json,r.spec_hash,a.artifact_hash,agent.attempts_used,
                       s.report_json->>'report_hash' AS sandbox_report_hash
                FROM strategy_drafts d
                LEFT JOIN strategy_draft_revisions r
                  ON r.draft_id=d.id AND r.revision=d.current_revision
                LEFT JOIN strategy_artifacts a
                  ON a.draft_id=d.id AND a.revision=d.current_revision
                LEFT JOIN sandbox_runs s ON s.artifact_id=a.id
                LEFT JOIN LATERAL (
                    SELECT attempts_used FROM agent_runs
                    WHERE draft_id=d.id AND agent_type='StrategyDesignerAgent'
                    ORDER BY created_at DESC LIMIT 1
                ) agent ON TRUE
                WHERE d.id=%s
                """,
                (draft_id,),
            ).fetchone()
        if row is None or (owner_id is not None and row["owner_id"] != owner_id):
            raise not_found("strategy_draft")
        return {
            "draft_id": row["id"],
            "owner_id": row["owner_id"],
            "source_type": row["source_type"],
            "mode": row["mode"],
            "name_hint": row["name_hint"],
            "status": row["status"],
            "current_revision": row["current_revision"],
            "source_hash": row["source_hash"],
            "spec_hash": row["spec_hash"],
            "artifact_hash": row["artifact_hash"],
            "sandbox_report_hash": row["sandbox_report_hash"],
            "repair_attempts_used": row["attempts_used"] or 1,
            "repair_attempts_max": 3,
            "strategy_spec": row["spec_json"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def list_strategy_drafts(self, owner_id: UUID, limit: int) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id FROM strategy_drafts
                WHERE owner_id=%s
                ORDER BY updated_at DESC, id DESC
                LIMIT %s
                """,
                (owner_id, limit),
            ).fetchall()
        return [self.get_strategy_draft(row["id"], owner_id) for row in rows]

    def approve_strategy_draft(self, draft_id: UUID, request: StrategyApprovalIn) -> dict[str, Any]:
        target_status = "APPROVED" if request.decision == "approve" else "REJECTED"
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT d.owner_id,d.status,d.current_revision,r.spec_json,r.spec_hash,a.artifact_hash,
                       s.status AS sandbox_status,s.report_json->>'report_hash' AS sandbox_report_hash
                FROM strategy_drafts d
                JOIN strategy_draft_revisions r ON r.draft_id=d.id AND r.revision=d.current_revision
                JOIN strategy_artifacts a ON a.draft_id=d.id AND a.revision=d.current_revision
                JOIN sandbox_runs s ON s.artifact_id=a.id
                WHERE d.id=%s FOR UPDATE
                """,
                (draft_id,),
            ).fetchone()
            if row is None or row["owner_id"] != request.reviewer_id:
                raise not_found("strategy_draft")
            reused = False
            if request.idempotency_key:
                existing_approval = connection.execute(
                    """
                    SELECT revision,spec_hash,artifact_hash,sandbox_report_hash
                    FROM strategy_approvals
                    WHERE draft_id=%s AND idempotency_key=%s
                    """,
                    (draft_id, request.idempotency_key),
                ).fetchone()
                if existing_approval:
                    if any(
                        existing_approval[key] != value
                        for key, value in (
                            ("revision", request.revision),
                            ("spec_hash", request.spec_hash),
                            ("artifact_hash", request.artifact_hash),
                            ("sandbox_report_hash", request.sandbox_report_hash),
                        )
                    ):
                        raise conflict("idempotency_key_reused", "approval idempotency key has different content")
                    reused = True
            if not reused and row["status"] != "REVIEW_REQUIRED":
                raise conflict("invalid_draft_transition", "draft is no longer awaiting review")
            if (
                request.revision != row["current_revision"]
                or request.spec_hash != row["spec_hash"]
                or request.artifact_hash != row["artifact_hash"]
                or request.sandbox_report_hash != row["sandbox_report_hash"]
            ):
                raise conflict("stale_revision", "approval fingerprint does not match the frozen draft")
            if target_status == "APPROVED" and row["sandbox_status"] != "passed":
                raise conflict("sandbox_not_passed", "strategy preflight must pass before approval")
            if not reused and target_status == "APPROVED":
                spec = row["spec_json"]
                existing_version = connection.execute(
                    "SELECT code_fingerprint FROM strategy_versions WHERE strategy_id=%s AND version='v1'",
                    (str(spec["strategy_id"]),),
                ).fetchone()
                if existing_version and existing_version["code_fingerprint"].strip() != request.artifact_hash:
                    raise conflict("strategy_version_conflict", "strategy id already has a different immutable artifact")
            if not reused:
                connection.execute(
                """
                INSERT INTO strategy_approvals(
                    draft_id,reviewer_id,revision,spec_hash,artifact_hash,
                    sandbox_report_hash,decision,reason,idempotency_key
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT DO NOTHING
                """,
                (
                    draft_id,
                    request.reviewer_id,
                    request.revision,
                    request.spec_hash,
                    request.artifact_hash,
                    request.sandbox_report_hash,
                    request.decision,
                    request.reason,
                    request.idempotency_key,
                ),
                )
                connection.execute(
                    "UPDATE strategy_drafts SET status=%s,updated_at=now() WHERE id=%s",
                    (target_status, draft_id),
                )
                if target_status == "APPROVED":
                    spec = row["spec_json"]
                    strategy_id = str(spec["strategy_id"])
                    version = "v1"
                    connection.execute(
                        """
                        INSERT INTO strategy_definitions(strategy_id,display_name,family,description,is_composite)
                        VALUES (%s,%s,%s,%s,FALSE)
                        ON CONFLICT(strategy_id) DO NOTHING
                        """,
                        (strategy_id, spec["display_name"], spec["family"], spec["description"]),
                    )
                    connection.execute(
                        """
                        INSERT INTO strategy_versions(
                            strategy_id,version,parameters_schema,default_params,
                            input_requirements,overlay_types,code_fingerprint
                        ) VALUES (%s,%s,%s,%s,%s,%s,%s)
                        ON CONFLICT(strategy_id,version) DO NOTHING
                        """,
                        (
                            strategy_id,
                            version,
                            Jsonb(spec.get("parameters", {})),
                            Jsonb({
                                key: value.get("default")
                                for key, value in spec.get("parameters", {}).items()
                                if isinstance(value, dict) and "default" in value
                            }),
                            Jsonb([]),
                            Jsonb([]),
                            request.artifact_hash,
                        ),
                    )
                    connection.execute(
                        """
                        INSERT INTO strategy_runtime_specs(strategy_id,version,spec_json,artifact_hash)
                        VALUES (%s,%s,%s,%s)
                        ON CONFLICT(strategy_id,version) DO NOTHING
                        """,
                        (strategy_id, version, Jsonb(spec), request.artifact_hash),
                    )
                    connection.execute(
                        """
                        INSERT INTO domain_events(event_type,aggregate_type,aggregate_id,correlation_id,payload)
                        VALUES ('StrategyPublished','strategy_draft',%s,%s,%s)
                        """,
                        (draft_id, None, Jsonb({"strategy_id": strategy_id, "version": version})),
                    )
        return self.get_strategy_draft(draft_id, request.reviewer_id)

    def create_experiment(
        self, request: ExperimentCreateIn, correlation_id: str | None = None
    ) -> dict[str, Any]:
        candidate = request.candidate_definition or {
            "strategy_id": request.strategy_id,
            "version": request.strategy_version,
            "parameters": {},
        }
        candidate_hash = request.candidate_hash or hash_canonical_json(candidate)
        with self._connect() as connection:
            if request.idempotency_key:
                existing = connection.execute(
                    """
                    SELECT e.id AS experiment_id, j.id AS run_id, j.status
                    FROM experiments e JOIN backtest_jobs j ON j.experiment_id=e.id
                    WHERE e.owner_id=%s AND e.idempotency_key=%s
                    """,
                    (request.owner_id, request.idempotency_key),
                ).fetchone()
                if existing:
                    return {**existing, "reused": True}

            # Serialize quota decisions without requiring UPDATE permission on
            # the Go-owned users table. The lock lives only for this transaction.
            connection.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                (str(request.owner_id),),
            )
            owner = connection.execute(
                "SELECT id FROM users WHERE id=%s AND is_active", (request.owner_id,)
            ).fetchone()
            if owner is None:
                raise not_found("owner")
            strategy = connection.execute(
                "SELECT id FROM strategy_versions WHERE strategy_id=%s AND version=%s",
                (request.strategy_id, request.strategy_version),
            ).fetchone()
            if strategy is None:
                raise not_found("strategy_version")
            dataset = connection.execute(
                """
                SELECT d.id,d.bbo_content_hash,d.range_from,d.range_to,count(c.open_time) AS candle_count
                FROM market_datasets d
                LEFT JOIN market_dataset_candles c ON c.market_dataset_id=d.id
                WHERE d.dataset_version=%s
                GROUP BY d.id,d.bbo_content_hash,d.range_from,d.range_to
                """,
                (request.dataset_version,),
            ).fetchone()
            if dataset is None:
                raise not_found("dataset")
            replay_range_from = request.range_from or dataset["range_from"]
            replay_range_to = request.range_to or dataset["range_to"]
            if replay_range_from < dataset["range_from"] or replay_range_to > dataset["range_to"]:
                raise validation("replay_range_outside_dataset", "backtest range must be inside the immutable dataset")
            replay_count = connection.execute(
                """
                SELECT count(*) AS count FROM market_dataset_candles
                WHERE market_dataset_id=%s AND open_time >= %s AND close_time <= %s
                """,
                (dataset["id"], replay_range_from, replay_range_to),
            ).fetchone()["count"]
            if replay_count == 0:
                raise validation("replay_range_empty", "backtest range contains no closed candles")
            if request.bbo_dataset_hash and dataset["bbo_content_hash"] != request.bbo_dataset_hash:
                raise validation(
                    "bbo_dataset_hash_mismatch",
                    "BBO replay hash does not match dataset",
                    "bbo_dataset_hash",
                )

            quota = connection.execute(
                """
                SELECT COALESCE(q.max_concurrent_runs, 2) AS limit,
                       COALESCE(q.max_candles_per_experiment, 20000) AS max_candles,
                       count(j.id) FILTER (
                           WHERE j.status='leased' AND j.lease_expires_at >= now()
                       ) AS active
                FROM users u
                LEFT JOIN user_quotas q ON q.user_id=u.id
                LEFT JOIN experiments e ON e.owner_id=u.id
                LEFT JOIN backtest_jobs j ON j.experiment_id=e.id
                WHERE u.id=%s GROUP BY q.max_concurrent_runs,q.max_candles_per_experiment
                """,
                (request.owner_id,),
            ).fetchone()
            if quota and quota["active"] >= quota["limit"]:
                raise validation("concurrent_run_quota_exceeded", "concurrent run quota exceeded")
            if quota and replay_count > quota["max_candles"]:
                raise validation("candle_quota_exceeded", "dataset exceeds candle quota")

            experiment = connection.execute(
                """
                INSERT INTO experiments(
                    owner_id, strategy_version_id, candidate_definition, candidate_hash,
                    market_dataset_id, replay_range_from, replay_range_to, bbo_dataset_hash, initial_equity, fixed_notional,
                    leverage, fee_bps, slippage_bps, fill_policy, position_policy,
                    open_position_at_end, stop_loss_pct, take_profit_pct,
                    intrabar_priority, evaluator_version, sentiment_model,
                    sentiment_model_version, sentiment_window_sec, analysis_lag_sec,
                    idempotency_key, correlation_id
                ) VALUES (
                    %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s
                ) RETURNING id
                """,
                (
                    request.owner_id,
                    strategy["id"],
                    Jsonb(candidate),
                    candidate_hash,
                    dataset["id"],
                    replay_range_from,
                    replay_range_to,
                    request.bbo_dataset_hash or dataset["bbo_content_hash"],
                    request.initial_equity,
                    request.fixed_notional,
                    request.leverage,
                    request.fee_bps,
                    request.slippage_bps,
                    request.fill_policy,
                    request.position_policy,
                    request.open_position_at_end,
                    request.stop_loss_pct,
                    request.take_profit_pct,
                    request.intrabar_priority,
                    request.evaluator_version,
                    request.sentiment_model,
                    request.sentiment_model_version,
                    request.sentiment_window_sec,
                    request.analysis_lag_sec,
                    request.idempotency_key,
                    correlation_id,
                ),
            ).fetchone()
            job = connection.execute(
                "INSERT INTO backtest_jobs(experiment_id) VALUES (%s) RETURNING id, status",
                (experiment["id"],),
            ).fetchone()
            connection.execute(
                """
                INSERT INTO domain_events(
                    event_type, aggregate_type, aggregate_id, correlation_id, payload
                ) VALUES ('ExperimentCreated','experiment',%s,%s,%s)
                """,
                (
                    experiment["id"],
                    correlation_id,
                    Jsonb(
                        {
                            "experiment_id": str(experiment["id"]),
                            "job_id": str(job["id"]),
                            "candidate_hash": candidate_hash,
                        }
                    ),
                ),
            )
        return {
            "experiment_id": experiment["id"],
            "run_id": job["id"],
            "status": job["status"],
            "reused": False,
        }

    def get_experiment(self, experiment_id: UUID, owner_id: UUID | None = None) -> dict[str, Any]:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT e.id AS experiment_id, r.id AS run_id, e.owner_id, e.candidate_hash,
                       COALESCE(r.status, 'queued'::run_status) AS status,
                       d.dataset_version,e.replay_range_from AS range_from,e.replay_range_to AS range_to,
                       d.provider, d.symbol, d.timeframe,d.content_hash,
                       d.bbo_content_hash,r.result_hash,e.candidate_definition,
                       v.strategy_id, v.version AS strategy_version, e.evaluator_version,
                       e.created_at, r.started_at, r.finished_at, r.candles_read,
                       r.signals_count, r.error_code,e.initial_equity,e.fixed_notional,
                       e.leverage,e.fee_bps,e.slippage_bps,e.fill_policy,e.position_policy,
                       e.open_position_at_end,e.stop_loss_pct,e.take_profit_pct,
                       e.intrabar_priority,e.sentiment_model,e.sentiment_model_version,
                       e.sentiment_window_sec,e.analysis_lag_sec,
                       ev.total_return_pct,ev.win_rate_pct,ev.max_drawdown_pct,
                       ev.trade_count,ev.profit_factor,ev.sharpe_ratio,
                       ranked.score
                FROM experiments e
                JOIN market_datasets d ON d.id=e.market_dataset_id
                JOIN strategy_versions v ON v.id=e.strategy_version_id
                LEFT JOIN backtest_runs r ON r.experiment_id=e.id
                LEFT JOIN evaluations ev
                  ON ev.backtest_run_id=r.id AND ev.evaluator_version=e.evaluator_version
                LEFT JOIN LATERAL (
                    SELECT l.score FROM leaderboard_entries l
                    WHERE l.evaluation_id=ev.id ORDER BY l.observed_at DESC LIMIT 1
                ) ranked ON TRUE
                WHERE e.id=%s
                """,
                (experiment_id,),
            ).fetchone()
        if row is None or (owner_id is not None and row["owner_id"] != owner_id):
            raise not_found("experiment")
        row["id"] = row["experiment_id"]
        row["execution"] = {
            "initial_equity": _float(row.pop("initial_equity")),
            "fixed_notional": _float(row.pop("fixed_notional")),
            "leverage": _float(row.pop("leverage")),
            "fee_bps": row.pop("fee_bps"),
            "slippage_bps": row.pop("slippage_bps"),
            "fill_policy": row.pop("fill_policy"),
            "position_policy": row.pop("position_policy"),
            "open_position_at_end": row.pop("open_position_at_end"),
            "stop_loss_pct": _float(row.pop("stop_loss_pct")),
            "take_profit_pct": _float(row.pop("take_profit_pct")),
            "intrabar_priority": row.pop("intrabar_priority"),
            "sentiment_model": row.pop("sentiment_model"),
            "sentiment_model_version": row.pop("sentiment_model_version"),
            "sentiment_window_sec": row.pop("sentiment_window_sec"),
            "analysis_lag_sec": row.pop("analysis_lag_sec"),
        }
        if row["total_return_pct"] is None:
            row["metrics"] = None
        else:
            row["metrics"] = {
                "total_return_pct": _float(row.pop("total_return_pct")),
                "win_rate_pct": _float(row.pop("win_rate_pct")),
                "max_drawdown_pct": _float(row.pop("max_drawdown_pct")),
                "trade_count": row.pop("trade_count"),
                "profit_factor": _float(row.pop("profit_factor")),
                "sharpe_ratio": _float(row.pop("sharpe_ratio")),
                "score": _float(row.pop("score")),
                "evaluator_version": row["evaluator_version"],
            }
        for key in (
            "total_return_pct",
            "win_rate_pct",
            "max_drawdown_pct",
            "trade_count",
            "profit_factor",
            "sharpe_ratio",
            "score",
        ):
            row.pop(key, None)
        return row

    def list_experiment_candles(self, experiment_id: UUID) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT c.open_time,c.close_time,c.open,c.high,c.low,c.close,c.volume,c.trade_count
                FROM market_dataset_candles c
                JOIN experiments e ON e.market_dataset_id=c.market_dataset_id
                WHERE e.id=%s AND c.open_time >= e.replay_range_from
                  AND c.close_time <= e.replay_range_to ORDER BY c.open_time
                """,
                (experiment_id,),
            ).fetchall()
        return [
            _as_float_fields(row, ("open", "high", "low", "close", "volume")) for row in rows
        ]

    def list_experiment_trades(self, experiment_id: UUID) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT t.sequence_no,t.side,t.signal_t,t.entry_time,t.entry_price,t.quantity,
                       t.fee_paid,t.slippage_cost,t.exit_time,t.exit_price,t.pnl_absolute,
                       t.pnl_percent,t.exit_reason,t.sl_price,t.tp_price
                FROM trades t JOIN backtest_runs r ON r.id=t.backtest_run_id
                WHERE r.experiment_id=%s ORDER BY t.sequence_no
                """,
                (experiment_id,),
            ).fetchall()
        numeric = (
            "entry_price",
            "quantity",
            "fee_paid",
            "slippage_cost",
            "exit_price",
            "pnl_absolute",
            "pnl_percent",
            "sl_price",
            "tp_price",
        )
        return [_as_float_fields(row, numeric) for row in rows]

    def list_experiment_equity(self, experiment_id: UUID) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT p.point_time,p.equity,p.drawdown_pct
                FROM equity_points p JOIN backtest_runs r ON r.id=p.backtest_run_id
                WHERE r.experiment_id=%s ORDER BY p.point_time
                """,
                (experiment_id,),
            ).fetchall()
        return [_as_float_fields(row, ("equity", "drawdown_pct")) for row in rows]

    def list_experiment_overlays(self, experiment_id: UUID) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT s.candle_time,s.signal,s.confidence,s.child_signals
                FROM run_signals s JOIN backtest_runs r ON r.id=s.backtest_run_id
                WHERE r.experiment_id=%s ORDER BY s.candle_time
                """,
                (experiment_id,),
            ).fetchall()
        return [_as_float_fields(row, ("confidence",)) for row in rows]

    def create_search_run(
        self, request: SearchRunCreateIn, correlation_id: str | None = None
    ) -> dict[str, Any]:
        with self._connect() as connection:
            if request.idempotency_key:
                existing = connection.execute(
                    """
                    SELECT s.*,d.dataset_version,d.content_hash
                    FROM search_runs s JOIN market_datasets d ON d.id=s.market_dataset_id
                    WHERE s.owner_id=%s AND s.idempotency_key=%s
                    """,
                    (request.owner_id, request.idempotency_key),
                ).fetchone()
                if existing:
                    return self._search_row(existing, reused=True)
            connection.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                (str(request.owner_id),),
            )
            owner = connection.execute(
                """
                SELECT u.id,
                       COALESCE(q.max_candidates_per_run,50) AS max_candidates,
                       COALESCE(q.max_concurrent_runs,2) AS max_concurrent_runs,
                       COALESCE(q.max_candles_per_experiment,20000) AS max_candles
                FROM users u LEFT JOIN user_quotas q ON q.user_id=u.id
                WHERE u.id=%s AND u.is_active
                """,
                (request.owner_id,),
            ).fetchone()
            if owner is None:
                raise not_found("owner")
            dataset = connection.execute(
                """
                SELECT d.id,d.content_hash,d.range_from,d.range_to,
                       COALESCE(d.bbo_content_hash,d.content_hash) AS bbo_content_hash,
                       count(c.open_time) AS candle_count
                FROM market_datasets d
                LEFT JOIN market_dataset_candles c ON c.market_dataset_id=d.id
                WHERE d.dataset_version=%s
                GROUP BY d.id,d.content_hash,d.bbo_content_hash,d.range_from,d.range_to
                """,
                (request.dataset_version,),
            ).fetchone()
            if dataset is None:
                raise not_found("dataset")
            if dataset["candle_count"] > owner["max_candles"]:
                raise validation("candle_quota_exceeded", "dataset exceeds candle quota")
            active = connection.execute(
                """
                SELECT count(j.id) AS count
                FROM experiments e JOIN backtest_jobs j ON j.experiment_id=e.id
                WHERE e.owner_id=%s AND j.status='leased' AND j.lease_expires_at >= now()
                """,
                (request.owner_id,),
            ).fetchone()["count"]
            if active >= owner["max_concurrent_runs"]:
                raise validation("concurrent_run_quota_exceeded", "concurrent run quota exceeded")
            stop_conditions = request.stop_conditions.model_dump(exclude_none=True)
            search_space = request.search_space.model_dump()
            requested_limit = int(
                stop_conditions.get("max_candidates") or owner["max_candidates"]
            )
            if requested_limit > owner["max_candidates"]:
                raise validation("candidate_quota_exceeded", "search exceeds candidate quota")
            candidate_limit = min(requested_limit, 500)
            # Ask for one extra item so persistence can distinguish a bounded
            # max-candidates stop from a genuinely exhausted finite space.
            generated = generate_candidates(
                request.generator_id, search_space, candidate_limit + 1, request.seed
            )
            generator_exhausted = len(generated) <= candidate_limit
            candidates = generated[:candidate_limit]
            if not candidates:
                raise validation("empty_search_space", "search space produced no candidates")
            stop_conditions.setdefault("max_candidates", candidate_limit)
            row = connection.execute(
                """
                INSERT INTO search_runs(
                    owner_id,generator_id,search_space,stop_conditions,
                    market_dataset_id,seed,idempotency_key,generator_exhausted,correlation_id
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *
                """,
                (
                    request.owner_id,
                    request.generator_id,
                    Jsonb(search_space),
                    Jsonb(stop_conditions),
                    dataset["id"],
                    request.seed,
                    request.idempotency_key,
                    generator_exhausted,
                    correlation_id,
                ),
            ).fetchone()
            for ordinal, candidate in enumerate(candidates, start=1):
                strategy = connection.execute(
                    "SELECT id FROM strategy_versions WHERE strategy_id=%s AND version=%s",
                    (candidate["strategy_id"], candidate["strategy_version"]),
                ).fetchone()
                if strategy is None:
                    raise not_found("strategy_version")
                candidate_row = connection.execute(
                    """
                    INSERT INTO search_candidates(
                        search_run_id,ordinal,candidate_definition,candidate_hash,
                        generated_by,generation_meta
                    ) VALUES (%s,%s,%s,%s,%s,%s) RETURNING id
                    """,
                    (
                        row["id"],
                        ordinal,
                        Jsonb(candidate["candidate_definition"]),
                        candidate["candidate_hash"],
                        request.generator_id,
                        Jsonb(
                            {
                                "seed": request.seed,
                                "generator_version": "v1",
                                **candidate.get("generation_meta", {}),
                            }
                        ),
                    ),
                ).fetchone()
                experiment = connection.execute(
                    """
                    INSERT INTO experiments(
                    owner_id,strategy_version_id,candidate_definition,candidate_hash,
                    market_dataset_id,replay_range_from,replay_range_to,bbo_dataset_hash,evaluator_version,search_candidate_id,
                    correlation_id
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'v1',%s,%s) RETURNING id
                    """,
                    (
                        request.owner_id,
                        strategy["id"],
                        Jsonb(candidate["candidate_definition"]),
                        candidate["candidate_hash"],
                        dataset["id"],
                        dataset["range_from"],
                        dataset["range_to"],
                        dataset["bbo_content_hash"],
                        candidate_row["id"],
                        correlation_id,
                    ),
                ).fetchone()
                connection.execute(
                    "UPDATE search_candidates SET experiment_id=%s WHERE id=%s",
                    (experiment["id"], candidate_row["id"]),
                )
                connection.execute(
                    "INSERT INTO backtest_jobs(experiment_id) VALUES (%s)",
                    (experiment["id"],),
                )
            row = connection.execute(
                """
                UPDATE search_runs SET status='running',generated=%s,updated_at=now()
                WHERE id=%s RETURNING *
                """,
                (len(candidates), row["id"]),
            ).fetchone()
            row["dataset_version"] = request.dataset_version
            row["content_hash"] = dataset["content_hash"]
            connection.execute(
                """
                INSERT INTO domain_events(
                    event_type,aggregate_type,aggregate_id,correlation_id,payload
                ) VALUES ('SearchRunStarted','search_run',%s,%s,%s)
                """,
                (
                    row["id"],
                    correlation_id,
                    Jsonb({"generated": len(candidates), "generator_id": request.generator_id}),
                ),
            )
        return self._search_row(row, reused=False)

    @staticmethod
    def _search_row(row: dict[str, Any], reused: bool = False) -> dict[str, Any]:
        return {
            "search_run_id": row["id"],
            "owner_id": row["owner_id"],
            "generator_id": row["generator_id"],
            "status": row["status"],
            "generated": row["generated"],
            "tested": row["tested"],
            "failed": row["failed"],
            "best_score": _float(row["best_score"]),
            "current_candidate_hash": row["current_candidate_hash"],
            "stop_reason": row["stop_reason"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "dataset_version": row["dataset_version"],
            "content_hash": row["content_hash"],
            "reused": reused,
        }

    def get_search_run(self, run_id: UUID, owner_id: UUID | None = None) -> dict[str, Any]:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT s.*,d.dataset_version,d.content_hash
                FROM search_runs s JOIN market_datasets d ON d.id=s.market_dataset_id
                WHERE s.id=%s
                """,
                (run_id,),
            ).fetchone()
        if row is None or (owner_id is not None and row["owner_id"] != owner_id):
            raise not_found("search_run")
        return self._search_row(row)

    def apply_search_action(self, run_id: UUID, request: SearchActionIn) -> dict[str, Any]:
        allowed = {
            ("queued", "pause"): "paused",
            ("running", "pause"): "paused",
            ("paused", "resume"): "running",
            ("queued", "cancel"): "cancelled",
            ("running", "cancel"): "cancelled",
            ("paused", "cancel"): "cancelled",
        }
        with self._connect() as connection:
            duplicate = connection.execute(
                "SELECT resulted_in FROM search_actions WHERE command_id=%s",
                (request.command_id,),
            ).fetchone()
            if duplicate:
                return {"search_run_id": run_id, "status": duplicate["resulted_in"], "reused": True}
            row = connection.execute(
                "SELECT owner_id,status FROM search_runs WHERE id=%s FOR UPDATE", (run_id,)
            ).fetchone()
            if row is None or row["owner_id"] != request.actor_id:
                raise not_found("search_run")
            target = allowed.get((row["status"], request.action))
            if target is None:
                raise conflict(
                    "invalid_search_transition",
                    f"cannot {request.action} a {row['status']} search run",
                )
            connection.execute(
                "UPDATE search_runs SET status=%s,updated_at=now() WHERE id=%s",
                (target, run_id),
            )
            if target == "cancelled":
                connection.execute(
                    """
                    UPDATE backtest_jobs j
                    SET status='cancelled',completed_at=now(),last_error='search_cancelled',
                        leased_by=NULL,lease_token=NULL,lease_expires_at=NULL
                    FROM experiments e JOIN search_candidates c ON c.id=e.search_candidate_id
                    WHERE j.experiment_id=e.id AND c.search_run_id=%s
                      AND j.status IN ('queued','leased')
                    """,
                    (run_id,),
                )
                connection.execute(
                    """
                    UPDATE backtest_runs r
                    SET status='cancelled',finished_at=now(),error_code='search_cancelled'
                    FROM experiments e JOIN search_candidates c ON c.id=e.search_candidate_id
                    WHERE r.experiment_id=e.id AND c.search_run_id=%s
                      AND r.status IN ('queued','running')
                    """,
                    (run_id,),
                )
            connection.execute(
                """
                INSERT INTO search_actions(
                    command_id,search_run_id,action,actor_id,requested_from,resulted_in
                ) VALUES (%s,%s,%s,%s,%s,%s)
                """,
                (request.command_id, run_id, request.action, request.actor_id, row["status"], target),
            )
        return {"search_run_id": run_id, "status": target, "reused": False}

    def list_leaderboard(
        self,
        dataset_version: str,
        score_policy_version: str | None,
        limit: int,
        sort_by: str,
    ) -> list[dict[str, Any]]:
        sort_columns = {
            "score": "score DESC",
            "return": "total_return_pct DESC",
            "win_rate": "win_rate_pct DESC",
            "mdd": "max_drawdown_pct ASC",
            "sharpe": "sharpe_ratio DESC NULLS LAST",
        }
        if sort_by not in sort_columns:
            raise validation("unsupported_sort_field", "unsupported leaderboard sort field", "sort_by")
        with self._connect() as connection:
            dataset = connection.execute(
                "SELECT id FROM market_datasets WHERE dataset_version=%s", (dataset_version,)
            ).fetchone()
            if dataset is None:
                raise not_found("dataset")
            policy = score_policy_version
            if policy is None:
                active = connection.execute(
                    "SELECT version FROM score_policies WHERE is_active"
                ).fetchone()
                if active is None:
                    raise conflict("no_active_score_policy", "no active score policy")
                policy = active["version"]
            rows = connection.execute(
                f"""
                SELECT entry_id,evaluation_id,score,
                       row_number() OVER (
                           ORDER BY {sort_columns[sort_by]},observed_at,evaluation_id
                       ) AS rank,
                       score_policy_version,dataset_version,strategy_id,strategy_version,
                       candidate_hash,total_return_pct,win_rate_pct,max_drawdown_pct,
                       trade_count,profit_factor,sharpe_ratio,observed_at
                FROM read.leaderboard_v1
                WHERE dataset_version=%s AND score_policy_version=%s
                ORDER BY {sort_columns[sort_by]}, observed_at, evaluation_id
                LIMIT %s
                """,
                (dataset_version, policy, limit),
            ).fetchall()
        numeric = (
            "score",
            "total_return_pct",
            "win_rate_pct",
            "max_drawdown_pct",
            "profit_factor",
            "sharpe_ratio",
        )
        return [_as_float_fields(row, numeric) for row in rows]

    def get_provenance(self, entry_id: UUID) -> dict[str, Any]:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT l.id AS entry_id,l.score,l.score_policy_version,l.observed_at,
                       e.id AS evaluation_id,e.evaluator_version,e.total_return_pct,
                       e.win_rate_pct,e.max_drawdown_pct,e.trade_count,e.profit_factor,
                       e.sharpe_ratio,r.id AS backtest_run_id,r.worker_id,r.duration_ms,
                       x.id AS experiment_id,x.candidate_definition,x.candidate_hash,
                       x.initial_equity,x.fixed_notional,x.leverage,x.fee_bps,x.slippage_bps,
                       x.fill_policy,x.position_policy,x.open_position_at_end,x.stop_loss_pct,
                       x.take_profit_pct,x.intrabar_priority,v.strategy_id,
                       v.version AS strategy_version,v.code_fingerprint,d.dataset_version,
                       d.provider,d.symbol,d.timeframe,d.range_from,d.range_to,d.content_hash
                FROM leaderboard_entries l
                JOIN evaluations e ON e.id=l.evaluation_id
                JOIN backtest_runs r ON r.id=e.backtest_run_id
                JOIN experiments x ON x.id=r.experiment_id
                JOIN strategy_versions v ON v.id=x.strategy_version_id
                JOIN market_datasets d ON d.id=x.market_dataset_id
                WHERE l.id=%s
                """,
                (entry_id,),
            ).fetchone()
        if row is None:
            raise not_found("leaderboard_entry")
        return _as_float_fields(
            row,
            (
                "score",
                "total_return_pct",
                "win_rate_pct",
                "max_drawdown_pct",
                "profit_factor",
                "sharpe_ratio",
                "initial_equity",
                "fixed_notional",
                "leverage",
                "stop_loss_pct",
                "take_profit_pct",
            ),
        )

    def create_score_policy(self, request: ScorePolicyCreateIn) -> dict[str, Any]:
        try:
            with self._connect() as connection:
                row = connection.execute(
                    """
                    INSERT INTO score_policies(version,min_trades,weights,formula)
                    VALUES (%s,%s,%s,%s) RETURNING *
                    """,
                    (request.version, request.min_trades, Jsonb(request.weights), request.formula),
                ).fetchone()
        except psycopg.errors.UniqueViolation as exc:
            raise conflict("score_policy_exists", "score policy version already exists") from exc
        return row

    def activate_score_policy(self, version: str) -> None:
        with self._connect() as connection:
            try:
                connection.execute("SELECT activate_score_policy(%s)", (version,)).fetchone()
            except psycopg.errors.NoDataFound as exc:
                raise not_found("score_policy") from exc

    def list_news(self, limit: int, coin: str | None = None) -> list[dict[str, Any]]:
        where = "WHERE %s = ANY(related_coins)" if coin else ""
        params: tuple[Any, ...] = (coin.upper(), limit) if coin else (limit,)
        with self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT id,title,canonical_url AS url,published_at,source_key,
                       display_name AS source_name,related_coins,sentiment_label,
                       sentiment_score,sentiment_model,sentiment_model_version,
                       sentiment_analyzed_at
                FROM read.news_v1 {where}
                ORDER BY published_at DESC LIMIT %s
                """,
                params,
            ).fetchall()
        result = []
        for row in rows:
            sentiment = None
            if row["sentiment_label"] is not None:
                sentiment = {
                    "label": row.pop("sentiment_label"),
                    "score": float(row.pop("sentiment_score")),
                    "model": row.pop("sentiment_model"),
                    "model_version": row.pop("sentiment_model_version"),
                    "analyzed_at": row.pop("sentiment_analyzed_at"),
                }
            else:
                for key in (
                    "sentiment_label",
                    "sentiment_score",
                    "sentiment_model",
                    "sentiment_model_version",
                    "sentiment_analyzed_at",
                ):
                    row.pop(key)
            row["sentiment"] = sentiment
            result.append(row)
        return result

    def news_aggregate(self, coin: str | None = None) -> dict[str, Any]:
        where = "WHERE %s = ANY(n.related_coins)" if coin else ""
        params: tuple[Any, ...] = (coin.upper(),) if coin else ()
        with self._connect() as connection:
            row = connection.execute(
                f"""
                SELECT count(*) AS item_count,count(s.id) AS analyzed_count,
                       avg(s.score) AS average_score,
                       count(*) FILTER (WHERE s.label='POSITIVE') AS positive,
                       count(*) FILTER (WHERE s.label='NEUTRAL') AS neutral,
                       count(*) FILTER (WHERE s.label='NEGATIVE') AS negative
                FROM news_items n LEFT JOIN sentiment_results s ON s.news_item_id=n.id
                {where}
                """,
                params,
            ).fetchone()
        item_count = row["item_count"]
        analyzed = row["analyzed_count"]
        return {
            "item_count": item_count,
            "analyzed_count": analyzed,
            "coverage": analyzed / item_count if item_count else 0.0,
            "average_score": _float(row["average_score"]),
            "label_counts": {
                "POSITIVE": row["positive"],
                "NEUTRAL": row["neutral"],
                "NEGATIVE": row["negative"],
            },
        }

    # -- News collection and sentiment orchestration -------------------------

    def create_news_source(
        self,
        *,
        source_key: str,
        display_name: str,
        kind: str,
        allowed_origin: str,
        url_template: str,
    ) -> dict[str, Any]:
        try:
            with self._connect() as connection:
                return connection.execute(
                    """
                    INSERT INTO news_sources(
                        source_key,display_name,kind,allowed_origin,url_template
                    ) VALUES (%s,%s,%s,%s,%s) RETURNING *
                    """,
                    (source_key, display_name, kind, allowed_origin, url_template),
                ).fetchone()
        except psycopg.errors.UniqueViolation as exc:
            raise conflict("news_source_exists", "news source key already exists") from exc

    def list_approved_sources(self, source_id: UUID | None = None) -> list[ApprovedSource]:
        where = "AND id=%s" if source_id else ""
        params: tuple[Any, ...] = (source_id,) if source_id else ()
        with self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT id,source_key,display_name,kind,allowed_origin,url_template,is_active
                FROM news_sources WHERE is_active {where} ORDER BY source_key
                """,
                params,
            ).fetchall()
        return [ApprovedSource(**row) for row in rows]

    def latest_news_collection(self, source_id: UUID) -> datetime | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT finished_at FROM news_collection_jobs
                WHERE source_id=%s AND status='completed'
                ORDER BY finished_at DESC LIMIT 1
                """,
                (source_id,),
            ).fetchone()
        return row["finished_at"] if row else None

    def begin_news_collection(self, source_id: UUID) -> UUID | None:
        try:
            with self._connect() as connection:
                row = connection.execute(
                    """
                    INSERT INTO news_collection_jobs(source_id,status,started_at)
                    VALUES (%s,'running',now()) RETURNING id
                    """,
                    (source_id,),
                ).fetchone()
            return row["id"]
        except psycopg.errors.UniqueViolation:
            return None

    def complete_news_collection(
        self,
        job_id: UUID,
        source: ApprovedSource,
        items: list[CollectedItem],
        correlation_id: str | None = None,
    ) -> tuple[int, list[UUID]]:
        inserted_ids: list[UUID] = []
        with self._connect() as connection:
            job = connection.execute(
                """
                SELECT id FROM news_collection_jobs
                WHERE id=%s AND source_id=%s AND status='running' FOR UPDATE
                """,
                (job_id, source.id),
            ).fetchone()
            if job is None:
                raise conflict("news_job_not_running", "news collection job is not running")
            for item in items:
                inserted = connection.execute(
                    """
                    INSERT INTO news_items(
                        source_id,canonical_url,url_hash,title,content_hash,content,
                        published_at,related_coins,extraction_version,tagging_version
                    ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT DO NOTHING RETURNING id
                    """,
                    (
                        source.id,
                        item.canonical_url,
                        item.url_hash,
                        item.title,
                        item.content_hash,
                        item.content,
                        item.published_at,
                        list(item.related_coins),
                        item.extraction_version,
                        item.tagging_version,
                    ),
                ).fetchone()
                if inserted is None:
                    continue
                news_item_id = inserted["id"]
                inserted_ids.append(news_item_id)
                connection.execute(
                    """
                    INSERT INTO domain_events(
                        event_type,aggregate_type,aggregate_id,correlation_id,payload
                    ) VALUES ('NewsCollected','news_item',%s,%s,%s)
                    """,
                    (
                        news_item_id,
                        correlation_id,
                        Jsonb(
                            {
                                "news_item_id": str(news_item_id),
                                "source_key": source.source_key,
                                "title_hash": hash_canonical_json(item.title),
                            }
                        ),
                    ),
                )
            connection.execute(
                """
                UPDATE news_collection_jobs
                SET status='completed',items_found=%s,items_new=%s,finished_at=now()
                WHERE id=%s
                """,
                (len(items), len(inserted_ids), job_id),
            )
            connection.execute(
                "UPDATE news_sources SET last_collected_at=now() WHERE id=%s",
                (source.id,),
            )
        return len(items), inserted_ids

    def fail_news_collection(self, job_id: UUID, reason: str) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE news_collection_jobs
                SET status='failed',failure_reason=%s,finished_at=now()
                WHERE id=%s AND status='running'
                """,
                (reason[:500], job_id),
            )

    def persist_news_document(self, source: ApprovedSource, failure: Any) -> UUID:
        document_text = str(failure.document_text)
        with self._connect() as connection:
            row = connection.execute(
                """
                INSERT INTO news_documents(
                    source_id,canonical_url,content_hash,sanitized_document,title_hint,
                    published_at,quality_reason,sanitizer_version
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,'html-sanitizer/v1')
                ON CONFLICT(source_id,content_hash) DO UPDATE SET
                    canonical_url=EXCLUDED.canonical_url,title_hint=EXCLUDED.title_hint,
                    published_at=EXCLUDED.published_at,quality_reason=EXCLUDED.quality_reason
                RETURNING id
                """,
                (
                    source.id,
                    canonical_url(str(failure.page_url)),
                    sha256_text(document_text),
                    document_text,
                    str(failure.title_hint)[:512],
                    failure.published_at,
                    str(failure.reason)[:64],
                ),
            ).fetchone()
        return row["id"]

    def find_news_extraction(self, document_id: UUID, cache_key: str | None) -> CollectedItem | None:
        if not cache_key:
            return None
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT result_json FROM news_extraction_attempts
                WHERE document_id=%s AND cache_key=%s AND status='completed'
                """,
                (document_id, cache_key),
            ).fetchone()
        if row is None or not isinstance(row["result_json"], dict):
            return None
        try:
            item = row["result_json"]
            published_at = datetime.fromisoformat(str(item["published_at"]).replace("Z", "+00:00"))
            if published_at.tzinfo is None:
                published_at = published_at.replace(tzinfo=UTC)
            return CollectedItem(
                source_id=UUID(str(item["source_id"])),
                canonical_url=str(item["canonical_url"]),
                url_hash=str(item["url_hash"]),
                title=str(item["title"]),
                content=str(item["content"]),
                content_hash=str(item["content_hash"]),
                published_at=published_at.astimezone(UTC),
                related_coins=tuple(str(coin) for coin in item.get("related_coins", [])),
                extraction_version=str(item["extraction_version"]),
                tagging_version=str(item.get("tagging_version", "aliases-v1")),
            )
        except (KeyError, TypeError, ValueError):
            return None

    def persist_news_extraction(
        self,
        *,
        document_id: UUID,
        cache_key: str | None,
        method: str,
        status: str,
        item: CollectedItem | None = None,
        model: str | None = None,
        model_version: str | None = None,
        error_code: str | None = None,
    ) -> None:
        resolved_key = cache_key or hash_canonical_json(
            {"document_id": str(document_id), "method": method}
        )
        result_json = None if item is None else {
            "source_id": str(item.source_id), "canonical_url": item.canonical_url,
            "url_hash": item.url_hash, "title": item.title, "content": item.content,
            "content_hash": item.content_hash, "published_at": item.published_at.isoformat(),
            "related_coins": list(item.related_coins), "extraction_version": item.extraction_version,
            "tagging_version": item.tagging_version,
        }
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO news_extraction_attempts(
                    document_id,cache_key,method,status,model,model_version,result_json,error_code
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT(document_id,cache_key) DO UPDATE SET
                    status=EXCLUDED.status,model=EXCLUDED.model,model_version=EXCLUDED.model_version,
                    result_json=EXCLUDED.result_json,error_code=EXCLUDED.error_code,created_at=now()
                """,
                (document_id, resolved_key, method, status, model, model_version, Jsonb(result_json), error_code),
            )

    def pending_sentiment_items(
        self, model: str, model_version: str, limit: int = 200
    ) -> list[dict[str, Any]]:
        with self._connect() as connection:
            return connection.execute(
                """
                SELECT n.id,n.title,n.content
                FROM news_items n
                LEFT JOIN sentiment_results s
                  ON s.news_item_id=n.id AND s.model=%s AND s.model_version=%s
                WHERE s.id IS NULL
                ORDER BY n.published_at,n.id LIMIT %s
                """,
                (model, model_version, limit),
            ).fetchall()

    def persist_sentiment(self, news_item_id: UUID, result: SentimentResult) -> bool:
        with self._connect() as connection:
            row = connection.execute(
                """
                INSERT INTO sentiment_results(
                    news_item_id,label,score,model,model_version,analyzed_at
                ) VALUES (%s,%s,%s,%s,%s,%s)
                ON CONFLICT(news_item_id,model,model_version) DO NOTHING
                RETURNING id
                """,
                (
                    news_item_id,
                    result.label,
                    result.score,
                    result.model,
                    result.model_version,
                    result.analyzed_at,
                ),
            ).fetchone()
        return row is not None

    def sentiment_window(
        self,
        *,
        coin: str,
        as_of: datetime,
        window_seconds: int,
        analysis_lag_seconds: int,
        model: str,
        model_version: str,
    ) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT count(*) AS item_count,
                       avg(CASE s.label WHEN 'POSITIVE' THEN s.score
                                        WHEN 'NEGATIVE' THEN -s.score ELSE 0 END) AS avg_score
                FROM news_items n
                JOIN sentiment_results s ON s.news_item_id=n.id
                WHERE %s=ANY(n.related_coins)
                  AND s.model=%s AND s.model_version=%s
                  AND n.published_at + make_interval(secs => %s) <= %s
                  AND n.published_at + make_interval(secs => %s) >
                      %s - make_interval(secs => %s)
                """,
                (
                    coin.upper(),
                    model,
                    model_version,
                    analysis_lag_seconds,
                    as_of,
                    analysis_lag_seconds,
                    as_of,
                    window_seconds,
                ),
            ).fetchone()
        if not row or row["item_count"] == 0:
            return None
        return {
            "window_sec": window_seconds,
            "avg_score": float(row["avg_score"]),
            "item_count": row["item_count"],
            "model_version": model_version,
            "as_of": as_of.astimezone(UTC),
        }
