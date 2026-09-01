package research

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"strings"
	"sync"
	"time"
)

var (
	ErrUnavailable      = errors.New("research service unavailable")
	ErrResponseTooLarge = errors.New("research response exceeds configured limit")
)

type Response struct {
	StatusCode         int
	ContentType        string
	ContentDisposition string
	Body               []byte
}

type StreamResponse struct {
	StatusCode         int
	ContentType        string
	ContentDisposition string
	Body               io.ReadCloser
}

type Client struct {
	baseURL      *url.URL
	token        string
	httpClient   *http.Client
	maxBodyBytes int64
	mu           sync.Mutex
	failures     int
	openUntil    time.Time
}

func NewClient(baseURL, token string, httpClient *http.Client, maxBodyBytes int64) (*Client, error) {
	parsed, err := url.Parse(strings.TrimRight(strings.TrimSpace(baseURL), "/"))
	if err != nil || parsed.Scheme == "" || parsed.Host == "" {
		return nil, fmt.Errorf("invalid research service URL")
	}
	if parsed.Scheme != "http" && parsed.Scheme != "https" {
		return nil, fmt.Errorf("research service URL must use http or https")
	}
	if strings.TrimSpace(token) == "" {
		return nil, fmt.Errorf("internal service token is required")
	}
	if httpClient == nil {
		httpClient = http.DefaultClient
	}
	if maxBodyBytes <= 0 {
		return nil, fmt.Errorf("research response limit must be positive")
	}
	return &Client{
		baseURL:      parsed,
		token:        token,
		httpClient:   httpClient,
		maxBodyBytes: maxBodyBytes,
	}, nil
}

func (c *Client) Call(
	ctx context.Context,
	method string,
	path string,
	query url.Values,
	body any,
	requestID string,
	userID string,
	userRole string,
) (Response, error) {
	return c.CallWithMetadata(
		ctx, method, path, query, body, requestID, userID, userRole, "", requestID,
	)
}

// StreamWithMetadata forwards a trusted service download without buffering its body.
func (c *Client) StreamWithMetadata(
	ctx context.Context,
	method string,
	path string,
	query url.Values,
	requestID string,
	userID string,
	userRole string,
	correlationID string,
) (StreamResponse, error) {
	c.mu.Lock()
	if time.Now().Before(c.openUntil) {
		c.mu.Unlock()
		return StreamResponse{}, ErrUnavailable
	}
	c.mu.Unlock()
	target := *c.baseURL
	target.Path = strings.TrimRight(c.baseURL.Path, "/") + "/" + strings.TrimLeft(path, "/")
	target.RawQuery = query.Encode()
	req, err := http.NewRequestWithContext(ctx, method, target.String(), nil)
	if err != nil {
		return StreamResponse{}, fmt.Errorf("build research request: %w", err)
	}
	req.Header.Set("Authorization", "Bearer "+c.token)
	req.Header.Set("Accept", "text/csv")
	if requestID != "" {
		req.Header.Set("X-Request-ID", requestID)
	}
	if userID != "" {
		req.Header.Set("X-User-ID", userID)
	}
	if userRole != "" {
		req.Header.Set("X-User-Role", userRole)
	}
	if correlationID != "" {
		req.Header.Set("X-Correlation-ID", correlationID)
	}
	resp, err := c.httpClient.Do(req)
	if err != nil {
		c.recordResult(err)
		return StreamResponse{}, fmt.Errorf("%w: %v", ErrUnavailable, err)
	}
	if resp.StatusCode == http.StatusBadGateway || resp.StatusCode == http.StatusServiceUnavailable || resp.StatusCode == http.StatusGatewayTimeout {
		c.recordResult(ErrUnavailable)
	} else {
		c.recordResult(nil)
	}
	return StreamResponse{
		StatusCode:         resp.StatusCode,
		ContentType:        resp.Header.Get("Content-Type"),
		ContentDisposition: resp.Header.Get("Content-Disposition"),
		Body:               resp.Body,
	}, nil
}

func (c *Client) ChartOverlayDelta(ctx context.Context, key string) (map[string]any, error) {
	parts := strings.Split(key, "|")
	if len(parts) != 5 || parts[0] == "" || parts[1] == "" || parts[2] == "" || parts[3] == "" || parts[4] == "" {
		return nil, fmt.Errorf("invalid chart overlay subscription key")
	}
	response, err := c.Call(
		ctx, http.MethodGet, "/api/v1/markets/chart-overlays/delta",
		url.Values{
			"provider":    {parts[0]},
			"symbol":      {parts[1]},
			"timeframe":   {parts[2]},
			"strategy":    {parts[3]},
			"config_hash": {parts[4]},
		}, nil, "", "", "",
	)
	if err != nil {
		return nil, err
	}
	if response.StatusCode < http.StatusOK || response.StatusCode >= http.StatusMultipleChoices {
		return nil, fmt.Errorf("chart overlay delta returned status %d", response.StatusCode)
	}
	var payload map[string]any
	if err := json.Unmarshal(response.Body, &payload); err != nil {
		return nil, fmt.Errorf("decode chart overlay delta: %w", err)
	}
	return payload, nil
}

func (c *Client) CallWithMetadata(
	ctx context.Context,
	method string,
	path string,
	query url.Values,
	body any,
	requestID string,
	userID string,
	userRole string,
	idempotencyKey string,
	correlationID string,
) (Response, error) {
	c.mu.Lock()
	if time.Now().Before(c.openUntil) {
		c.mu.Unlock()
		return Response{}, ErrUnavailable
	}
	c.mu.Unlock()
	response, err := c.callOnce(
		ctx, method, path, query, body, requestID, userID, userRole,
		idempotencyKey, correlationID,
	)
	if err != nil && (method == http.MethodGet || method == http.MethodHead || idempotencyKey != "") {
		response, err = c.callOnce(
			ctx, method, path, query, body, requestID, userID, userRole,
			idempotencyKey, correlationID,
		)
	}
	if err != nil && response.StatusCode != 0 {
		c.recordResult(nil)
		return response, nil
	}
	c.recordResult(err)
	return response, err
}

func (c *Client) callOnce(
	ctx context.Context,
	method string,
	path string,
	query url.Values,
	body any,
	requestID string,
	userID string,
	userRole string,
	idempotencyKey string,
	correlationID string,
) (Response, error) {
	target := *c.baseURL
	target.Path = strings.TrimRight(c.baseURL.Path, "/") + "/" + strings.TrimLeft(path, "/")
	target.RawQuery = query.Encode()

	var payload io.Reader
	if body != nil {
		encoded, err := json.Marshal(body)
		if err != nil {
			return Response{}, fmt.Errorf("encode research request: %w", err)
		}
		if int64(len(encoded)) > c.maxBodyBytes {
			return Response{}, ErrResponseTooLarge
		}
		payload = bytes.NewReader(encoded)
	}
	req, err := http.NewRequestWithContext(ctx, method, target.String(), payload)
	if err != nil {
		return Response{}, fmt.Errorf("build research request: %w", err)
	}
	req.Header.Set("Authorization", "Bearer "+c.token)
	req.Header.Set("Accept", "application/json")
	if body != nil {
		req.Header.Set("Content-Type", "application/json")
	}
	if requestID != "" {
		req.Header.Set("X-Request-ID", requestID)
	}
	if userID != "" {
		req.Header.Set("X-User-ID", userID)
	}
	if userRole != "" {
		req.Header.Set("X-User-Role", userRole)
	}
	if idempotencyKey != "" {
		req.Header.Set("Idempotency-Key", idempotencyKey)
	}
	if correlationID != "" {
		req.Header.Set("X-Correlation-ID", correlationID)
	}

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return Response{}, fmt.Errorf("%w: %v", ErrUnavailable, err)
	}
	defer resp.Body.Close()
	limited := io.LimitReader(resp.Body, c.maxBodyBytes+1)
	responseBody, err := io.ReadAll(limited)
	if err != nil {
		return Response{}, fmt.Errorf("read research response: %w", err)
	}
	if int64(len(responseBody)) > c.maxBodyBytes {
		return Response{}, ErrResponseTooLarge
	}
	result := Response{
		StatusCode:         resp.StatusCode,
		ContentType:        resp.Header.Get("Content-Type"),
		ContentDisposition: resp.Header.Get("Content-Disposition"),
		Body:               responseBody,
	}
	if resp.StatusCode == http.StatusBadGateway || resp.StatusCode == http.StatusServiceUnavailable ||
		resp.StatusCode == http.StatusGatewayTimeout {
		return result, ErrUnavailable
	}
	return result, nil
}

func (c *Client) recordResult(err error) {
	c.mu.Lock()
	defer c.mu.Unlock()
	if err == nil {
		c.failures = 0
		c.openUntil = time.Time{}
		return
	}
	c.failures++
	if c.failures >= 5 {
		c.openUntil = time.Now().Add(15 * time.Second)
		c.failures = 0
	}
}
