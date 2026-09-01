from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas import ExperimentCreateIn


def _payload(**overrides):
    value = {
        "owner_id": uuid4(),
        "strategy_id": "ma_cross",
        "strategy_version": "v1",
        "dataset_version": "fixture-v1",
        "range_from": datetime(2026, 1, 2, tzinfo=UTC),
        "range_to": datetime(2026, 1, 3, tzinfo=UTC),
    }
    value.update(overrides)
    return value


def test_experiment_range_is_an_immutable_part_of_the_request():
    request = ExperimentCreateIn(**_payload())

    assert request.range_from == datetime(2026, 1, 2, tzinfo=UTC)
    assert request.range_to == datetime(2026, 1, 3, tzinfo=UTC)


@pytest.mark.parametrize(
    "overrides",
    [
        {"range_from": None},
        {"range_to": None},
        {"range_from": datetime(2026, 1, 3, tzinfo=UTC), "range_to": datetime(2026, 1, 2, tzinfo=UTC)},
    ],
)
def test_experiment_range_requires_a_complete_increasing_window(overrides):
    with pytest.raises(ValidationError):
        ExperimentCreateIn(**_payload(**overrides))
