from dataclasses import dataclass
import os


@dataclass
class Prediction:
    label: str
    score: float
    model: str
    model_version: str


class Predictor:
    """Deterministic sentiment adapter for the demo deployment.

    The contract is intentionally the same seam a model-backed adapter would
    expose: label, confidence score, model id, and model_version.
    """

    positive_terms = {
        "positive", "bullish", "inflow", "growth", "support",
        "breakout", "lower fees", "constructive", "uptrend", "strong",
    }
    negative_terms = {
        "negative", "bearish", "hack", "incident", "halted",
        "risk", "selloff", "regulation", "downtrend", "weak",
    }

    def predict(self, text: str) -> Prediction:
        lowered = text.lower()
        positive = sum(1 for term in self.positive_terms if term in lowered)
        negative = sum(1 for term in self.negative_terms if term in lowered)
        if positive > negative:
            label = "POSITIVE"
            score = min(0.95, 0.62 + 0.08 * (positive - negative))
        elif negative > positive:
            label = "NEGATIVE"
            score = min(0.95, 0.62 + 0.08 * (negative - positive))
        else:
            label = "NEUTRAL"
            score = 0.55
        return Prediction(
            label=label,
            score=score,
            model="sentiment-v1",
            model_version=os.getenv("SENTIMENT_MODEL_VERSION", "2026-08-01"),
        )


predictor = Predictor()
