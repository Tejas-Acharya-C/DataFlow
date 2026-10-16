"""Unit tests for retry classification, backoff calculation, and bounded execution."""

import pytest

from dataflow.services.retry import (
    PermanentError,
    RetryExhaustedError,
    TransientError,
    calculate_backoff,
    classify_exception,
    execute_with_retry,
)


def test_classify_exception_permanent():
    """Verify permanent input, validation, and contract errors are classified as 'permanent'."""
    assert classify_exception(ValueError("invalid CSV format")) == "permanent"
    assert classify_exception(KeyError("missing column")) == "permanent"
    assert classify_exception(PermanentError("contract violated")) == "permanent"


def test_classify_exception_transient():
    """Verify network, lock, and timeout exceptions are classified as 'transient'."""
    assert classify_exception(TimeoutError("connection timed out")) == "transient"
    assert classify_exception(TransientError("lock wait timeout")) == "transient"
    assert classify_exception(ConnectionResetError("peer reset")) == "transient"


def test_calculate_backoff_bounds():
    """Verify exponential backoff growth and ceiling bound."""
    # attempt 1: base backoff = 0.5 * 2^(1-1) = 0.5
    b1 = calculate_backoff(attempt=1, factor=0.5, max_backoff=5.0, jitter=False)
    assert b1 == 0.5

    # attempt 2: base backoff = 0.5 * 2^(2-1) = 1.0
    b2 = calculate_backoff(attempt=2, factor=0.5, max_backoff=5.0, jitter=False)
    assert b2 == 1.0

    # attempt 3: base backoff = 0.5 * 2^(3-1) = 2.0
    b3 = calculate_backoff(attempt=3, factor=0.5, max_backoff=5.0, jitter=False)
    assert b3 == 2.0

    # attempt 6: 0.5 * 2^5 = 16.0, should be capped at max_backoff (5.0)
    b6 = calculate_backoff(attempt=6, factor=0.5, max_backoff=5.0, jitter=False)
    assert b6 == 5.0


def test_execute_with_retry_success_after_transient():
    """Verify transient error is retried and recovers upon subsequent attempt."""
    call_count = 0
    sleeps = []

    def mock_operation():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise TransientError("temporary db lock")
        return "success"

    result = execute_with_retry(
        operation=mock_operation,
        max_attempts=3,
        backoff_factor=0.1,
        max_backoff=1.0,
        jitter=False,
        sleep_fn=sleeps.append,
    )

    assert result == "success"
    assert call_count == 3
    assert len(sleeps) == 2  # slept twice before 3rd attempt succeeded


def test_execute_with_retry_permanent_fails_immediately():
    """Verify permanent errors abort immediately without burning retry attempts."""
    call_count = 0
    sleeps = []

    def mock_operation():
        nonlocal call_count
        call_count += 1
        raise ValueError("Malformed CSV line 42")

    with pytest.raises(ValueError) as exc_info:
        execute_with_retry(
            operation=mock_operation,
            max_attempts=5,
            backoff_factor=0.1,
            sleep_fn=sleeps.append,
        )

    assert "Malformed CSV" in str(exc_info.value)
    assert call_count == 1  # No retries attempted
    assert len(sleeps) == 0


def test_execute_with_retry_exhaustion():
    """Verify RetryExhaustedError is raised when max attempts are exceeded."""
    call_count = 0
    sleeps = []

    def mock_operation():
        nonlocal call_count
        call_count += 1
        raise TimeoutError("Upstream service unresponsive")

    with pytest.raises(RetryExhaustedError) as exc_info:
        execute_with_retry(
            operation=mock_operation,
            max_attempts=3,
            backoff_factor=0.1,
            sleep_fn=sleeps.append,
        )

    assert "after 3 attempts" in str(exc_info.value)
    assert call_count == 3
    assert len(sleeps) == 2
