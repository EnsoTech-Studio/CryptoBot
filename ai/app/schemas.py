from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


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
