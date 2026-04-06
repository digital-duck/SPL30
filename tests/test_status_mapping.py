"""Tests for COMMIT status → EXCEPTION mapping.

Run: pytest tests/test_status_mapping.py -v
"""
import pytest

from spl.status import (
    status_to_exception_type,
    raise_if_failed,
    WorkflowCompositionError,
    SUCCESSFUL_STATUSES,
)


class TestStatusToExceptionType:

    def test_complete_returns_none(self):
        assert status_to_exception_type("complete") is None

    def test_no_commit_returns_none(self):
        assert status_to_exception_type("no_commit") is None

    def test_all_successful_statuses_return_none(self):
        for status in SUCCESSFUL_STATUSES:
            assert status_to_exception_type(status) is None

    def test_refused_maps_to_refusal(self):
        assert status_to_exception_type("refused") == "RefusalToAnswer"

    def test_blocked_maps_to_refusal(self):
        assert status_to_exception_type("blocked") == "RefusalToAnswer"

    def test_partial_maps_to_quality(self):
        assert status_to_exception_type("partial") == "QualityBelowThreshold"

    def test_timeout_maps_to_node_unavailable(self):
        assert status_to_exception_type("timeout") == "NodeUnavailable"

    def test_overloaded_maps_to_model_overloaded(self):
        assert status_to_exception_type("overloaded") == "ModelOverloaded"

    def test_budget_maps_to_budget_exceeded(self):
        assert status_to_exception_type("budget") == "BudgetExceeded"

    def test_unknown_status_maps_to_generation_error(self):
        assert status_to_exception_type("something_unknown") == "GenerationError"


class TestRaiseIfFailed:

    def test_complete_does_not_raise(self):
        raise_if_failed("complete", "my_workflow", "output")  # no exception

    def test_no_commit_does_not_raise(self):
        raise_if_failed("no_commit", "my_workflow", None)     # no exception

    def test_refused_raises_composition_error(self):
        with pytest.raises(WorkflowCompositionError) as exc_info:
            raise_if_failed("refused", "generate_code", None)
        err = exc_info.value
        assert err.exception_type == "RefusalToAnswer"
        assert err.workflow_name == "generate_code"
        assert err.status == "refused"

    def test_partial_raises_with_correct_type(self):
        with pytest.raises(WorkflowCompositionError) as exc_info:
            raise_if_failed("partial", "review_code", "partial output")
        assert exc_info.value.exception_type == "QualityBelowThreshold"
        assert exc_info.value.output == "partial output"

    def test_error_message_is_informative(self):
        with pytest.raises(WorkflowCompositionError, match="generate_code"):
            raise_if_failed("timeout", "generate_code", None)
        with pytest.raises(WorkflowCompositionError, match="NodeUnavailable"):
            raise_if_failed("timeout", "generate_code", None)
