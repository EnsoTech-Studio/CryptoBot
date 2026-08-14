package common

import (
	"encoding/json"
)

// CanonicalJSON and HashCanonicalJSON are reserved for immutable snapshot and
// candidate hashes. Production canonicalization is intentionally deferred.
func CanonicalJSON(any) ([]byte, error)     { return nil, ErrNotImplemented }
func HashCanonicalJSON(any) (string, error) { return "", ErrNotImplemented }

var _ = json.RawMessage{}
