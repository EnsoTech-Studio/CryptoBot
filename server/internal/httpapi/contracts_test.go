package httpapi

import "testing"

func validSearchRequest() searchRunRequest {
	return searchRunRequest{
		GeneratorID: "domain_guided",
		SearchSpace: searchSpaceInput{
			StrategyIDs: []string{"ma_cross", "rsi"},
			Cardinality: []int{2},
			Policies:    []string{"weighted_vote"},
			ParameterGrid: map[string]map[string][]any{
				"ma_cross": {"fast": {10, 20}, "slow": {30}},
			},
		},
		StopConditions: map[string]any{
			"max_candidates":    float64(20),
			"max_duration_sec":  float64(300),
			"max_non_improving": float64(5),
			"max_failure_rate":  0.3,
		},
	}
}

func TestSearchRequestValidationAcceptsBoundedCompositeSearch(t *testing.T) {
	request := validSearchRequest()
	if err := request.validate(); err != nil {
		t.Fatalf("expected valid search request, got %v", err)
	}
}

func TestSearchRequestValidationAcceptsDiscoveryLoop(t *testing.T) {
	request := validSearchRequest()
	request.GeneratorID = "discovery"
	if err := request.validate(); err != nil {
		t.Fatalf("expected discovery request to be valid, got %v", err)
	}
}

func TestSearchRequestValidationRejectsMalformedStops(t *testing.T) {
	cases := []map[string]any{
		{},
		{"max_candidates": 1.5},
		{"max_duration_sec": "300"},
		{"max_failure_rate": 0.0},
		{"unknown": 1},
	}
	for _, stopConditions := range cases {
		request := validSearchRequest()
		request.StopConditions = stopConditions
		if err := request.validate(); err == nil {
			t.Fatalf("expected invalid stop conditions: %#v", stopConditions)
		}
	}
}

func TestSearchRequestValidationRejectsImpossibleCardinality(t *testing.T) {
	request := validSearchRequest()
	request.SearchSpace.Cardinality = []int{3}
	if err := request.validate(); err == nil {
		t.Fatal("expected cardinality above strategy count to be rejected")
	}
}

func TestNewsStrategyAnalysisValidationDefaultsModel(t *testing.T) {
	score := 0.72
	request := newsStrategyAnalysisRequest{
		SentimentMix: newsStrategyMixInput{Positive: 60, Neutral: 30, Negative: 10},
		Coverage: newsStrategyCoverageInput{
			ItemsTotal: 10, ItemsAnalyzed: 8, ItemsUnanalyzed: 2,
		},
		AverageScore: &score,
	}

	if err := request.validate(); err != nil {
		t.Fatalf("expected valid strategy analysis request, got %v", err)
	}
	if request.Model != "gpt-4o-mini" {
		t.Fatalf("expected gpt-4o-mini default, got %s", request.Model)
	}
}

func TestNewsStrategyAnalysisValidationRejectsUnknownModel(t *testing.T) {
	request := newsStrategyAnalysisRequest{
		SentimentMix: newsStrategyMixInput{Positive: 60, Neutral: 30, Negative: 10},
		Coverage:     newsStrategyCoverageInput{ItemsTotal: 1, ItemsAnalyzed: 1},
		Model:        "unknown-model",
	}

	if err := request.validate(); err == nil {
		t.Fatal("expected unsupported model to be rejected")
	}
}
