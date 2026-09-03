from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class PredictRequest(BaseModel):
    text: str = Field(min_length=1, max_length=10_000)

    @field_validator("text")
    @classmethod
    def text_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("text must not be blank")
        return value


class PredictResponse(BaseModel):
    label: Literal["POSITIVE", "NEUTRAL", "NEGATIVE"]
    score: float = Field(ge=0, le=1)
    model: str = Field(min_length=1)
    model_version: str = Field(min_length=1)
    received_at: datetime

    @field_validator("model", "model_version")
    @classmethod
    def metadata_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("model metadata must not be blank")
        return value


class StrategySpecRequest(BaseModel):
    text: str = Field(min_length=1, max_length=10_000)

    @field_validator("text")
    @classmethod
    def text_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("text must not be blank")
        return value


class DiscoveryProposalRequest(BaseModel):
    mode: Literal["new", "improve", "combine"]
    search_space: dict[str, Any]
    archive: list[dict[str, Any]] = Field(default_factory=list, max_length=20)
    research: dict[str, Any] = Field(default_factory=dict)


class DiscoveryProposal(BaseModel):
    candidate_definition: dict[str, Any]
    hypothesis: str = Field(min_length=1, max_length=1_000)
    operation: Literal["new", "improve", "combine"]


class DiscoveryProposalResponse(BaseModel):
    proposal: DiscoveryProposal
    provider: str = Field(min_length=1)
    model: str = Field(min_length=1)
    model_version: str = Field(min_length=1)
    prompt_version: str = Field(min_length=1)


class StrategySpecResponse(BaseModel):
    schema_version: str = "strategy-spec/v1"
    strategy_id: str = Field(min_length=1, max_length=120)
    display_name: str = Field(min_length=1, max_length=120)
    family: Literal["trend", "momentum", "volatility", "structure", "information"]
    description: str = Field(min_length=1, max_length=2_000)
    parameters: dict[str, dict[str, Any]]
    indicators: list[dict[str, Any]]
    rules: dict[str, Any]
    warmup_bars: int = Field(ge=1, le=10_000)


class StrategyDesignResponse(BaseModel):
    spec: StrategySpecResponse
    model: str = Field(min_length=1)
    model_version: str = Field(min_length=1)

    @field_validator("model", "model_version")
    @classmethod
    def metadata_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("model metadata must not be blank")
        return value


class StrategyPythonRepairRequest(BaseModel):
    artifact: str = Field(min_length=1, max_length=20_000)
    error_code: str = Field(min_length=1, max_length=128)

    @field_validator("artifact", "error_code")
    @classmethod
    def fields_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("value must not be blank")
        return value


class StrategyPythonRepairResponse(BaseModel):
    artifact: str = Field(min_length=1, max_length=20_000)


class NewsExtractionRequest(BaseModel):
    text: str = Field(min_length=1, max_length=20_000)

    @field_validator("text")
    @classmethod
    def text_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("text must not be blank")
        return value


class NewsExtractionResponse(BaseModel):
    title: str = Field(min_length=1, max_length=512)
    body: str = Field(min_length=40, max_length=20_000)
    model: str = Field(min_length=1)
    model_version: str = Field(min_length=1)


class NewsStrategyMix(BaseModel):
    positive: int = Field(ge=0, le=100)
    neutral: int = Field(ge=0, le=100)
    negative: int = Field(ge=0, le=100)

    @model_validator(mode="after")
    def percentages_must_sum_to_100_when_present(self) -> "NewsStrategyMix":
        total = self.positive + self.neutral + self.negative
        if total not in {0, 100}:
            raise ValueError("sentiment percentages must sum to 100")
        return self


class NewsStrategyCoverage(BaseModel):
    items_total: int = Field(ge=0, le=10_000)
    items_analyzed: int = Field(ge=0, le=10_000)
    items_unanalyzed: int = Field(ge=0, le=10_000)

    @model_validator(mode="after")
    def counts_must_be_consistent(self) -> "NewsStrategyCoverage":
        if self.items_analyzed + self.items_unanalyzed != self.items_total:
            raise ValueError("coverage counts are inconsistent")
        return self


class NewsStrategyAnalysisRequest(BaseModel):
    sentiment_mix: NewsStrategyMix
    coverage: NewsStrategyCoverage
    average_score: float | None = Field(default=None, ge=0, le=1)
    model: Literal["gpt-4o-mini", "gpt-4o", "gpt-4.1-mini", "gpt-5-mini"] = "gpt-4o-mini"


class NewsStrategyAnalysisResponse(BaseModel):
    reasoning: str = Field(min_length=1, max_length=2_000)
    result: str = Field(min_length=2, max_length=8_000)
    model: str = Field(min_length=1)
    model_version: str = Field(min_length=1)
