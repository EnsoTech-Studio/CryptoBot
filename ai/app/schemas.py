from datetime import datetime
from typing import Literal

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
