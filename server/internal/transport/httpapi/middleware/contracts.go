package middleware

import (
	"context"
	"net/http"
)

type RequestID func(http.Handler) http.Handler
type CORS func(http.Handler) http.Handler
type SecurityHeaders func(http.Handler) http.Handler
type BodyLimit func(http.Handler) http.Handler
type Authentication func(http.Handler) http.Handler

type PrincipalKey struct{}

func WithPrincipal(ctx context.Context, principal any) context.Context {
	return context.WithValue(ctx, PrincipalKey{}, principal)
}
func PrincipalFromContext(ctx context.Context) (any, bool) {
	value := ctx.Value(PrincipalKey{})
	return value, value != nil
}
