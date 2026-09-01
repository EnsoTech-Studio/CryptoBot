package market

import (
	"fmt"
	"strings"

	"github.com/EnsoTech-Studio/CryptoBot/server/internal/ports"
)

// ProviderRegistry is intentionally small: adding an exchange means
// registering its typed adapter, never adding a branch to MarketService.
type ProviderRegistry struct {
	providers map[string]ports.RealtimeMarketProvider
}

func NewProviderRegistry(providers ...ports.RealtimeMarketProvider) (*ProviderRegistry, error) {
	registry := &ProviderRegistry{providers: make(map[string]ports.RealtimeMarketProvider, len(providers))}
	for _, provider := range providers {
		if provider == nil || strings.TrimSpace(provider.ProviderID()) == "" {
			return nil, fmt.Errorf("market provider is required")
		}
		id := strings.ToLower(strings.TrimSpace(provider.ProviderID()))
		if _, exists := registry.providers[id]; exists {
			return nil, fmt.Errorf("duplicate market provider %q", id)
		}
		registry.providers[id] = provider
	}
	return registry, nil
}

func (r *ProviderRegistry) Resolve(provider string) (ports.RealtimeMarketProvider, error) {
	if r == nil {
		return nil, fmt.Errorf("market provider registry is unavailable")
	}
	resolved, ok := r.providers[strings.ToLower(strings.TrimSpace(provider))]
	if !ok {
		return nil, fmt.Errorf("market provider %q is not registered", provider)
	}
	return resolved, nil
}
