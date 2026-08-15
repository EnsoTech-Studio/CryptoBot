package lab

import (
	"context"
	"crypto"
	"crypto/rand"
	"crypto/rsa"
	"crypto/sha256"
	"crypto/subtle"
	"database/sql"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"math/big"
	"strings"
	"time"

	"github.com/google/uuid"
)

type Signer struct {
	private *rsa.PrivateKey
	public  *rsa.PublicKey
	keyID   string
	issuer  string
	audience string
}

func NewSigner() (*Signer, error) {
	key, err := rsa.GenerateKey(rand.Reader, 2048)
	if err != nil {
		return nil, err
	}
	return &Signer{private: key, public: &key.PublicKey, keyID: "demo-rs256", issuer: "cryptobot", audience: "cryptobot-web"}, nil
}

func (s *Signer) Issue(p Principal, ttl time.Duration) (string, error) {
	now := time.Now().UTC()
	header := map[string]any{"alg": "RS256", "typ": "JWT", "kid": s.keyID}
	claims := map[string]any{
		"sub": p.ID, "email": p.Email, "display_name": p.DisplayName, "role": p.Role,
		"jti": uuid.NewString(), "iss": s.issuer, "aud": s.audience,
		"iat": now.Unix(), "exp": now.Add(ttl).Unix(),
	}
	h, _ := json.Marshal(header)
	c, _ := json.Marshal(claims)
	unsigned := b64(h) + "." + b64(c)
	sum := sha256.Sum256([]byte(unsigned))
	sig, err := rsa.SignPKCS1v15(rand.Reader, s.private, crypto.SHA256, sum[:])
	if err != nil {
		return "", err
	}
	return unsigned + "." + b64(sig), nil
}

func (s *Signer) Verify(token string) (Principal, error) {
	parts := strings.Split(token, ".")
	if len(parts) != 3 {
		return Principal{}, fmt.Errorf("invalid token")
	}
	unsigned := parts[0] + "." + parts[1]
	sig, err := base64.RawURLEncoding.DecodeString(parts[2])
	if err != nil {
		return Principal{}, err
	}
	sum := sha256.Sum256([]byte(unsigned))
	if err := rsa.VerifyPKCS1v15(s.public, crypto.SHA256, sum[:], sig); err != nil {
		return Principal{}, err
	}
	payload, err := base64.RawURLEncoding.DecodeString(parts[1])
	if err != nil {
		return Principal{}, err
	}
	var claims map[string]any
	if err := json.Unmarshal(payload, &claims); err != nil {
		return Principal{}, err
	}
	if claims["iss"] != s.issuer || claims["aud"] != s.audience {
		return Principal{}, fmt.Errorf("invalid token audience")
	}
	exp, _ := claims["exp"].(float64)
	if time.Now().Unix() > int64(exp) {
		return Principal{}, fmt.Errorf("token expired")
	}
	return Principal{
		ID: stringClaim(claims, "sub"),
		Email: stringClaim(claims, "email"),
		DisplayName: stringClaim(claims, "display_name"),
		Role: stringClaim(claims, "role"),
	}, nil
}

func Authenticate(ctx context.Context, db *sql.DB, email, password string) (Principal, error) {
	var p Principal
	var hash string
	var active bool
	err := db.QueryRowContext(ctx, `
		SELECT id,email,display_name,role,password_hash,is_active FROM users WHERE lower(email)=lower($1)
	`, strings.TrimSpace(email)).Scan(&p.ID, &p.Email, &p.DisplayName, &p.Role, &hash, &active)
	if err != nil {
		_ = verifyPassword(hashPassword("dummy"), password)
		return Principal{}, fmt.Errorf("invalid_credentials")
	}
	if !active || !constantTimeStringEqual(hash, hashPassword(password)) {
		return Principal{}, fmt.Errorf("invalid_credentials")
	}
	return p, nil
}

func RegisterUser(ctx context.Context, db *sql.DB, email, password, displayName string) (Principal, error) {
	email = strings.TrimSpace(strings.ToLower(email))
	displayName = strings.TrimSpace(displayName)
	if len(password) < 12 || !strings.Contains(email, "@") {
		return Principal{}, fmt.Errorf("invalid_registration")
	}
	if displayName == "" {
		displayName = strings.Split(email, "@")[0]
	}
	p := Principal{ID: uuid.NewString(), Email: email, DisplayName: displayName, Role: "RESEARCHER"}
	if _, err := db.ExecContext(ctx, `
		INSERT INTO users(id,email,display_name,password_hash,role) VALUES($1,$2,$3,$4,'RESEARCHER')
	`, p.ID, p.Email, p.DisplayName, hashPassword(password)); err != nil {
		return Principal{}, err
	}
	if _, err := db.ExecContext(ctx, `INSERT INTO user_quotas(user_id) VALUES($1)`, p.ID); err != nil {
		return Principal{}, err
	}
	return p, nil
}

func NewCSRFToken() string {
	n, _ := rand.Int(rand.Reader, new(big.Int).Lsh(big.NewInt(1), 160))
	return base64.RawURLEncoding.EncodeToString(n.Bytes())
}

func b64(data []byte) string {
	return base64.RawURLEncoding.EncodeToString(data)
}

func stringClaim(claims map[string]any, key string) string {
	value, _ := claims[key].(string)
	return value
}

func constantTimeStringEqual(a, b string) bool {
	return subtle.ConstantTimeCompare([]byte(a), []byte(b)) == 1
}
