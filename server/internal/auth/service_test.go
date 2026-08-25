package auth

import (
	"errors"
	"path/filepath"
	"testing"
	"time"

	"github.com/google/uuid"
)

func TestPersistentSignerVerifiesTokenAfterReload(t *testing.T) {
	keyPath := filepath.Join(t.TempDir(), "jwt.pem")
	first, err := LoadOrCreateSigner(keyPath, "issuer", "audience")
	if err != nil {
		t.Fatal(err)
	}
	principal := Principal{
		UserID: uuid.New(), Email: "researcher@example.com", DisplayName: "Researcher",
		Role: RoleResearcher, Active: true,
	}
	token, err := first.Issue(principal, time.Minute)
	if err != nil {
		t.Fatal(err)
	}
	second, err := LoadOrCreateSigner(keyPath, "issuer", "audience")
	if err != nil {
		t.Fatal(err)
	}
	userID, err := second.Verify(token)
	if err != nil {
		t.Fatal(err)
	}
	if userID != principal.UserID {
		t.Fatalf("unexpected subject %s", userID)
	}
}

func TestArgon2IDPasswordHash(t *testing.T) {
	encoded, err := hashPassword("correct horse battery staple")
	if err != nil {
		t.Fatal(err)
	}
	if !verifyPassword(encoded, "correct horse battery staple") {
		t.Fatal("valid password did not verify")
	}
	if verifyPassword(encoded, "wrong password") {
		t.Fatal("invalid password verified")
	}
}

func TestAuthLimiterReturnsRetryWindow(t *testing.T) {
	limiter := NewLimiter(2, time.Minute)
	if _, err := limiter.Allow("client"); err != nil {
		t.Fatal(err)
	}
	if _, err := limiter.Allow("client"); err != nil {
		t.Fatal(err)
	}
	retry, err := limiter.Allow("client")
	if !errors.Is(err, ErrRateLimited) || retry <= 0 {
		t.Fatalf("expected rate limit with retry, got retry=%s err=%v", retry, err)
	}
}
