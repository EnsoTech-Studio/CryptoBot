import json
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import httpx

from app.infrastructure.ai import DiscoveryLLMHTTPAdapter


def test_discovery_adapter_serializes_database_values_before_http() -> None:
    observed: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        observed.update(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "proposal": {
                    "candidate_definition": {
                        "strategy_id": "ma_cross",
                        "version": "v1",
                        "parameters": {"fast": 5, "slow": 30},
                    },
                    "hypothesis": "Trend filter",
                    "operation": "new",
                },
                "provider": "openai",
                "model": "test-model",
                "model_version": "test-version",
                "prompt_version": "discovery-v1",
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    adapter = DiscoveryLLMHTTPAdapter("http://ai", client=client)
    try:
        result = adapter.propose(
            {"strategy_ids": ["ma_cross"]},
            [{"id": uuid4(), "score": Decimal("0.1")}],
            {"observed_at": datetime.now(timezone.utc), "score": Decimal("0.1")},
        )
    finally:
        adapter.close()

    assert result["provider"] == "openai"
    assert result["candidate_definition"]["strategy_id"] == "ma_cross"
    archive = observed["archive"]
    assert isinstance(archive, list)
    assert isinstance(archive[0]["id"], str)
    assert isinstance(observed["research"]["score"], str)
