"""
Reliability Module

Provides reliability patterns for API calls:
- Rate limiting (RPM/TPM)
- Circuit breaker
- Custom exceptions
"""

import time
import logging
from dataclasses import dataclass, field
from typing import Optional, List, Tuple
from threading import Lock

logger = logging.getLogger(__name__)


# =============================================================================
# Custom Exceptions
# =============================================================================

class LLMError(Exception):
    """Base exception for LLM-related errors."""
    pass


class RateLimitExceeded(LLMError):
    """Raised when rate limit is exceeded and wait would be too long."""
    pass


class CircuitOpenError(LLMError):
    """Raised when circuit breaker is open."""
    pass


class APITimeoutError(LLMError):
    """Raised when API request times out."""
    pass


# =============================================================================
# Rate Limiter
# =============================================================================

@dataclass
class RateLimiter:
    """
    Token bucket rate limiter for API calls.

    Tracks both requests per minute (RPM) and tokens per minute (TPM).
    Thread-safe implementation using sliding window.

    Args:
        rpm_limit: Max requests per minute (0 = disabled)
        tpm_limit: Max tokens per minute (0 = disabled)
    """
    rpm_limit: int = 60
    tpm_limit: int = 90000
    _lock: Lock = field(default_factory=Lock, repr=False)
    _request_timestamps: List[float] = field(default_factory=list, repr=False)
    _token_usage: List[Tuple[float, int]] = field(default_factory=list, repr=False)

    def _cleanup_old_entries(self, now: float) -> None:
        """Remove entries older than 60 seconds."""
        cutoff = now - 60.0
        self._request_timestamps = [t for t in self._request_timestamps if t > cutoff]
        self._token_usage = [(t, tokens) for t, tokens in self._token_usage if t > cutoff]

    def check_and_wait(self, estimated_tokens: int = 0) -> None:
        """
        Check rate limits and wait if necessary.

        Args:
            estimated_tokens: Estimated tokens for upcoming request

        Note:
            Will sleep if rate limit is approached. Logs warnings when waiting.
        """
        with self._lock:
            now = time.time()
            self._cleanup_old_entries(now)

            # Check RPM
            if self.rpm_limit > 0 and len(self._request_timestamps) >= self.rpm_limit:
                oldest = min(self._request_timestamps)
                wait_time = 60.0 - (now - oldest)
                if wait_time > 0:
                    logger.warning(f"RPM limit reached, waiting {wait_time:.1f}s")
                    time.sleep(wait_time)
                    now = time.time()
                    self._cleanup_old_entries(now)

            # Check TPM
            if self.tpm_limit > 0 and self._token_usage:
                current_tokens = sum(tokens for _, tokens in self._token_usage)
                if current_tokens + estimated_tokens > self.tpm_limit:
                    oldest_token = min(t for t, _ in self._token_usage)
                    wait_time = 60.0 - (now - oldest_token)
                    if wait_time > 0:
                        logger.warning(f"TPM limit reached ({current_tokens} tokens used), waiting {wait_time:.1f}s")
                        time.sleep(wait_time)
                        now = time.time()
                        self._cleanup_old_entries(now)

    def record_request(self, tokens_used: int = 0) -> None:
        """
        Record a completed request for rate limiting.

        Args:
            tokens_used: Number of tokens consumed by this request
        """
        with self._lock:
            now = time.time()
            self._request_timestamps.append(now)
            if tokens_used > 0:
                self._token_usage.append((now, tokens_used))

    def get_current_usage(self) -> dict:
        """Get current rate limit usage statistics."""
        with self._lock:
            now = time.time()
            self._cleanup_old_entries(now)
            return {
                "requests_in_window": len(self._request_timestamps),
                "tokens_in_window": sum(tokens for _, tokens in self._token_usage),
                "rpm_limit": self.rpm_limit,
                "tpm_limit": self.tpm_limit,
            }


# =============================================================================
# Circuit Breaker
# =============================================================================

class CircuitBreaker:
    """
    Circuit breaker pattern for fault tolerance.

    Prevents cascading failures by temporarily blocking requests after
    repeated failures. Automatically tests recovery after timeout.

    States:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Too many failures, requests blocked
    - HALF_OPEN: Testing if service recovered

    Args:
        failure_threshold: Number of failures before circuit opens
        reset_timeout: Seconds before circuit transitions to half-open
    """

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

    def __init__(self, failure_threshold: int = 5, reset_timeout: float = 60.0):
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self._state = self.CLOSED
        self._failure_count = 0
        self._last_failure_time: Optional[float] = None
        self._lock = Lock()

    @property
    def state(self) -> str:
        """Get current circuit state, checking for timeout transition."""
        with self._lock:
            if self._state == self.OPEN:
                # Check if we should transition to half-open
                if self._last_failure_time and \
                   time.time() - self._last_failure_time >= self.reset_timeout:
                    self._state = self.HALF_OPEN
                    logger.info("Circuit breaker transitioning to HALF_OPEN")
            return self._state

    @property
    def failure_count(self) -> int:
        """Get current failure count."""
        with self._lock:
            return self._failure_count

    def check(self) -> None:
        """
        Check if request should proceed.

        Raises:
            CircuitOpenError: If circuit is open and requests are blocked
        """
        state = self.state
        if state == self.OPEN:
            raise CircuitOpenError(
                f"Circuit breaker is open after {self.failure_threshold} failures. "
                f"Retry after {self.reset_timeout}s"
            )

    def record_success(self) -> None:
        """Record successful request, resetting failure count."""
        with self._lock:
            self._failure_count = 0
            self._state = self.CLOSED
            logger.debug("Circuit breaker: success recorded, state=CLOSED")

    def record_failure(self) -> None:
        """Record failed request, potentially opening circuit."""
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()

            if self._failure_count >= self.failure_threshold:
                self._state = self.OPEN
                logger.warning(
                    f"Circuit breaker OPEN after {self._failure_count} consecutive failures"
                )
            else:
                logger.debug(
                    f"Circuit breaker: failure {self._failure_count}/{self.failure_threshold}"
                )

    def reset(self) -> None:
        """Manually reset circuit breaker to closed state."""
        with self._lock:
            self._state = self.CLOSED
            self._failure_count = 0
            self._last_failure_time = None
            logger.info("Circuit breaker manually reset to CLOSED")

    def get_status(self) -> dict:
        """Get current circuit breaker status."""
        return {
            "state": self.state,
            "failure_count": self._failure_count,
            "failure_threshold": self.failure_threshold,
            "reset_timeout": self.reset_timeout,
        }
