from datetime import datetime, timezone

from fastapi import FastAPI

from app.schemas import PredictRequest, PredictResponse
from app.services.predictor import predictor

app = FastAPI(
    title="CryptoBot AI Service",
    version="0.1.0",
    description="Inference boundary for the CryptoBot platform.",
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "ai", "model": "sentiment-v1"}


@app.post("/predict", response_model=PredictResponse)
def predict(payload: PredictRequest) -> PredictResponse:
    result = predictor.predict(payload.text)
    return PredictResponse(
        label=result.label,
        score=result.score,
        model=result.model,
        model_version=result.model_version,
        received_at=datetime.now(timezone.utc),
    )
