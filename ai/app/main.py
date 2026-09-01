from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, status

from app.schemas import NewsExtractionRequest, NewsExtractionResponse, PredictRequest, PredictResponse, StrategySpecRequest, StrategySpecResponse
from app.services.predictor import predictor

app = FastAPI(
    title="CryptoBot AI Service",
    version="0.1.0",
    description="Inference boundary for the CryptoBot platform.",
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "ai", "model": predictor.model}


@app.post("/predict", response_model=PredictResponse)
def predict(payload: PredictRequest) -> PredictResponse:
    try:
        result = predictor.predict(payload.text)
        return PredictResponse(
            label=result.label,
            score=result.score,
            model=result.model,
            model_version=result.model_version,
            received_at=datetime.now(timezone.utc),
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "sentiment_unavailable"},
        ) from exc


@app.post("/strategy/spec", response_model=StrategySpecResponse)
def design_strategy(payload: StrategySpecRequest) -> StrategySpecResponse:
    try:
        return StrategySpecResponse.model_validate(predictor.design(payload.text))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "strategy_design_unavailable"},
        ) from exc


@app.post("/news/extract", response_model=NewsExtractionResponse)
def extract_news(payload: NewsExtractionRequest) -> NewsExtractionResponse:
    try:
        result = predictor.extract_news(payload.text)
        return NewsExtractionResponse(title=result.title, body=result.body, model=result.model, model_version=result.model_version)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "news_extraction_unavailable"},
        ) from exc
