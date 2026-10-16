"""Retry engine and error classification for DataFlow."""

import logging
import random
import time
from typing import Callable, Optional, Sequence, Type, TypeVar

from dataflow.config import get_settings

logger = logging.getLogger(__name__)

T = TypeVar("T")


class DataFlowError(Exception):
    """Base exception for all DataFlow errors."""
    pass


class PermanentError(DataFlowError):
    """Errors that should never be retried (e.g. invalid syntax, schema violation, auth error)."""
    pass


class TransientError(DataFlowError):
    """Errors that are temporary and may succeed on retry (e.g. network timeout, lock conflict)."""
    pass


class RetryExhaustedError(PermanentError):
    """Raised when all retry attempts have failed."""

    def __init__(self, message: str, last_exception: Exception, attempts: int):
        super().__init__(f"{message} (after {attempts} attempts): {last_exception}")
        self.last_exception = last_exception
        self.attempts = attempts


def classify_exception(exc: Exception) -> str:
    """Classify an exception into a category string: permanent, transient, or unknown."""
    if isinstance(exc, PermanentError):
        return "permanent"
    if isinstance(exc, TransientError):
        return "transient"

    exc_name = type(exc).__name__.lower()
    exc_msg = str(exc).lower()

    # Network, DB connection, timeout, and concurrency conflicts
    transient_indicators = [
        "timeout",
        "connection",
        "operationalerror",
        "deadlock",
        "lock",
        "pool",
        "temporarily",
        "503",
        "502",
        "504",
        "rate limit",
        "429",
    ]
    if any(ind in exc_name or ind in exc_msg for ind in transient_indicators):
        return "transient"

    # Schema, file format, validation, and type errors
    permanent_indicators = [
        "validation",
        "schema",
        "valueerror",
        "typeerror",
        "keyerror",
        "notfound",
        "pathtraversal",
        "integrityerror",
        "duplicateheader",
        "400",
        "401",
        "403",
        "404",
        "422",
    ]
    if any(ind in exc_name or ind in exc_msg for ind in permanent_indicators):
        return "permanent"

    return "unknown"


def calculate_backoff(
    attempt: int,
    factor: float = 0.5,
    max_backoff: float = 10.0,
    jitter: bool = True,
) -> float:
    """Calculate exponential backoff time with optional jitter."""
    delay = factor * (2 ** (attempt - 1))
    delay = min(delay, max_backoff)
    if jitter:
        # Uniform jitter between 50% and 100% of delay
        delay = delay * random.uniform(0.5, 1.0)
    return max(0.0, delay)


def execute_with_retry(
    operation: Callable[[], T],
    max_attempts: Optional[int] = None,
    backoff_factor: Optional[float] = None,
    max_backoff: Optional[float] = None,
    jitter: Optional[bool] = None,
    transient_exceptions: Sequence[Type[Exception]] = (TransientError,),
    on_retry: Optional[Callable[[int, Exception, float], None]] = None,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> T:
    """
    Execute a callable with bounded exponential backoff retries for transient errors.
    Permanent errors and non-transient exceptions terminate immediately without retry.
    """
    settings = get_settings()
    attempts_limit = max_attempts if max_attempts is not None else settings.MAX_RETRIES
    b_factor = backoff_factor if backoff_factor is not None else settings.RETRY_BACKOFF_FACTOR
    b_max = max_backoff if max_backoff is not None else settings.RETRY_MAX_BACKOFF_SECONDS
    use_jitter = jitter if jitter is not None else settings.RETRY_JITTER

    attempt = 1
    while True:
        try:
            return operation()
        except Exception as exc:
            # Check if this exception is classified as transient
            is_transient = isinstance(exc, tuple(transient_exceptions)) or classify_exception(exc) == "transient"

            if not is_transient:
                logger.debug(f"Operation failed with non-transient error: {exc}. Not retrying.")
                raise

            if attempt >= attempts_limit:
                logger.warning(f"Exhausted all {attempts_limit} retry attempts. Last error: {exc}")
                raise RetryExhaustedError(
                    "Retry exhausted for operation",
                    last_exception=exc,
                    attempts=attempt,
                ) from exc

            delay = calculate_backoff(attempt, factor=b_factor, max_backoff=b_max, jitter=use_jitter)
            logger.info(f"Transient error on attempt {attempt}/{attempts_limit}: {exc}. Retrying in {delay:.2f}s...")

            if on_retry:
                try:
                    on_retry(attempt, exc, delay)
                except Exception as cb_exc:
                    logger.warning(f"Error in on_retry callback: {cb_exc}")

            sleep_fn(delay)
            attempt += 1
