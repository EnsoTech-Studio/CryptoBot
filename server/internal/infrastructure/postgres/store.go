package postgres

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"fmt"
	"sort"
	"strings"
	"time"

	"github.com/google/uuid"
	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	domainmarket "github.com/EnsoTech-Studio/CryptoBot/server/internal/domain/market"
)

var ErrNotFound = errors.New("not found")

type Store struct {
	pool *pgxpool.Pool
}

func NewStore(pool *pgxpool.Pool) *Store { return &Store{pool: pool} }

func (s *Store) Ready(ctx context.Context) error { return s.pool.Ping(ctx) }

func (s *Store) ListPairs(ctx context.Context) ([]domainmarket.Pair, error) {
	rows, err := s.pool.Query(
		ctx,
		`SELECT p.provider,p.symbol,p.base,p.quote,
		        ARRAY['1m','5m','15m','1h','4h','1d']::text[]
		 FROM market_pairs p
		 WHERE p.is_active
		 ORDER BY p.provider,p.symbol`,
	)
	if err != nil {
		return nil, fmt.Errorf("list market pairs: %w", err)
	}
	defer rows.Close()
	pairs := make([]domainmarket.Pair, 0)
	for rows.Next() {
		var pair domainmarket.Pair
		if err := rows.Scan(
			&pair.Provider, &pair.Symbol, &pair.BaseAsset, &pair.QuoteAsset, &pair.Timeframes,
		); err != nil {
			return nil, fmt.Errorf("scan market pair: %w", err)
		}
		pairs = append(pairs, pair)
	}
	return pairs, rows.Err()
}

func (s *Store) ListCandles(
	ctx context.Context, key domainmarket.MarketKey, limit int,
) ([]domainmarket.Candle, error) {
	if limit < 1 || limit > 1_000 {
		return nil, fmt.Errorf("candle limit must be 1..1000")
	}
	rows, err := s.pool.Query(
		ctx,
		`SELECT provider,symbol,timeframe,open_time,close_time,open,high,low,close,volume,trade_count
		 FROM (
		   SELECT provider,symbol,timeframe,open_time,close_time,open,high,low,close,volume,trade_count
		   FROM candles WHERE provider=$1 AND symbol=$2 AND timeframe=$3
		   ORDER BY open_time DESC LIMIT $4
		 ) recent ORDER BY open_time`,
		key.Provider, strings.ToUpper(key.Symbol), string(key.Timeframe), limit,
	)
	if err != nil {
		return nil, fmt.Errorf("list candles: %w", err)
	}
	return pgx.CollectRows(rows, func(row pgx.CollectableRow) (domainmarket.Candle, error) {
		var candle domainmarket.Candle
		err := row.Scan(
			&candle.Provider, &candle.Symbol, &candle.Timeframe, &candle.OpenTime,
			&candle.CloseTime, &candle.Open, &candle.High, &candle.Low, &candle.Close,
			&candle.Volume, &candle.TradeCount,
		)
		return candle, err
	})
}

func (s *Store) ListDatasets(
	ctx context.Context, key domainmarket.MarketKey, limit int,
) ([]domainmarket.Dataset, error) {
	if limit < 1 || limit > 100 {
		return nil, fmt.Errorf("dataset limit must be 1..100")
	}
	rows, err := s.pool.Query(
		ctx,
		`SELECT id,dataset_version,provider,symbol,timeframe,range_from,range_to,
		        revision_no,candle_count,content_hash,
		        COALESCE(bbo_content_hash,content_hash)
		 FROM market_datasets
		 WHERE provider=$1 AND symbol=$2 AND timeframe=$3
		 ORDER BY created_at DESC,id DESC LIMIT $4`,
		key.Provider, strings.ToUpper(key.Symbol), string(key.Timeframe), limit,
	)
	if err != nil {
		return nil, fmt.Errorf("list market datasets: %w", err)
	}
	return pgx.CollectRows(rows, func(row pgx.CollectableRow) (domainmarket.Dataset, error) {
		var dataset domainmarket.Dataset
		err := row.Scan(
			&dataset.ID, &dataset.DatasetVersion, &dataset.Market.Provider,
			&dataset.Market.Symbol, &dataset.Market.Timeframe, &dataset.RangeFrom,
			&dataset.RangeTo, &dataset.RevisionNo, &dataset.CandleCount,
			&dataset.ContentHash, &dataset.BBOContentHash,
		)
		return dataset, err
	})
}

func (s *Store) PersistClosedCandles(ctx context.Context, candles []domainmarket.Candle) error {
	if len(candles) == 0 {
		return nil
	}
	if len(candles) > 2_000 {
		return fmt.Errorf("closed candle batch exceeds 2000 rows")
	}
	tx, err := s.pool.Begin(ctx)
	if err != nil {
		return fmt.Errorf("begin candle batch: %w", err)
	}
	defer tx.Rollback(ctx)
	batch := &pgx.Batch{}
	for _, candle := range candles {
		batch.Queue(
			`INSERT INTO candles(provider,symbol,timeframe,open_time,close_time,open,high,low,close,volume,trade_count)
			 VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)
			 ON CONFLICT(provider,symbol,timeframe,open_time) DO UPDATE SET
			 close_time=EXCLUDED.close_time,open=EXCLUDED.open,high=EXCLUDED.high,
			 low=EXCLUDED.low,close=EXCLUDED.close,volume=EXCLUDED.volume,
			 trade_count=EXCLUDED.trade_count`,
			candle.Provider, strings.ToUpper(candle.Symbol), string(candle.Timeframe),
			candle.OpenTime, candle.CloseTime, candle.Open.String(), candle.High.String(),
			candle.Low.String(), candle.Close.String(), candle.Volume.String(), candle.TradeCount,
		)
	}
	results := tx.SendBatch(ctx, batch)
	for range candles {
		if _, err := results.Exec(); err != nil {
			results.Close()
			return fmt.Errorf("persist closed candle: %w", err)
		}
	}
	if err := results.Close(); err != nil {
		return fmt.Errorf("close candle batch: %w", err)
	}
	if err := tx.Commit(ctx); err != nil {
		return fmt.Errorf("commit candle batch: %w", err)
	}
	return nil
}

func (s *Store) LoadCheckpoint(
	ctx context.Context, key domainmarket.MarketKey,
) (domainmarket.Checkpoint, error) {
	checkpoint := domainmarket.Checkpoint{Market: key, IsStale: true}
	var lastClosed *time.Time
	var lastSequence *int64
	err := s.pool.QueryRow(
		ctx,
		`SELECT last_closed_at,last_source_sequence,is_stale,reconnect_count
		 FROM stream_checkpoints WHERE provider=$1 AND symbol=$2 AND timeframe=$3`,
		key.Provider, strings.ToUpper(key.Symbol), string(key.Timeframe),
	).Scan(&lastClosed, &lastSequence, &checkpoint.IsStale, &checkpoint.ReconnectCount)
	if errors.Is(err, pgx.ErrNoRows) {
		return checkpoint, nil
	}
	if err != nil {
		return checkpoint, fmt.Errorf("load stream checkpoint: %w", err)
	}
	checkpoint.LastClosedAt = lastClosed
	if lastSequence != nil && *lastSequence >= 0 {
		sequence := uint64(*lastSequence)
		checkpoint.LastSourceSequence = &sequence
	}
	return checkpoint, nil
}

func (s *Store) MarkStreamStale(
	ctx context.Context, key domainmarket.MarketKey, sequence uint64,
) error {
	_, err := s.pool.Exec(
		ctx,
		`INSERT INTO stream_checkpoints(provider,symbol,timeframe,last_source_sequence,is_stale,reconnect_count)
		 VALUES($1,$2,$3,$4,true,1)
		 ON CONFLICT(provider,symbol,timeframe) DO UPDATE SET
		 is_stale=true,reconnect_count=stream_checkpoints.reconnect_count+1,
		 last_source_sequence=GREATEST(stream_checkpoints.last_source_sequence,EXCLUDED.last_source_sequence),
		 updated_at=now()`,
		key.Provider, strings.ToUpper(key.Symbol), string(key.Timeframe), int64(sequence),
	)
	if err != nil {
		return fmt.Errorf("mark market stream stale: %w", err)
	}
	return nil
}

func (s *Store) MarkStreamRecovered(
	ctx context.Context, key domainmarket.MarketKey, lastClosed time.Time, sequence uint64,
) error {
	_, err := s.pool.Exec(
		ctx,
		`INSERT INTO stream_checkpoints(provider,symbol,timeframe,last_closed_at,last_source_sequence,is_stale,source_fetched_at)
		 VALUES($1,$2,$3,$4,$5,false,now())
		 ON CONFLICT(provider,symbol,timeframe) DO UPDATE SET
		 last_closed_at=GREATEST(stream_checkpoints.last_closed_at,EXCLUDED.last_closed_at),
		 last_source_sequence=GREATEST(stream_checkpoints.last_source_sequence,EXCLUDED.last_source_sequence),
		 is_stale=false,source_fetched_at=now(),updated_at=now()`,
		key.Provider, strings.ToUpper(key.Symbol), string(key.Timeframe), lastClosed, int64(sequence),
	)
	if err != nil {
		return fmt.Errorf("mark market stream recovered: %w", err)
	}
	return nil
}

func (s *Store) CreateDataset(
	ctx context.Context,
	key domainmarket.MarketKey,
	from time.Time,
	to time.Time,
	revision int,
	quotes []domainmarket.BBO,
) (domainmarket.Dataset, error) {
	if !to.After(from) || revision < 1 || len(quotes) == 0 {
		return domainmarket.Dataset{}, fmt.Errorf("invalid immutable dataset request")
	}
	tx, err := s.pool.Begin(ctx)
	if err != nil {
		return domainmarket.Dataset{}, err
	}
	defer tx.Rollback(ctx)
	rows, err := tx.Query(
		ctx,
		`SELECT provider,symbol,timeframe,open_time,close_time,open,high,low,close,volume,trade_count
		 FROM candles WHERE provider=$1 AND symbol=$2 AND timeframe=$3
		 AND open_time >= $4 AND close_time <= $5 ORDER BY open_time`,
		key.Provider, strings.ToUpper(key.Symbol), string(key.Timeframe), from, to,
	)
	if err != nil {
		return domainmarket.Dataset{}, fmt.Errorf("read dataset candles: %w", err)
	}
	candles, err := pgx.CollectRows(rows, func(row pgx.CollectableRow) (domainmarket.Candle, error) {
		var candle domainmarket.Candle
		err := row.Scan(
			&candle.Provider, &candle.Symbol, &candle.Timeframe, &candle.OpenTime,
			&candle.CloseTime, &candle.Open, &candle.High, &candle.Low, &candle.Close,
			&candle.Volume, &candle.TradeCount,
		)
		return candle, err
	})
	if err != nil {
		return domainmarket.Dataset{}, fmt.Errorf("scan dataset candles: %w", err)
	}
	if len(candles) == 0 || len(candles) > 20_000 {
		return domainmarket.Dataset{}, fmt.Errorf("dataset candle count must be 1..20000")
	}
	sort.Slice(quotes, func(i, j int) bool {
		if quotes[i].EventTime.Equal(quotes[j].EventTime) {
			return quotes[i].SourceSequence < quotes[j].SourceSequence
		}
		return quotes[i].EventTime.Before(quotes[j].EventTime)
	})
	candleHash := hashCandles(candles)
	quoteHash := hashQuotes(quotes)
	datasetVersion := fmt.Sprintf(
		"%s:%s:%s:%d:%d:r%d:%s",
		key.Provider, strings.ToUpper(key.Symbol), key.Timeframe,
		from.UTC().UnixMilli(), to.UTC().UnixMilli(), revision, candleHash[:16],
	)
	var datasetID uuid.UUID
	err = tx.QueryRow(
		ctx,
		`INSERT INTO market_datasets(dataset_version,provider,symbol,timeframe,range_from,range_to,
		 revision_no,candle_count,content_hash,bbo_content_hash)
		 VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)
		 ON CONFLICT(dataset_version) DO NOTHING
		 RETURNING id`,
		datasetVersion, key.Provider, strings.ToUpper(key.Symbol), string(key.Timeframe),
		from, to, revision, len(candles), candleHash, quoteHash,
	).Scan(&datasetID)
	if errors.Is(err, pgx.ErrNoRows) {
		err = tx.QueryRow(
			ctx, "SELECT id FROM market_datasets WHERE dataset_version=$1", datasetVersion,
		).Scan(&datasetID)
	}
	if err != nil {
		return domainmarket.Dataset{}, fmt.Errorf("insert market dataset: %w", err)
	}
	for _, candle := range candles {
		if _, err := tx.Exec(
			ctx,
			`INSERT INTO market_dataset_candles(market_dataset_id,open_time,close_time,open,high,low,close,volume,trade_count)
			 VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9) ON CONFLICT DO NOTHING`,
			datasetID, candle.OpenTime, candle.CloseTime, candle.Open.String(), candle.High.String(),
			candle.Low.String(), candle.Close.String(), candle.Volume.String(), candle.TradeCount,
		); err != nil {
			return domainmarket.Dataset{}, fmt.Errorf("insert dataset candle: %w", err)
		}
	}
	for _, quote := range quotes {
		if quote.EventTime.Before(from) || quote.EventTime.After(to) {
			continue
		}
		if _, err := tx.Exec(
			ctx,
			`INSERT INTO market_dataset_bbo(market_dataset_id,event_time,source_sequence,bid,bid_qty,ask,ask_qty,update_id)
			 VALUES($1,$2,$3,$4,$5,$6,$7,$8) ON CONFLICT DO NOTHING`,
			datasetID, quote.EventTime, int64(quote.SourceSequence), quote.Bid.String(),
			quote.BidQty.String(), quote.Ask.String(), quote.AskQty.String(), quote.UpdateID,
		); err != nil {
			return domainmarket.Dataset{}, fmt.Errorf("insert dataset BBO: %w", err)
		}
	}
	if err := tx.Commit(ctx); err != nil {
		return domainmarket.Dataset{}, fmt.Errorf("commit market dataset: %w", err)
	}
	return domainmarket.Dataset{
		ID: datasetID.String(), DatasetVersion: datasetVersion, Market: key,
		RangeFrom: from, RangeTo: to, RevisionNo: revision, CandleCount: len(candles),
		ContentHash: candleHash, BBOContentHash: quoteHash,
	}, nil
}

func hashCandles(candles []domainmarket.Candle) string {
	hash := sha256.New()
	for _, candle := range candles {
		fmt.Fprintf(
			hash, "%s|%s|%s|%d|%d|%s|%s|%s|%s|%s|",
			candle.Provider, strings.ToUpper(candle.Symbol), candle.Timeframe,
			candle.OpenTime.UTC().UnixMilli(), candle.CloseTime.UTC().UnixMilli(),
			candle.Open.String(), candle.High.String(), candle.Low.String(), candle.Close.String(),
			candle.Volume.String(),
		)
		if candle.TradeCount != nil {
			fmt.Fprint(hash, *candle.TradeCount)
		}
		fmt.Fprintln(hash)
	}
	return hex.EncodeToString(hash.Sum(nil))
}

func hashQuotes(quotes []domainmarket.BBO) string {
	hash := sha256.New()
	for _, quote := range quotes {
		fmt.Fprintf(
			hash, "%s|%s|%d|%d|%s|%s|%s|%s|",
			quote.Provider, strings.ToUpper(quote.Symbol), quote.EventTime.UTC().UnixMilli(),
			quote.SourceSequence, quote.Bid.String(), quote.BidQty.String(),
			quote.Ask.String(), quote.AskQty.String(),
		)
		if quote.UpdateID != nil {
			fmt.Fprint(hash, *quote.UpdateID)
		}
		fmt.Fprintln(hash)
	}
	return hex.EncodeToString(hash.Sum(nil))
}
