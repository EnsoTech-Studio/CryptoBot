"""Evaluator — derives metrics from trade facts (float64). Deferred stub."""

from __future__ import annotations

from ..domain.evaluation import Evaluation, EvaluationInput, EvaluationPolicy


class DeterministicEvaluator:
    def evaluate(self, input_: EvaluationInput, policy: EvaluationPolicy) -> Evaluation:
        raise NotImplementedError
