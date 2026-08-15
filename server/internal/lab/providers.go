package lab

import (
	"bytes"
	"context"
	"database/sql"
	"encoding/json"
	"encoding/xml"
	"fmt"
	"html"
	"io"
	"net/http"
	"net/url"
	"regexp"
	"sort"
	"strconv"
	"strings"
	"time"

	"github.com/google/uuid"
)

const (
	binanceFuturesKlinesURL = "https://fapi.binance.com/fapi/v1/klines"
	defaultSentimentModel   = "sentiment-v1"
	defaultSentimentVersion = "2026-08-01"
)

var providerHTTPClient = &http.Client{Timeout: 20 * time.Second}

func FetchBinanceCandles(ctx context.Context, provider, symbol, timeframe string, desired int) ([]Candle, error) {
	if provider != ProviderBinance {
		return nil, fmt.Errorf("unsupported provider %q", provider)
	}
	symbol = strings.ToUpper(strings.TrimSpace(symbol))
	if symbol != SymbolETHUSDT {
		return nil, fmt.Errorf("unsupported symbol %q", symbol)
	}
	if !validTimeframe(timeframe) {
		return nil, fmt.Errorf("unsupported timeframe %q", timeframe)
	}
	if desired <= 0 {
		desired = 180
	}
	limit := desired + 2
	if limit > 1500 {
		limit = 1500
	}

	u, _ := url.Parse(binanceFuturesKlinesURL)
	q := u.Query()
	q.Set("symbol", symbol)
	q.Set("interval", timeframe)
	q.Set("limit", strconv.Itoa(limit))
	u.RawQuery = q.Encode()

	req, err := http.NewRequestWithContext(ctx, http.MethodGet, u.String(), nil)
	if err != nil {
		return nil, err
	}
	req.Header.Set("Accept", "application/json")
	req.Header.Set("User-Agent", "CryptoBotResearchLab/0.1")

	res, err := providerHTTPClient.Do(req)
	if err != nil {
		return nil, err
	}
	defer res.Body.Close()
	if res.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(io.LimitReader(res.Body, 512))
		return nil, fmt.Errorf("binance returned status %d: %s", res.StatusCode, strings.TrimSpace(string(body)))
	}

	var raw [][]json.RawMessage
	if err := json.NewDecoder(res.Body).Decode(&raw); err != nil {
		return nil, err
	}

	now := time.Now().UTC()
	out := make([]Candle, 0, desired)
	for _, row := range raw {
		if len(row) < 9 {
			continue
		}
		openMs, err := rawInt64(row[0])
		if err != nil {
			return nil, fmt.Errorf("parse open time: %w", err)
		}
		openPrice, err := rawFloat(row[1])
		if err != nil {
			return nil, fmt.Errorf("parse open: %w", err)
		}
		high, err := rawFloat(row[2])
		if err != nil {
			return nil, fmt.Errorf("parse high: %w", err)
		}
		low, err := rawFloat(row[3])
		if err != nil {
			return nil, fmt.Errorf("parse low: %w", err)
		}
		closePrice, err := rawFloat(row[4])
		if err != nil {
			return nil, fmt.Errorf("parse close: %w", err)
		}
		volume, err := rawFloat(row[5])
		if err != nil {
			return nil, fmt.Errorf("parse volume: %w", err)
		}
		closeMs, err := rawInt64(row[6])
		if err != nil {
			return nil, fmt.Errorf("parse close time: %w", err)
		}
		trades, err := rawInt64(row[8])
		if err != nil {
			return nil, fmt.Errorf("parse trade count: %w", err)
		}
		closeTime := time.UnixMilli(closeMs).UTC()
		if closeTime.After(now) {
			continue
		}
		out = append(out, Candle{
			Provider: ProviderBinance, Symbol: symbol, Timeframe: timeframe,
			OpenTime: time.UnixMilli(openMs).UTC(), CloseTime: closeTime,
			Open: openPrice, High: high, Low: low, Close: closePrice, Volume: volume, TradeCount: int(trades),
		})
	}
	if len(out) > desired {
		out = out[len(out)-desired:]
	}
	return out, nil
}

func CollectApprovedNews(ctx context.Context, db *sql.DB) error {
	rows, err := db.QueryContext(ctx, `
		SELECT id, display_name, kind, allowed_origin, url_template
		FROM news_sources
		WHERE is_active
		ORDER BY source_key
	`)
	if err != nil {
		return err
	}
	defer rows.Close()

	var firstErr error
	for rows.Next() {
		var source newsSource
		if err := rows.Scan(&source.ID, &source.DisplayName, &source.Kind, &source.AllowedOrigin, &source.URLTemplate); err != nil {
			return err
		}
		found, inserted, err := collectNewsSource(ctx, db, source)
		if err != nil && firstErr == nil {
			firstErr = err
		}
		if err == nil {
			_, _ = db.ExecContext(ctx, `UPDATE news_sources SET last_collected_at=now() WHERE id=$1`, source.ID)
		}
		_ = found
		_ = inserted
	}
	if err := rows.Err(); err != nil {
		return err
	}
	return firstErr
}

func AnalyzeNewsSentiment(ctx context.Context, db *sql.DB, aiURL string) error {
	aiURL = strings.TrimRight(strings.TrimSpace(aiURL), "/")
	if aiURL == "" {
		return fmt.Errorf("AI_SERVICE_URL is required for news sentiment")
	}

	rows, err := db.QueryContext(ctx, `
		SELECT ni.id, ni.title, COALESCE(ni.content, '')
		FROM news_items ni
		WHERE NOT EXISTS (
			SELECT 1 FROM sentiment_results sr WHERE sr.news_item_id=ni.id
		)
		ORDER BY ni.published_at DESC
		LIMIT 50
	`)
	if err != nil {
		return err
	}
	defer rows.Close()

	analyzed := 0
	var firstErr error
	for rows.Next() {
		var itemID, title, content string
		if err := rows.Scan(&itemID, &title, &content); err != nil {
			return err
		}
		prediction, err := callSentimentService(ctx, aiURL, title+"\n\n"+content)
		if err != nil {
			if firstErr == nil {
				firstErr = err
			}
			continue
		}
		model := defaultString(prediction.Model, defaultSentimentModel)
		version := defaultString(prediction.ModelVersion, defaultSentimentVersion)
		if _, err := db.ExecContext(ctx, `
			INSERT INTO sentiment_results(id,news_item_id,label,score,model,model_version,analyzed_at)
			VALUES($1,$2,$3,$4,$5,$6,now())
			ON CONFLICT(news_item_id, model, model_version) DO UPDATE SET
				label=EXCLUDED.label,
				score=EXCLUDED.score,
				analyzed_at=EXCLUDED.analyzed_at
		`, uuid.NewString(), itemID, prediction.Label, prediction.Score, model, version); err != nil {
			return err
		}
		analyzed++
	}
	if err := rows.Err(); err != nil {
		return err
	}
	if analyzed == 0 && firstErr != nil {
		return firstErr
	}
	return nil
}

type newsSource struct {
	ID            string
	DisplayName   string
	Kind          string
	AllowedOrigin string
	URLTemplate   string
}

type rssFeed struct {
	Channel struct {
		Items []rssItem `xml:"item"`
	} `xml:"channel"`
	Entries []atomEntry `xml:"entry"`
}

type rssItem struct {
	Title       string `xml:"title"`
	Link        string `xml:"link"`
	GUID        string `xml:"guid"`
	Description string `xml:"description"`
	PubDate     string `xml:"pubDate"`
}

type atomEntry struct {
	Title     string     `xml:"title"`
	Links     []atomLink `xml:"link"`
	Summary   string     `xml:"summary"`
	Content   string     `xml:"content"`
	Published string     `xml:"published"`
	Updated   string     `xml:"updated"`
}

type atomLink struct {
	Rel  string `xml:"rel,attr"`
	Href string `xml:"href,attr"`
}

type collectedNewsItem struct {
	Title       string
	Link        string
	Content     string
	PublishedAt time.Time
	Coins       []string
}

type sentimentPrediction struct {
	Label        string  `json:"label"`
	Score        float64 `json:"score"`
	Model        string  `json:"model"`
	ModelVersion string  `json:"model_version"`
}

func collectNewsSource(ctx context.Context, db *sql.DB, source newsSource) (int, int, error) {
	jobID := uuid.NewString()
	if _, err := db.ExecContext(ctx, `
		INSERT INTO news_collection_jobs(id,source_id,status)
		VALUES($1,$2,'running')
	`, jobID, source.ID); err != nil {
		return 0, 0, err
	}

	items, err := fetchRSS(ctx, source)
	if err != nil {
		_, _ = db.ExecContext(ctx, `
			UPDATE news_collection_jobs
			SET status='failed', failure_reason=$1, finished_at=now()
			WHERE id=$2
		`, limitString(err.Error(), 600), jobID)
		return 0, 0, err
	}

	inserted := 0
	for _, item := range items {
		result, err := db.ExecContext(ctx, `
			INSERT INTO news_items(id,source_id,url,url_hash,title,content,published_at,related_coins)
			VALUES($1,$2,$3,$4,$5,$6,$7,$8::text[])
			ON CONFLICT(url_hash) DO UPDATE SET
				title=EXCLUDED.title,
				content=EXCLUDED.content,
				published_at=EXCLUDED.published_at,
				related_coins=EXCLUDED.related_coins
		`, uuid.NewString(), source.ID, item.Link, sha256Hex(item.Link), item.Title, item.Content, item.PublishedAt, pgTextArray(item.Coins))
		if err != nil {
			_, _ = db.ExecContext(ctx, `
				UPDATE news_collection_jobs
				SET status='failed', failure_reason=$1, items_found=$2, items_new=$3, finished_at=now()
				WHERE id=$4
			`, limitString(err.Error(), 600), len(items), inserted, jobID)
			return len(items), inserted, err
		}
		if count, _ := result.RowsAffected(); count > 0 {
			inserted++
		}
	}
	_, err = db.ExecContext(ctx, `
		UPDATE news_collection_jobs
		SET status='completed', items_found=$1, items_new=$2, finished_at=now()
		WHERE id=$3
	`, len(items), inserted, jobID)
	return len(items), inserted, err
}

func fetchRSS(ctx context.Context, source newsSource) ([]collectedNewsItem, error) {
	if strings.ToLower(source.Kind) != "rss" {
		return nil, fmt.Errorf("unsupported news source kind %q", source.Kind)
	}
	if err := validateSourceURL(source.URLTemplate, source.AllowedOrigin); err != nil {
		return nil, err
	}
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, source.URLTemplate, nil)
	if err != nil {
		return nil, err
	}
	req.Header.Set("Accept", "application/rss+xml, application/xml, text/xml")
	req.Header.Set("User-Agent", "CryptoBotResearchLab/0.1")
	res, err := providerHTTPClient.Do(req)
	if err != nil {
		return nil, err
	}
	defer res.Body.Close()
	if res.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(io.LimitReader(res.Body, 512))
		return nil, fmt.Errorf("news source returned status %d: %s", res.StatusCode, strings.TrimSpace(string(body)))
	}
	var feed rssFeed
	decoder := xml.NewDecoder(io.LimitReader(res.Body, 3*1024*1024))
	if err := decoder.Decode(&feed); err != nil {
		return nil, err
	}

	var items []collectedNewsItem
	for _, item := range feed.Channel.Items {
		link := canonicalNewsURL(defaultString(item.Link, item.GUID))
		published, ok := parseNewsTime(item.PubDate)
		title := cleanNewsText(item.Title)
		content := cleanNewsText(item.Description)
		if link == "" || title == "" || !ok {
			continue
		}
		items = append(items, collectedNewsItem{Title: title, Link: link, Content: content, PublishedAt: published, Coins: relatedCoins(title + " " + content)})
	}
	for _, entry := range feed.Entries {
		link := canonicalNewsURL(atomHref(entry.Links))
		published, ok := parseNewsTime(defaultString(entry.Published, entry.Updated))
		title := cleanNewsText(entry.Title)
		content := cleanNewsText(defaultString(entry.Summary, entry.Content))
		if link == "" || title == "" || !ok {
			continue
		}
		items = append(items, collectedNewsItem{Title: title, Link: link, Content: content, PublishedAt: published, Coins: relatedCoins(title + " " + content)})
	}
	return items, nil
}

func callSentimentService(ctx context.Context, aiURL, text string) (sentimentPrediction, error) {
	body, _ := json.Marshal(map[string]string{"text": text})
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, aiURL+"/predict", bytes.NewReader(body))
	if err != nil {
		return sentimentPrediction{}, err
	}
	req.Header.Set("Content-Type", "application/json")
	res, err := providerHTTPClient.Do(req)
	if err != nil {
		return sentimentPrediction{}, err
	}
	defer res.Body.Close()
	if res.StatusCode >= 300 {
		body, _ := io.ReadAll(io.LimitReader(res.Body, 512))
		return sentimentPrediction{}, fmt.Errorf("ai returned status %d: %s", res.StatusCode, strings.TrimSpace(string(body)))
	}
	var prediction sentimentPrediction
	if err := json.NewDecoder(res.Body).Decode(&prediction); err != nil {
		return sentimentPrediction{}, err
	}
	switch prediction.Label {
	case "POSITIVE", "NEUTRAL", "NEGATIVE":
	default:
		return sentimentPrediction{}, fmt.Errorf("ai returned invalid label %q", prediction.Label)
	}
	if prediction.Score < 0 || prediction.Score > 1 {
		return sentimentPrediction{}, fmt.Errorf("ai returned invalid score %.4f", prediction.Score)
	}
	return prediction, nil
}

func rawInt64(raw json.RawMessage) (int64, error) {
	var n int64
	if err := json.Unmarshal(raw, &n); err == nil {
		return n, nil
	}
	var s string
	if err := json.Unmarshal(raw, &s); err != nil {
		return 0, err
	}
	return strconv.ParseInt(s, 10, 64)
}

func rawFloat(raw json.RawMessage) (float64, error) {
	var s string
	if err := json.Unmarshal(raw, &s); err == nil {
		return strconv.ParseFloat(s, 64)
	}
	var f float64
	if err := json.Unmarshal(raw, &f); err != nil {
		return 0, err
	}
	return f, nil
}

func validTimeframe(tf string) bool {
	switch tf {
	case "1m", "5m", "15m", "1h", "4h":
		return true
	default:
		return false
	}
}

func validateSourceURL(rawURL, allowedOrigin string) error {
	u, err := url.Parse(rawURL)
	if err != nil {
		return err
	}
	origin, err := url.Parse(allowedOrigin)
	if err != nil {
		return err
	}
	if u.Scheme != "https" || origin.Scheme != "https" {
		return fmt.Errorf("news sources must use https")
	}
	if !strings.EqualFold(u.Host, origin.Host) {
		return fmt.Errorf("news source origin %q is not allowed", u.Host)
	}
	return nil
}

var htmlTagPattern = regexp.MustCompile(`(?s)<[^>]*>`)

func cleanNewsText(value string) string {
	value = html.UnescapeString(value)
	value = htmlTagPattern.ReplaceAllString(value, " ")
	value = strings.Join(strings.Fields(value), " ")
	return limitString(value, 1200)
}

func canonicalNewsURL(rawURL string) string {
	u, err := url.Parse(strings.TrimSpace(rawURL))
	if err != nil || u.Scheme == "" || u.Host == "" {
		return ""
	}
	q := u.Query()
	for key := range q {
		lower := strings.ToLower(key)
		if strings.HasPrefix(lower, "utm_") || lower == "fbclid" || lower == "gclid" || lower == "ref" {
			q.Del(key)
		}
	}
	u.Scheme = strings.ToLower(u.Scheme)
	u.Host = strings.ToLower(u.Host)
	u.RawQuery = q.Encode()
	u.Fragment = ""
	return u.String()
}

func parseNewsTime(value string) (time.Time, bool) {
	value = strings.TrimSpace(value)
	if value == "" {
		return time.Time{}, false
	}
	layouts := []string{
		time.RFC1123Z,
		time.RFC1123,
		time.RFC3339,
		"Mon, 02 Jan 2006 15:04:05 -0700",
		"Mon, 2 Jan 2006 15:04:05 -0700",
		"2006-01-02T15:04:05-07:00",
	}
	for _, layout := range layouts {
		if parsed, err := time.Parse(layout, value); err == nil {
			return parsed.UTC(), true
		}
	}
	return time.Time{}, false
}

func atomHref(links []atomLink) string {
	for _, link := range links {
		if link.Rel == "" || link.Rel == "alternate" {
			return link.Href
		}
	}
	if len(links) > 0 {
		return links[0].Href
	}
	return ""
}

func relatedCoins(text string) []string {
	lower := strings.ToLower(text)
	seen := map[string]bool{}
	add := func(symbol string) {
		seen[symbol] = true
	}
	if containsToken(lower, "eth") || strings.Contains(lower, "ethereum") || strings.Contains(lower, "ether") {
		add("ETH")
	}
	if containsToken(lower, "btc") || strings.Contains(lower, "bitcoin") {
		add("BTC")
	}
	if containsToken(lower, "sol") || strings.Contains(lower, "solana") {
		add("SOL")
	}
	if containsToken(lower, "usdt") || strings.Contains(lower, "tether") {
		add("USDT")
	}
	if len(seen) == 0 {
		return []string{}
	}
	coins := make([]string, 0, len(seen))
	for coin := range seen {
		coins = append(coins, coin)
	}
	sort.Strings(coins)
	return coins
}

func containsToken(text, token string) bool {
	for _, field := range strings.FieldsFunc(text, func(r rune) bool {
		return !(r >= 'a' && r <= 'z') && !(r >= '0' && r <= '9')
	}) {
		if field == token {
			return true
		}
	}
	return false
}

func pgTextArray(values []string) string {
	if len(values) == 0 {
		return "{}"
	}
	return "{" + strings.Join(values, ",") + "}"
}

func limitString(value string, maxLen int) string {
	if len(value) <= maxLen {
		return value
	}
	return value[:maxLen]
}
