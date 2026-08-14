package news

import (
	"context"
	"time"

	"github.com/EnsoTech-Studio/CryptoBot/server/internal/domain/common"
	domainnews "github.com/EnsoTech-Studio/CryptoBot/server/internal/domain/news"
)

type RSSProvider struct{}

func NewRSSProvider() *RSSProvider { return &RSSProvider{} }
func (*RSSProvider) Collect(context.Context, domainnews.ApprovedSource, time.Time) ([]domainnews.Item, error) {
	return nil, common.ErrNotImplemented
}
