"""Retry policies for the two external APIs.

Transient failures are common and cheap to recover from, but both policies fail
fast on errors a retry can't fix (bad key, unknown model) so a misconfiguration
surfaces immediately instead of after four backoffs.
"""

import logging

import groq
import requests
from tenacity import (
    retry,
    retry_if_exception,
    retry_if_exception_type,
    stop_after_attempt,
    wait_random_exponential,
)

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 4
RETRYABLE_STATUS = {429, 500, 502, 503, 504}

# Everything else (NotFoundError, AuthenticationError, BadRequestError) would just fail four more times.
GROQ_RETRYABLE = (
    groq.RateLimitError,
    groq.APITimeoutError,
    groq.APIConnectionError,
    groq.InternalServerError,
)


def _log_retry(state) -> None:
    logger.warning(
        "%s failed (attempt %d/%d), retrying in %.1fs: %s",
        state.fn.__name__ if state.fn else "call",
        state.attempt_number,
        MAX_ATTEMPTS,
        state.next_action.sleep,
        state.outcome.exception(),
    )


def _tavily_is_retryable(exc: BaseException) -> bool:
    """tavily-python 0.3.3 defines no exception types of its own — it uses
    `requests` and calls raise_for_status(), so classify by status code."""
    if isinstance(exc, (requests.exceptions.Timeout, requests.exceptions.ConnectionError)):
        return True
    if isinstance(exc, requests.exceptions.HTTPError):
        response = exc.response
        return response is not None and response.status_code in RETRYABLE_STATUS
    return False


_common = {
    "wait": wait_random_exponential(multiplier=1, min=1, max=20),
    "stop": stop_after_attempt(MAX_ATTEMPTS),
    "before_sleep": _log_retry,
    "reraise": True,
}

groq_retry = retry(retry=retry_if_exception_type(GROQ_RETRYABLE), **_common)
tavily_retry = retry(retry=retry_if_exception(_tavily_is_retryable), **_common)
