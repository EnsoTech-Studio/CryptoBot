package auth

import (
	"context"
	"net/http"

	"github.com/google/uuid"
)

type Role string

const (
	RoleResearcher Role = "RESEARCHER"
	RoleOperator   Role = "OPERATOR"
	RoleAdmin      Role = "ADMIN"
)

type Principal struct {
	UserID      uuid.UUID `json:"id"`
	Email       string    `json:"email"`
	DisplayName string    `json:"display_name"`
	Role        Role      `json:"role"`
	Active      bool      `json:"-"`
}

type Authenticator interface {
	Authenticate(context.Context, *http.Request) (Principal, error)
}

type SessionService interface {
	Register(context.Context, string, string, string) (Principal, error)
	Login(context.Context, string, string) (Principal, error)
	Refresh(context.Context, *http.Request) (Principal, error)
	Logout(context.Context, *http.Request) error
}

type PrincipalStore interface {
	GetPrincipal(context.Context, uuid.UUID) (Principal, error)
}

type Authorizer interface {
	Allows(Principal, string, string) error
	Owns(context.Context, Principal, string, uuid.UUID) error
}

type CSRFValidator interface {
	Validate(*http.Request) error
}

type RateLimiter interface {
	Allow(context.Context, string) error
}
