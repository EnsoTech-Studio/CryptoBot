from dataclasses import dataclass


@dataclass
class Prediction:
    label: str
    score: float
    model: str


class Predictor:
    """Replace this deterministic stub with the production model adapter."""

    def predict(self, text: str) -> Prediction:
        del text
        return Prediction(label="neutral", score=0.5, model="stub-v0")


predictor = Predictor()
