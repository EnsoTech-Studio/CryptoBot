package auth

import (
	"context"
	"crypto"
	"crypto/rand"
	"crypto/rsa"
	"crypto/sha256"
	"crypto/subtle"
	"crypto/x509"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"encoding/pem"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"sync"
	"time"

	"github.com/google/uuid"
	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
	"golang.org/x/crypto/argon2"
)

var (
	ErrInvalidCredentials = errors.New("invalid credentials")
	ErrInvalidSession     = errors.New("invalid session")
	ErrRefreshReuse       = errors.New("refresh token reuse detected")
	ErrEmailExists        = errors.New("email already registered")
	ErrRateLimited        = errors.New("rate limit exceeded")
)

const (
	accessTTL  = 15 * time.Minute
	refreshTTL = 30 * 24 * time.Hour
)

type Session struct {
	AccessToken  string
	RefreshToken string
	AccessTTL    time.Duration
	RefreshTTL   time.Duration
}

type Signer struct {
	private  *rsa.PrivateKey
	keyID    string
	issuer   string
	audience string
	now      func() time.Time
}

func LoadOrCreateSigner(path, issuer, audience string) (*Signer, error) {
	if strings.TrimSpace(path) == "" {
		return nil, fmt.Errorf("JWT private key path is required")
	}
	key, err := readPrivateKey(path)
	if errors.Is(err, os.ErrNotExist) {
		if err := os.MkdirAll(filepath.Dir(path), 0o700); err != nil {
			return nil, fmt.Errorf("create JWT key directory: %w", err)
		}
		key, err = rsa.GenerateKey(rand.Reader, 3072)
		if err != nil {
			return nil, fmt.Errorf("generate JWT key: %w", err)
		}
		encoded := pem.EncodeToMemory(&pem.Block{Type: "RSA PRIVATE KEY", Bytes: x509.MarshalPKCS1PrivateKey(key)})
		file, openErr := os.OpenFile(path, os.O_WRONLY|os.O_CREATE|os.O_EXCL, 0o600)
		if errors.Is(openErr, os.ErrExist) {
			key, err = readPrivateKey(path)
		} else if openErr != nil {
			return nil, fmt.Errorf("create JWT private key: %w", openErr)
		} else {
			if _, writeErr := file.Write(encoded); writeErr != nil {
				file.Close()
				return nil, fmt.Errorf("write JWT private key: %w", writeErr)
			}
			err = file.Close()
		}
	}
	if err != nil {
		return nil, err
	}
	publicDER, err := x509.MarshalPKIXPublicKey(&key.PublicKey)
	if err != nil {
		return nil, err
	}
	fingerprint := sha256.Sum256(publicDER)
	return &Signer{
		private: key, keyID: hex.EncodeToString(fingerprint[:8]), issuer: issuer,
		audience: audience, now: time.Now,
	}, nil
}

func readPrivateKey(path string) (*rsa.PrivateKey, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	block, _ := pem.Decode(data)
	if block == nil {
		return nil, fmt.Errorf("JWT key file is not PEM")
	}
	if key, err := x509.ParsePKCS1PrivateKey(block.Bytes); err == nil {
		return key, nil
	}
	parsed, err := x509.ParsePKCS8PrivateKey(block.Bytes)
	if err != nil {
		return nil, fmt.Errorf("parse JWT private key: %w", err)
	}
	key, ok := parsed.(*rsa.PrivateKey)
	if !ok {
		return nil, fmt.Errorf("JWT private key must be RSA")
	}
	return key, nil
}

func (s *Signer) Issue(principal Principal, ttl time.Duration) (string, error) {
	now := s.now().UTC()
	header, _ := json.Marshal(map[string]any{"alg": "RS256", "typ": "JWT", "kid": s.keyID})
	claims, _ := json.Marshal(map[string]any{
		"sub": principal.UserID.String(), "email": principal.Email,
		"display_name": principal.DisplayName, "role": principal.Role,
		"jti": uuid.NewString(), "iss": s.issuer, "aud": s.audience,
		"iat": now.Unix(), "nbf": now.Add(-5 * time.Second).Unix(), "exp": now.Add(ttl).Unix(),
	})
	unsigned := rawURL(header) + "." + rawURL(claims)
	digest := sha256.Sum256([]byte(unsigned))
	signature, err := rsa.SignPKCS1v15(rand.Reader, s.private, crypto.SHA256, digest[:])
	if err != nil {
		return "", err
	}
	return unsigned + "." + rawURL(signature), nil
}

func (s *Signer) Verify(token string) (uuid.UUID, error) {
	parts := strings.Split(token, ".")
	if len(parts) != 3 {
		return uuid.Nil, ErrInvalidSession
	}
	headerBytes, err := base64.RawURLEncoding.DecodeString(parts[0])
	if err != nil {
		return uuid.Nil, ErrInvalidSession
	}
	var header struct{ Alg, Kid string }
	if json.Unmarshal(headerBytes, &header) != nil || header.Alg != "RS256" || header.Kid != s.keyID {
		return uuid.Nil, ErrInvalidSession
	}
	signature, err := base64.RawURLEncoding.DecodeString(parts[2])
	if err != nil {
		return uuid.Nil, ErrInvalidSession
	}
	digest := sha256.Sum256([]byte(parts[0] + "." + parts[1]))
	if rsa.VerifyPKCS1v15(&s.private.PublicKey, crypto.SHA256, digest[:], signature) != nil {
		return uuid.Nil, ErrInvalidSession
	}
	payload, err := base64.RawURLEncoding.DecodeString(parts[1])
	if err != nil {
		return uuid.Nil, ErrInvalidSession
	}
	var claims struct {
		Subject   string `json:"sub"`
		Issuer    string `json:"iss"`
		Audience  string `json:"aud"`
		Expires   int64  `json:"exp"`
		NotBefore int64  `json:"nbf"`
	}
	if json.Unmarshal(payload, &claims) != nil || claims.Issuer != s.issuer ||
		claims.Audience != s.audience || s.now().Unix() >= claims.Expires ||
		s.now().Unix() < claims.NotBefore {
		return uuid.Nil, ErrInvalidSession
	}
	userID, err := uuid.Parse(claims.Subject)
	if err != nil {
		return uuid.Nil, ErrInvalidSession
	}
	return userID, nil
}

type Service struct {
	pool   *pgxpool.Pool
	signer *Signer
}

func NewService(pool *pgxpool.Pool, signer *Signer) *Service {
	return &Service{pool: pool, signer: signer}
}

func (s *Service) Register(
	ctx context.Context, email, password, displayName string,
) (Principal, Session, error) {
	email = strings.ToLower(strings.TrimSpace(email))
	displayName = strings.TrimSpace(displayName)
	if !strings.Contains(email, "@") || len(email) > 255 || len(password) < 12 || len(password) > 256 {
		return Principal{}, Session{}, ErrInvalidCredentials
	}
	if displayName == "" {
		displayName = strings.Split(email, "@")[0]
	}
	passwordHash, err := hashPassword(password)
	if err != nil {
		return Principal{}, Session{}, err
	}
	principal := Principal{
		UserID: uuid.New(), Email: email, DisplayName: displayName,
		Role: RoleResearcher, Active: true,
	}
	tx, err := s.pool.Begin(ctx)
	if err != nil {
		return Principal{}, Session{}, err
	}
	defer tx.Rollback(ctx)
	_, err = tx.Exec(
		ctx,
		`INSERT INTO users(id,email,password_hash,display_name,role,is_active)
		 VALUES($1,$2,$3,$4,$5,true)`,
		principal.UserID, email, passwordHash, displayName, principal.Role,
	)
	if err != nil {
		if strings.Contains(err.Error(), "users_email_key") {
			return Principal{}, Session{}, ErrEmailExists
		}
		return Principal{}, Session{}, err
	}
	_, err = tx.Exec(ctx, `INSERT INTO user_quotas(user_id) VALUES($1)`, principal.UserID)
	if err != nil {
		return Principal{}, Session{}, err
	}
	session, err := s.issueSession(ctx, tx, principal, uuid.New(), nil)
	if err != nil {
		return Principal{}, Session{}, err
	}
	if err := tx.Commit(ctx); err != nil {
		return Principal{}, Session{}, err
	}
	return principal, session, nil
}

func (s *Service) Login(ctx context.Context, email, password string) (Principal, Session, error) {
	var principal Principal
	var passwordHash string
	err := s.pool.QueryRow(
		ctx,
		`SELECT id,email,display_name,role,is_active,password_hash FROM users WHERE lower(email)=lower($1)`,
		strings.TrimSpace(email),
	).Scan(
		&principal.UserID, &principal.Email, &principal.DisplayName, &principal.Role,
		&principal.Active, &passwordHash,
	)
	if err != nil || !principal.Active || !verifyPassword(passwordHash, password) {
		// Equal-cost dummy check reduces account-enumeration timing differences.
		_, _ = hashPassword(password)
		return Principal{}, Session{}, ErrInvalidCredentials
	}
	if !strings.HasPrefix(passwordHash, "$argon2id$") {
		upgraded, hashErr := hashPassword(password)
		if hashErr == nil {
			_, _ = s.pool.Exec(ctx, `UPDATE users SET password_hash=$1 WHERE id=$2`, upgraded, principal.UserID)
		}
	}
	tx, err := s.pool.Begin(ctx)
	if err != nil {
		return Principal{}, Session{}, err
	}
	defer tx.Rollback(ctx)
	session, err := s.issueSession(ctx, tx, principal, uuid.New(), nil)
	if err != nil {
		return Principal{}, Session{}, err
	}
	if err := tx.Commit(ctx); err != nil {
		return Principal{}, Session{}, err
	}
	return principal, session, nil
}

func (s *Service) Authenticate(ctx context.Context, accessToken string) (Principal, error) {
	userID, err := s.signer.Verify(accessToken)
	if err != nil {
		return Principal{}, ErrInvalidSession
	}
	return s.loadPrincipal(ctx, s.pool, userID)
}

func (s *Service) Rotate(ctx context.Context, refreshToken string) (Principal, Session, error) {
	tokenHash := tokenDigest(refreshToken)
	tx, err := s.pool.Begin(ctx)
	if err != nil {
		return Principal{}, Session{}, err
	}
	defer tx.Rollback(ctx)
	var tokenID, userID, familyID uuid.UUID
	var expiresAt time.Time
	var usedAt, revokedAt *time.Time
	err = tx.QueryRow(
		ctx,
		`SELECT id,user_id,family_id,expires_at,used_at,revoked_at
		 FROM refresh_tokens WHERE token_hash=$1 FOR UPDATE`,
		tokenHash,
	).Scan(&tokenID, &userID, &familyID, &expiresAt, &usedAt, &revokedAt)
	if err != nil {
		return Principal{}, Session{}, ErrInvalidSession
	}
	if usedAt != nil || revokedAt != nil {
		_, _ = tx.Exec(ctx, `UPDATE refresh_tokens SET revoked_at=COALESCE(revoked_at,now()) WHERE family_id=$1`, familyID)
		_ = tx.Commit(ctx)
		return Principal{}, Session{}, ErrRefreshReuse
	}
	if !expiresAt.After(time.Now().UTC()) {
		return Principal{}, Session{}, ErrInvalidSession
	}
	principal, err := s.loadPrincipal(ctx, tx, userID)
	if err != nil {
		return Principal{}, Session{}, err
	}
	if _, err := tx.Exec(ctx, `UPDATE refresh_tokens SET used_at=now() WHERE id=$1`, tokenID); err != nil {
		return Principal{}, Session{}, err
	}
	session, err := s.issueSession(ctx, tx, principal, familyID, &tokenID)
	if err != nil {
		return Principal{}, Session{}, err
	}
	if err := tx.Commit(ctx); err != nil {
		return Principal{}, Session{}, err
	}
	return principal, session, nil
}

func (s *Service) Logout(ctx context.Context, refreshToken string) error {
	if strings.TrimSpace(refreshToken) == "" {
		return nil
	}
	_, err := s.pool.Exec(
		ctx,
		`UPDATE refresh_tokens SET revoked_at=COALESCE(revoked_at,now())
		 WHERE family_id=(SELECT family_id FROM refresh_tokens WHERE token_hash=$1)`,
		tokenDigest(refreshToken),
	)
	return err
}

type principalQuerier interface {
	QueryRow(context.Context, string, ...any) pgx.Row
}

func (s *Service) loadPrincipal(
	ctx context.Context, querier principalQuerier, userID uuid.UUID,
) (Principal, error) {
	var principal Principal
	err := querier.QueryRow(
		ctx,
		`SELECT id,email,display_name,role,is_active FROM users WHERE id=$1`, userID,
	).Scan(&principal.UserID, &principal.Email, &principal.DisplayName, &principal.Role, &principal.Active)
	if err != nil || !principal.Active {
		return Principal{}, ErrInvalidSession
	}
	return principal, nil
}

func (s *Service) issueSession(
	ctx context.Context,
	tx pgx.Tx,
	principal Principal,
	familyID uuid.UUID,
	parentID *uuid.UUID,
) (Session, error) {
	accessToken, err := s.signer.Issue(principal, accessTTL)
	if err != nil {
		return Session{}, err
	}
	rawRefresh := make([]byte, 32)
	if _, err := rand.Read(rawRefresh); err != nil {
		return Session{}, err
	}
	refreshToken := base64.RawURLEncoding.EncodeToString(rawRefresh)
	_, err = tx.Exec(
		ctx,
		`INSERT INTO refresh_tokens(user_id,token_hash,family_id,parent_id,expires_at)
		 VALUES($1,$2,$3,$4,$5)`,
		principal.UserID, tokenDigest(refreshToken), familyID, parentID, time.Now().UTC().Add(refreshTTL),
	)
	if err != nil {
		return Session{}, err
	}
	return Session{
		AccessToken: accessToken, RefreshToken: refreshToken,
		AccessTTL: accessTTL, RefreshTTL: refreshTTL,
	}, nil
}

func hashPassword(password string) (string, error) {
	salt := make([]byte, 16)
	if _, err := rand.Read(salt); err != nil {
		return "", err
	}
	memory, iterations, parallelism := uint32(64*1024), uint32(3), uint8(2)
	hash := argon2.IDKey([]byte(password), salt, iterations, memory, parallelism, 32)
	return fmt.Sprintf(
		"$argon2id$v=19$m=%d,t=%d,p=%d$%s$%s",
		memory, iterations, parallelism,
		base64.RawStdEncoding.EncodeToString(salt), base64.RawStdEncoding.EncodeToString(hash),
	), nil
}

func verifyPassword(encoded, password string) bool {
	if !strings.HasPrefix(encoded, "$argon2id$") {
		legacy := sha256.Sum256([]byte(password))
		return subtle.ConstantTimeCompare([]byte(strings.ToLower(encoded)), []byte(hex.EncodeToString(legacy[:]))) == 1
	}
	parts := strings.Split(encoded, "$")
	if len(parts) != 6 {
		return false
	}
	var memory, iterations uint64
	var parallelism uint64
	for _, item := range strings.Split(parts[3], ",") {
		key, value, found := strings.Cut(item, "=")
		if !found {
			return false
		}
		parsed, err := strconv.ParseUint(value, 10, 32)
		if err != nil {
			return false
		}
		switch key {
		case "m":
			memory = parsed
		case "t":
			iterations = parsed
		case "p":
			parallelism = parsed
		}
	}
	if memory == 0 || iterations == 0 || parallelism == 0 || parallelism > 255 {
		return false
	}
	salt, err := base64.RawStdEncoding.DecodeString(parts[4])
	if err != nil {
		return false
	}
	expected, err := base64.RawStdEncoding.DecodeString(parts[5])
	if err != nil {
		return false
	}
	actual := argon2.IDKey(
		[]byte(password), salt, uint32(iterations), uint32(memory), uint8(parallelism), uint32(len(expected)),
	)
	return subtle.ConstantTimeCompare(actual, expected) == 1
}

func tokenDigest(token string) string {
	digest := sha256.Sum256([]byte(token))
	return hex.EncodeToString(digest[:])
}

func rawURL(value []byte) string { return base64.RawURLEncoding.EncodeToString(value) }

type bucket struct {
	count int
	reset time.Time
}

type Limiter struct {
	mu      sync.Mutex
	limit   int
	window  time.Duration
	buckets map[string]bucket
}

func NewLimiter(limit int, window time.Duration) *Limiter {
	return &Limiter{limit: limit, window: window, buckets: make(map[string]bucket)}
}

func (l *Limiter) Allow(key string) (time.Duration, error) {
	l.mu.Lock()
	defer l.mu.Unlock()
	now := time.Now()
	value := l.buckets[key]
	if value.reset.IsZero() || !now.Before(value.reset) {
		value = bucket{reset: now.Add(l.window)}
	}
	if value.count >= l.limit {
		return time.Until(value.reset), ErrRateLimited
	}
	value.count++
	l.buckets[key] = value
	return 0, nil
}
