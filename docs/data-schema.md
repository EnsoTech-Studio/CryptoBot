## Table `schema_migrations`

### Columns

| Name         | Type          | Constraints |
| ------------ | ------------- | ----------- |
| `version`    | `text`        | Primary     |
| `checksum`   | `bpchar`      |             |
| `applied_at` | `timestamptz` |             |

## Table `users`

### Columns

| Name            | Type          | Constraints |
| --------------- | ------------- | ----------- |
| `id`            | `uuid`        | Primary     |
| `email`         | `varchar`     | Unique      |
| `password_hash` | `varchar`     |             |
| `display_name`  | `varchar`     |             |
| `role`          | `varchar`     |             |
| `is_active`     | `bool`        |             |
| `created_at`    | `timestamptz` |             |
| `updated_at`    | `timestamptz` |             |

## Table `market_pairs`

### Columns

| Name        | Type      | Constraints |
| ----------- | --------- | ----------- |
| `id`        | `int2`    | Primary     |
| `symbol`    | `varchar` |             |
| `base`      | `varchar` |             |
| `quote`     | `varchar` |             |
| `provider`  | `varchar` |             |
| `is_active` | `bool`    |             |

## Table `market_datasets`

### Columns

| Name               | Type             | Constraints |
| ------------------ | ---------------- | ----------- |
| `id`               | `uuid`           | Primary     |
| `dataset_version`  | `varchar`        | Unique      |
| `provider`         | `varchar`        |             |
| `symbol`           | `varchar`        |             |
| `timeframe`        | `timeframe_enum` |             |
| `range_from`       | `timestamptz`    |             |
| `range_to`         | `timestamptz`    |             |
| `revision_no`      | `int2`           |             |
| `candle_count`     | `int4`           |             |
| `content_hash`     | `bpchar`         |             |
| `created_at`       | `timestamptz`    |             |
| `bbo_content_hash` | `bpchar`         | Nullable    |

## Table `market_dataset_candles`

### Columns

| Name                | Type          | Constraints |
| ------------------- | ------------- | ----------- |
| `market_dataset_id` | `uuid`        | Primary     |
| `open_time`         | `timestamptz` | Primary     |
| `close_time`        | `timestamptz` |             |
| `open`              | `numeric`     |             |
| `high`              | `numeric`     |             |
| `low`               | `numeric`     |             |
| `close`             | `numeric`     |             |
| `volume`            | `numeric`     |             |
| `trade_count`       | `int4`        | Nullable    |

## Table `market_dataset_bbo`

### Columns

| Name                | Type          | Constraints |
| ------------------- | ------------- | ----------- |
| `market_dataset_id` | `uuid`        | Primary     |
| `event_time`        | `timestamptz` | Primary     |
| `source_sequence`   | `int8`        | Primary     |
| `bid`               | `numeric`     |             |
| `bid_qty`           | `numeric`     |             |
| `ask`               | `numeric`     |             |
| `ask_qty`           | `numeric`     |             |
| `update_id`         | `int8`        | Nullable    |

## Table `strategy_definitions`

### Columns

| Name           | Type          | Constraints |
| -------------- | ------------- | ----------- |
| `strategy_id`  | `varchar`     | Primary     |
| `display_name` | `varchar`     |             |
| `family`       | `varchar`     | Nullable    |
| `description`  | `text`        | Nullable    |
| `is_composite` | `bool`        |             |
| `created_at`   | `timestamptz` |             |

## Table `strategy_versions`

### Columns

| Name                 | Type          | Constraints |
| -------------------- | ------------- | ----------- |
| `id`                 | `uuid`        | Primary     |
| `strategy_id`        | `varchar`     |             |
| `version`            | `varchar`     |             |
| `parameters_schema`  | `jsonb`       |             |
| `default_params`     | `jsonb`       |             |
| `input_requirements` | `jsonb`       |             |
| `overlay_types`      | `jsonb`       |             |
| `code_fingerprint`   | `bpchar`      |             |
| `registered_at`      | `timestamptz` |             |

## Table `experiments`

### Columns

| Name                      | Type                        | Constraints     |
| ------------------------- | --------------------------- | --------------- |
| `id`                      | `uuid`                      | Primary         |
| `owner_id`                | `uuid`                      |                 |
| `strategy_version_id`     | `uuid`                      |                 |
| `candidate_definition`    | `jsonb`                     |                 |
| `candidate_hash`          | `bpchar`                    |                 |
| `market_dataset_id`       | `uuid`                      |                 |
| `bbo_dataset_hash`        | `bpchar`                    | Nullable        |
| `initial_equity`          | `numeric`                   |                 |
| `fixed_notional`          | `numeric`                   |                 |
| `leverage`                | `numeric`                   |                 |
| `fee_bps`                 | `int2`                      |                 |
| `slippage_bps`            | `int2`                      |                 |
| `fill_policy`             | `fill_policy_enum`          |                 |
| `position_policy`         | `position_policy_enum`      |                 |
| `open_position_at_end`    | `open_position_policy_enum` |                 |
| `stop_loss_pct`           | `numeric`                   | Nullable        |
| `take_profit_pct`         | `numeric`                   | Nullable        |
| `intrabar_priority`       | `varchar`                   |                 |
| `evaluator_version`       | `varchar`                   |                 |
| `search_candidate_id`     | `uuid`                      | Nullable Unique |
| `created_at`              | `timestamptz`               |                 |
| `idempotency_key`         | `varchar`                   | Nullable        |
| `sentiment_model`         | `varchar`                   |                 |
| `sentiment_model_version` | `varchar`                   |                 |
| `sentiment_window_sec`    | `int4`                      |                 |
| `analysis_lag_sec`        | `int4`                      |                 |
| `correlation_id`          | `varchar`                   | Nullable        |
| `replay_range_from`       | `timestamptz`               |                 |
| `replay_range_to`         | `timestamptz`               |                 |

## Table `backtest_jobs`

### Columns

| Name               | Type          | Constraints |
| ------------------ | ------------- | ----------- |
| `id`               | `uuid`        | Primary     |
| `experiment_id`    | `uuid`        | Unique      |
| `status`           | `job_status`  |             |
| `priority`         | `int2`        |             |
| `attempt`          | `int2`        |             |
| `max_attempts`     | `int2`        |             |
| `leased_by`        | `varchar`     | Nullable    |
| `lease_token`      | `uuid`        | Nullable    |
| `lease_expires_at` | `timestamptz` | Nullable    |
| `last_error`       | `text`        | Nullable    |
| `enqueued_at`      | `timestamptz` |             |
| `completed_at`     | `timestamptz` | Nullable    |

## Table `backtest_runs`

### Columns

| Name            | Type          | Constraints |
| --------------- | ------------- | ----------- |
| `id`            | `uuid`        | Primary     |
| `experiment_id` | `uuid`        | Unique      |
| `status`        | `run_status`  |             |
| `worker_id`     | `varchar`     | Nullable    |
| `lease_token`   | `uuid`        | Nullable    |
| `attempt`       | `int2`        |             |
| `candles_read`  | `int4`        | Nullable    |
| `signals_count` | `int4`        | Nullable    |
| `duration_ms`   | `int4`        | Nullable    |
| `error_code`    | `varchar`     | Nullable    |
| `error_detail`  | `text`        | Nullable    |
| `started_at`    | `timestamptz` | Nullable    |
| `finished_at`   | `timestamptz` | Nullable    |
| `created_at`    | `timestamptz` |             |
| `result_hash`   | `bpchar`      | Nullable    |

## Table `trades`

### Columns

| Name              | Type          | Constraints |
| ----------------- | ------------- | ----------- |
| `id`              | `int8`        | Primary     |
| `backtest_run_id` | `uuid`        |             |
| `sequence_no`     | `int4`        |             |
| `side`            | `trade_side`  |             |
| `signal_t`        | `timestamptz` | Nullable    |
| `entry_time`      | `timestamptz` |             |
| `entry_price`     | `numeric`     |             |
| `exit_time`       | `timestamptz` | Nullable    |
| `exit_price`      | `numeric`     | Nullable    |
| `quantity`        | `numeric`     |             |
| `fee_paid`        | `numeric`     |             |
| `slippage_cost`   | `numeric`     |             |
| `pnl_absolute`    | `numeric`     | Nullable    |
| `pnl_percent`     | `numeric`     | Nullable    |
| `exit_reason`     | `varchar`     | Nullable    |
| `sl_price`        | `numeric`     | Nullable    |
| `tp_price`        | `numeric`     | Nullable    |

## Table `run_signals`

### Columns

| Name              | Type          | Constraints |
| ----------------- | ------------- | ----------- |
| `id`              | `int8`        | Primary     |
| `backtest_run_id` | `uuid`        |             |
| `candle_time`     | `timestamptz` |             |
| `signal`          | `signal_enum` |             |
| `confidence`      | `numeric`     | Nullable    |
| `child_signals`   | `jsonb`       | Nullable    |

## Table `equity_points`

### Columns

| Name              | Type          | Constraints |
| ----------------- | ------------- | ----------- |
| `backtest_run_id` | `uuid`        | Primary     |
| `point_time`      | `timestamptz` | Primary     |
| `equity`          | `numeric`     |             |
| `drawdown_pct`    | `numeric`     | Nullable    |

## Table `evaluations`

### Columns

| Name                | Type          | Constraints |
| ------------------- | ------------- | ----------- |
| `id`                | `uuid`        | Primary     |
| `backtest_run_id`   | `uuid`        |             |
| `evaluator_version` | `varchar`     |             |
| `total_return_pct`  | `numeric`     |             |
| `win_rate_pct`      | `numeric`     |             |
| `max_drawdown_pct`  | `numeric`     |             |
| `trade_count`       | `int4`        |             |
| `open_trade_count`  | `int4`        |             |
| `profit_factor`     | `numeric`     | Nullable    |
| `sharpe_ratio`      | `numeric`     | Nullable    |
| `avg_trade_pct`     | `numeric`     | Nullable    |
| `computed_at`       | `timestamptz` |             |

## Table `domain_events`

### Columns

| Name               | Type                    | Constraints |
| ------------------ | ----------------------- | ----------- |
| `event_id`         | `uuid`                  | Primary     |
| `event_type`       | `varchar`               |             |
| `schema_version`   | `int2`                  |             |
| `aggregate_type`   | `varchar`               |             |
| `aggregate_id`     | `uuid`                  |             |
| `correlation_id`   | `varchar`               | Nullable    |
| `payload`          | `jsonb`                 |             |
| `occurred_at`      | `timestamptz`           |             |
| `dispatch_status`  | `event_dispatch_status` |             |
| `attempt`          | `int2`                  |             |
| `max_attempts`     | `int2`                  |             |
| `claimed_by`       | `varchar`               | Nullable    |
| `claim_expires_at` | `timestamptz`           | Nullable    |
| `next_attempt_at`  | `timestamptz`           |             |
| `last_error`       | `text`                  | Nullable    |
| `delivered_at`     | `timestamptz`           | Nullable    |

## Table `refresh_tokens`

### Columns

| Name         | Type          | Constraints |
| ------------ | ------------- | ----------- |
| `id`         | `uuid`        | Primary     |
| `user_id`    | `uuid`        |             |
| `token_hash` | `bpchar`      | Unique      |
| `family_id`  | `uuid`        |             |
| `parent_id`  | `uuid`        | Nullable    |
| `expires_at` | `timestamptz` |             |
| `used_at`    | `timestamptz` | Nullable    |
| `revoked_at` | `timestamptz` | Nullable    |
| `created_at` | `timestamptz` |             |

## Table `user_quotas`

### Columns

| Name                         | Type   | Constraints |
| ---------------------------- | ------ | ----------- |
| `user_id`                    | `uuid` | Primary     |
| `max_concurrent_runs`        | `int4` |             |
| `max_candidates_per_run`     | `int4` |             |
| `max_candles_per_experiment` | `int4` |             |

## Table `candles`

### Columns

| Name          | Type             | Constraints |
| ------------- | ---------------- | ----------- |
| `provider`    | `varchar`        | Primary     |
| `symbol`      | `varchar`        | Primary     |
| `timeframe`   | `timeframe_enum` | Primary     |
| `open_time`   | `timestamptz`    | Primary     |
| `close_time`  | `timestamptz`    |             |
| `open`        | `numeric`        |             |
| `high`        | `numeric`        |             |
| `low`         | `numeric`        |             |
| `close`       | `numeric`        |             |
| `volume`      | `numeric`        |             |
| `trade_count` | `int4`           | Nullable    |

## Table `stream_checkpoints`

### Columns

| Name                   | Type             | Constraints |
| ---------------------- | ---------------- | ----------- |
| `provider`             | `varchar`        | Primary     |
| `symbol`               | `varchar`        | Primary     |
| `timeframe`            | `timeframe_enum` | Primary     |
| `last_closed_at`       | `timestamptz`    | Nullable    |
| `last_source_sequence` | `int8`           | Nullable    |
| `is_stale`             | `bool`           |             |
| `reconnect_count`      | `int4`           |             |
| `source_fetched_at`    | `timestamptz`    | Nullable    |
| `updated_at`           | `timestamptz`    |             |

## Table `search_runs`

### Columns

| Name                     | Type          | Constraints |
| ------------------------ | ------------- | ----------- |
| `id`                     | `uuid`        | Primary     |
| `owner_id`               | `uuid`        |             |
| `generator_id`           | `varchar`     |             |
| `status`                 | `varchar`     |             |
| `search_space`           | `jsonb`       |             |
| `stop_conditions`        | `jsonb`       |             |
| `market_dataset_id`      | `uuid`        |             |
| `seed`                   | `int8`        |             |
| `generated`              | `int4`        |             |
| `tested`                 | `int4`        |             |
| `failed`                 | `int4`        |             |
| `best_score`             | `numeric`     | Nullable    |
| `current_candidate_hash` | `bpchar`      | Nullable    |
| `stop_reason`            | `varchar`     | Nullable    |
| `idempotency_key`        | `varchar`     | Nullable    |
| `created_at`             | `timestamptz` |             |
| `updated_at`             | `timestamptz` |             |
| `non_improving`          | `int4`        |             |
| `dedup_hits`             | `int4`        |             |
| `generator_exhausted`    | `bool`        |             |
| `correlation_id`         | `varchar`     | Nullable    |

## Table `search_candidates`

### Columns

| Name                   | Type          | Constraints     |
| ---------------------- | ------------- | --------------- |
| `id`                   | `uuid`        | Primary         |
| `search_run_id`        | `uuid`        |                 |
| `ordinal`              | `int4`        |                 |
| `candidate_definition` | `jsonb`       |                 |
| `candidate_hash`       | `bpchar`      |                 |
| `generated_by`         | `varchar`     |                 |
| `generation_meta`      | `jsonb`       |                 |
| `experiment_id`        | `uuid`        | Nullable Unique |
| `created_at`           | `timestamptz` |                 |

## Table `search_actions`

### Columns

| Name             | Type          | Constraints |
| ---------------- | ------------- | ----------- |
| `command_id`     | `uuid`        | Primary     |
| `search_run_id`  | `uuid`        |             |
| `action`         | `varchar`     |             |
| `actor_id`       | `uuid`        |             |
| `requested_from` | `varchar`     |             |
| `resulted_in`    | `varchar`     |             |
| `created_at`     | `timestamptz` |             |

## Table `score_policies`

### Columns

| Name         | Type          | Constraints |
| ------------ | ------------- | ----------- |
| `version`    | `varchar`     | Primary     |
| `min_trades` | `int4`        |             |
| `weights`    | `jsonb`       |             |
| `formula`    | `text`        |             |
| `is_active`  | `bool`        |             |
| `created_at` | `timestamptz` |             |

## Table `leaderboard_entries`

### Columns

| Name                   | Type          | Constraints |
| ---------------------- | ------------- | ----------- |
| `id`                   | `uuid`        | Primary     |
| `evaluation_id`        | `uuid`        |             |
| `market_dataset_id`    | `uuid`        |             |
| `score_policy_version` | `varchar`     |             |
| `score`                | `numeric`     |             |
| `observed_at`          | `timestamptz` |             |

## Table `news_sources`

### Columns

| Name                | Type          | Constraints |
| ------------------- | ------------- | ----------- |
| `id`                | `uuid`        | Primary     |
| `source_key`        | `varchar`     | Unique      |
| `display_name`      | `varchar`     |             |
| `kind`              | `varchar`     |             |
| `allowed_origin`    | `text`        |             |
| `url_template`      | `text`        |             |
| `is_active`         | `bool`        |             |
| `last_collected_at` | `timestamptz` | Nullable    |
| `created_at`        | `timestamptz` |             |

## Table `news_collection_jobs`

### Columns

| Name             | Type          | Constraints |
| ---------------- | ------------- | ----------- |
| `id`             | `uuid`        | Primary     |
| `source_id`      | `uuid`        |             |
| `status`         | `varchar`     |             |
| `items_found`    | `int4`        |             |
| `items_new`      | `int4`        |             |
| `failure_reason` | `text`        | Nullable    |
| `started_at`     | `timestamptz` | Nullable    |
| `finished_at`    | `timestamptz` | Nullable    |
| `created_at`     | `timestamptz` |             |

## Table `news_items`

### Columns

| Name                 | Type          | Constraints |
| -------------------- | ------------- | ----------- |
| `id`                 | `uuid`        | Primary     |
| `source_id`          | `uuid`        |             |
| `canonical_url`      | `text`        |             |
| `url_hash`           | `bpchar`      | Unique      |
| `title`              | `text`        |             |
| `content_hash`       | `bpchar`      |             |
| `content`            | `text`        |             |
| `published_at`       | `timestamptz` |             |
| `related_coins`      | `_text`       |             |
| `created_at`         | `timestamptz` |             |
| `extraction_version` | `varchar`     |             |
| `tagging_version`    | `varchar`     |             |

## Table `sentiment_results`

### Columns

| Name            | Type          | Constraints |
| --------------- | ------------- | ----------- |
| `id`            | `uuid`        | Primary     |
| `news_item_id`  | `uuid`        |             |
| `label`         | `varchar`     |             |
| `score`         | `numeric`     |             |
| `model`         | `varchar`     |             |
| `model_version` | `varchar`     |             |
| `analyzed_at`   | `timestamptz` |             |

## Table `event_consumptions`

### Columns

| Name          | Type          | Constraints |
| ------------- | ------------- | ----------- |
| `event_id`    | `uuid`        | Primary     |
| `consumer_id` | `varchar`     | Primary     |
| `consumed_at` | `timestamptz` |             |

## Table `strategy_drafts`

### Columns

| Name               | Type          | Constraints |
| ------------------ | ------------- | ----------- |
| `id`               | `uuid`        | Primary     |
| `owner_id`         | `uuid`        |             |
| `source_type`      | `varchar`     |             |
| `source_ref`       | `text`        |             |
| `source_hash`      | `bpchar`      |             |
| `mode`             | `varchar`     |             |
| `name_hint`        | `varchar`     | Nullable    |
| `current_revision` | `int4`        |             |
| `status`           | `varchar`     |             |
| `idempotency_key`  | `varchar`     | Nullable    |
| `created_at`       | `timestamptz` |             |
| `updated_at`       | `timestamptz` |             |

## Table `strategy_draft_revisions`

### Columns

| Name         | Type          | Constraints |
| ------------ | ------------- | ----------- |
| `draft_id`   | `uuid`        | Primary     |
| `revision`   | `int4`        | Primary     |
| `spec_json`  | `jsonb`       |             |
| `spec_hash`  | `bpchar`      |             |
| `created_by` | `varchar`     |             |
| `created_at` | `timestamptz` |             |

## Table `agent_runs`

### Columns

| Name                  | Type          | Constraints |
| --------------------- | ------------- | ----------- |
| `id`                  | `uuid`        | Primary     |
| `draft_id`            | `uuid`        |             |
| `agent_type`          | `varchar`     |             |
| `state`               | `varchar`     |             |
| `model`               | `varchar`     |             |
| `model_version`       | `varchar`     |             |
| `prompt_hash`         | `bpchar`      |             |
| `tool_policy_version` | `varchar`     |             |
| `attempts_used`       | `int2`        |             |
| `created_at`          | `timestamptz` |             |

## Table `strategy_artifacts`

### Columns

| Name               | Type          | Constraints |
| ------------------ | ------------- | ----------- |
| `id`               | `uuid`        | Primary     |
| `draft_id`         | `uuid`        |             |
| `revision`         | `int4`        |             |
| `language`         | `varchar`     |             |
| `source_text`      | `text`        |             |
| `artifact_hash`    | `bpchar`      | Unique      |
| `compiler_version` | `varchar`     |             |
| `created_at`       | `timestamptz` |             |

## Table `sandbox_runs`

### Columns

| Name              | Type          | Constraints |
| ----------------- | ------------- | ----------- |
| `id`              | `uuid`        | Primary     |
| `artifact_id`     | `uuid`        |             |
| `policy_version`  | `varchar`     |             |
| `fixture_version` | `varchar`     |             |
| `status`          | `varchar`     |             |
| `report_json`     | `jsonb`       |             |
| `created_at`      | `timestamptz` |             |

## Table `strategy_approvals`

### Columns

| Name                  | Type          | Constraints |
| --------------------- | ------------- | ----------- |
| `id`                  | `uuid`        | Primary     |
| `draft_id`            | `uuid`        |             |
| `reviewer_id`         | `uuid`        |             |
| `revision`            | `int4`        |             |
| `spec_hash`           | `bpchar`      |             |
| `artifact_hash`       | `bpchar`      |             |
| `sandbox_report_hash` | `bpchar`      |             |
| `decision`            | `varchar`     |             |
| `reason`              | `varchar`     |             |
| `idempotency_key`     | `varchar`     | Nullable    |
| `created_at`          | `timestamptz` |             |

## Table `strategy_runtime_specs`

### Columns

| Name            | Type          | Constraints |
| --------------- | ------------- | ----------- |
| `strategy_id`   | `varchar`     | Primary     |
| `version`       | `varchar`     | Primary     |
| `spec_json`     | `jsonb`       |             |
| `artifact_hash` | `bpchar`      |             |
| `published_at`  | `timestamptz` |             |

## Table `news_documents`

### Columns

| Name                 | Type          | Constraints |
| -------------------- | ------------- | ----------- |
| `id`                 | `uuid`        | Primary     |
| `source_id`          | `uuid`        |             |
| `canonical_url`      | `text`        |             |
| `content_hash`       | `bpchar`      |             |
| `sanitized_document` | `text`        |             |
| `title_hint`         | `text`        |             |
| `published_at`       | `timestamptz` |             |
| `quality_reason`     | `varchar`     |             |
| `sanitizer_version`  | `varchar`     |             |
| `created_at`         | `timestamptz` |             |

## Table `news_extraction_attempts`

### Columns

| Name                     | Type          | Constraints |
| ------------------------ | ------------- | ----------- |
| `id`                     | `uuid`        | Primary     |
| `document_id`            | `uuid`        |             |
| `cache_key`              | `bpchar`      |             |
| `method`                 | `varchar`     |             |
| `status`                 | `varchar`     |             |
| `model`                  | `varchar`     | Nullable    |
| `model_version`          | `varchar`     | Nullable    |
| `prompt_version`         | `varchar`     |             |
| `schema_version`         | `varchar`     |             |
| `quality_policy_version` | `varchar`     |             |
| `result_json`            | `jsonb`       | Nullable    |
| `error_code`             | `varchar`     | Nullable    |
| `created_at`             | `timestamptz` |             |

## Custom Types / Enums

### `event_dispatch_status`

`pending` | `claimed` | `delivered` | `dead`

### `fill_policy_enum`

`bbo_limit`

### `job_status`

`queued` | `leased` | `completed` | `failed` | `cancelled`

### `open_position_policy_enum`

`last_executable_bbo`

### `position_policy_enum`

`one_net_position`

### `run_status`

`queued` | `running` | `completed` | `failed` | `cancelled`

### `signal_enum`

`BUY` | `SELL` | `HOLD`

### `timeframe_enum`

`1m` | `5m` | `15m` | `30m` | `1h` | `2h` | `4h` | `1d`

### `trade_side`

`LONG` | `SHORT`
