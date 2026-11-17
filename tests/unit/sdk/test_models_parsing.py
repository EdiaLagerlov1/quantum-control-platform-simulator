"""Unit tests for parsing API responses into SDK models. No server and no mocks are involved.

Every rejection test starts from a well-formed dictionary and breaks it in exactly one way,
so a failure points at a single cause.
"""

from __future__ import annotations

import copy
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import pytest

from quantum_sdk import InvalidResponseError
from quantum_sdk.models import ExperimentInfo, ExperimentResult

# Inputs that are not a dictionary at all (the fifth category).
NOT_A_DICT = [
    pytest.param(None, id="none"),
    pytest.param([], id="empty-list"),
    pytest.param([("id", "exp-1")], id="list-of-pairs"),
    pytest.param("a string", id="string"),
    pytest.param(42, id="int"),
]


# Known findings, not fixed yet. strict=True makes the run fail if one of them starts passing,
# which is the reminder to remove the mark once the product is fixed.
NULL_TEXT_ACCEPTED = pytest.mark.xfail(
    strict=True,
    reason="known finding 1: a null text field is accepted and becomes the string 'None'",
)
FRACTION_TRUNCATED = pytest.mark.xfail(
    strict=True, reason="known finding 2: a fractional number in an integer field is truncated"
)


def assert_rejected(parse: Callable[[Any], object], data: Any) -> None:
    """Fail unless ``parse(data)`` raises InvalidResponseError.

    Unlike ``pytest.raises``, the failure message shows the input that was sent and the
    object that came back, so the failure can be understood without opening the test.
    """
    try:
        result = parse(data)
    except InvalidResponseError:
        return
    pytest.fail(f"expected InvalidResponseError, but {data!r} was accepted as {result!r}")


def broken(valid: dict[str, Any], key: str, bad_value: Any) -> dict[str, Any]:
    """Return a deep copy of ``valid`` with exactly one key replaced."""
    data = copy.deepcopy(valid)
    data[key] = bad_value
    return data


def without(valid: dict[str, Any], key: str) -> dict[str, Any]:
    """Return a deep copy of ``valid`` with exactly one key removed."""
    data = copy.deepcopy(valid)
    del data[key]
    return data


class TestExperimentInfoValid:
    def test_well_formed_dict_fills_every_field(self, info_dict: dict[str, Any]) -> None:
        info = ExperimentInfo.from_dict(copy.deepcopy(info_dict))

        assert info.id == "exp-1"
        assert info.name == "bell"
        assert info.status == "COMPLETED"
        assert info.qubits == 2
        assert info.shots == 1000
        assert isinstance(info.created_at, datetime)
        assert info.created_at == datetime(2026, 11, 16, 10, 30, 0, tzinfo=UTC)
        assert isinstance(info.updated_at, datetime)
        assert info.updated_at == datetime(2026, 11, 16, 10, 31, 15, tzinfo=UTC)
        assert info.error_code is None
        assert info.error_message is None

    def test_error_key_is_optional(self, info_dict: dict[str, Any]) -> None:
        info = ExperimentInfo.from_dict(without(info_dict, "error"))

        assert info.error_code is None
        assert info.error_message is None

    def test_error_object_is_unpacked(self, info_dict: dict[str, Any]) -> None:
        error = {"code": "HARDWARE_FAULT", "message": "qubit 1 lost"}

        info = ExperimentInfo.from_dict(broken(info_dict, "error", error))

        assert info.error_code == "HARDWARE_FAULT"
        assert info.error_message == "qubit 1 lost"


class TestExperimentInfoRejects:
    # Category 1: a required key is missing.
    @pytest.mark.parametrize(
        "key", ["id", "name", "status", "qubits", "shots", "created_at", "updated_at"]
    )
    def test_missing_required_key(self, info_dict: dict[str, Any], key: str) -> None:
        assert_rejected(ExperimentInfo.from_dict, without(info_dict, key))

    # Category 2: a required key is present but null.
    @pytest.mark.parametrize(
        "key",
        [
            pytest.param("id", marks=NULL_TEXT_ACCEPTED),
            pytest.param("name", marks=NULL_TEXT_ACCEPTED),
            pytest.param("status", marks=NULL_TEXT_ACCEPTED),
            "qubits",
            "shots",
            "created_at",
            "updated_at",
        ],
    )
    def test_null_required_value(self, info_dict: dict[str, Any], key: str) -> None:
        assert_rejected(ExperimentInfo.from_dict, broken(info_dict, key, None))

    # Category 3: the value has the right type (a string) but cannot be parsed.
    @pytest.mark.parametrize(
        ("key", "bad_value"),
        [
            pytest.param("qubits", "two", id="qubits-word"),
            pytest.param("shots", "", id="shots-empty"),
            pytest.param("created_at", "not-a-date", id="created_at-garbage"),
            pytest.param("created_at", "", id="created_at-empty"),
            pytest.param("updated_at", "2026-13-45T00:00:00", id="updated_at-impossible-date"),
        ],
    )
    def test_unparseable_value(self, info_dict: dict[str, Any], key: str, bad_value: Any) -> None:
        assert_rejected(ExperimentInfo.from_dict, broken(info_dict, key, bad_value))

    # Category 4: the value has the wrong type or shape.
    @pytest.mark.parametrize(
        ("key", "bad_value"),
        [
            pytest.param("qubits", [2], id="qubits-list"),
            pytest.param("qubits", 2.7, id="qubits-fractional-float", marks=FRACTION_TRUNCATED),
            pytest.param("shots", {"value": 1000}, id="shots-dict"),
            pytest.param("created_at", 1731753000, id="created_at-epoch-int"),
            pytest.param("error", "boom", id="error-string"),
            pytest.param("error", ["boom"], id="error-list"),
        ],
    )
    def test_wrong_type(self, info_dict: dict[str, Any], key: str, bad_value: Any) -> None:
        assert_rejected(ExperimentInfo.from_dict, broken(info_dict, key, bad_value))

    # Category 5: the input is not a dictionary.
    @pytest.mark.parametrize("data", NOT_A_DICT)
    def test_not_a_dict(self, data: Any) -> None:
        assert_rejected(ExperimentInfo.from_dict, data)


class TestExperimentResultValid:
    def test_well_formed_dict_fills_every_field(self, result_dict: dict[str, Any]) -> None:
        result = ExperimentResult.from_dict(copy.deepcopy(result_dict))

        assert result.experiment_id == "exp-1"
        assert result.counts == {"00": 480, "11": 520}
        assert result.shots == 1000
        assert result.duration_ms == 12.5
        assert result.probabilities == {"00": 0.48, "11": 0.52}


class TestExperimentResultRejects:
    # Category 1: a required key is missing.
    @pytest.mark.parametrize("key", ["experiment_id", "counts", "shots", "duration_ms"])
    def test_missing_required_key(self, result_dict: dict[str, Any], key: str) -> None:
        assert_rejected(ExperimentResult.from_dict, without(result_dict, key))

    # Category 2: a required key is present but null.
    @pytest.mark.parametrize(
        "key",
        [
            pytest.param("experiment_id", marks=NULL_TEXT_ACCEPTED),
            "counts",
            "shots",
            "duration_ms",
        ],
    )
    def test_null_required_value(self, result_dict: dict[str, Any], key: str) -> None:
        assert_rejected(ExperimentResult.from_dict, broken(result_dict, key, None))

    # Category 3: the value has the right type (a string) but cannot be parsed.
    @pytest.mark.parametrize(
        ("key", "bad_value"),
        [
            pytest.param("shots", "many", id="shots-word"),
            pytest.param("duration_ms", "fast", id="duration-word"),
            pytest.param("counts", {"00": "lots"}, id="counts-value-word"),
        ],
    )
    def test_unparseable_value(self, result_dict: dict[str, Any], key: str, bad_value: Any) -> None:
        assert_rejected(ExperimentResult.from_dict, broken(result_dict, key, bad_value))

    # Category 4: the value has the wrong type or shape.
    @pytest.mark.parametrize(
        ("key", "bad_value"),
        [
            pytest.param("counts", [480, 520], id="counts-list"),
            pytest.param("counts", "00", id="counts-string"),
            pytest.param("counts", {"00": None}, id="counts-value-null"),
            pytest.param("shots", [1000], id="shots-list"),
            pytest.param("shots", 999.5, id="shots-fractional-float", marks=FRACTION_TRUNCATED),
            pytest.param("duration_ms", {"ms": 12.5}, id="duration-dict"),
        ],
    )
    def test_wrong_type(self, result_dict: dict[str, Any], key: str, bad_value: Any) -> None:
        assert_rejected(ExperimentResult.from_dict, broken(result_dict, key, bad_value))

    # Category 5: the input is not a dictionary.
    @pytest.mark.parametrize("data", NOT_A_DICT)
    def test_not_a_dict(self, data: Any) -> None:
        assert_rejected(ExperimentResult.from_dict, data)
