"""
Tests for reliability features.

Run with: pytest app/tests/test_reliability.py -v
"""

import time
import pytest
from unittest.mock import Mock, patch

import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.reliability import (
    RateLimiter,
    CircuitBreaker,
    CircuitOpenError,
    LLMError,
    RateLimitExceeded,
)


class TestRateLimiter:
    """Tests for RateLimiter class."""

    def test_init_with_defaults(self):
        """Should initialize with default limits."""
        limiter = RateLimiter()
        assert limiter.rpm_limit == 60
        assert limiter.tpm_limit == 90000

    def test_init_with_custom_limits(self):
        """Should accept custom limits."""
        limiter = RateLimiter(rpm_limit=10, tpm_limit=1000)
        assert limiter.rpm_limit == 10
        assert limiter.tpm_limit == 1000

    def test_allows_requests_under_rpm_limit(self):
        """Should allow requests when under RPM limit."""
        limiter = RateLimiter(rpm_limit=10, tpm_limit=100000)

        # Should not raise or wait significantly
        for _ in range(5):
            limiter.check_and_wait(estimated_tokens=100)
            limiter.record_request(tokens_used=100)

    def test_tracks_token_usage(self):
        """Should track token usage correctly."""
        limiter = RateLimiter(rpm_limit=100, tpm_limit=10000)

        limiter.record_request(tokens_used=500)
        limiter.record_request(tokens_used=300)

        usage = limiter.get_current_usage()
        assert usage["requests_in_window"] == 2
        assert usage["tokens_in_window"] == 800

    def test_get_current_usage(self):
        """Should return current usage statistics."""
        limiter = RateLimiter(rpm_limit=60, tpm_limit=90000)

        usage = limiter.get_current_usage()
        assert "requests_in_window" in usage
        assert "tokens_in_window" in usage
        assert "rpm_limit" in usage
        assert "tpm_limit" in usage

    def test_disabled_limits(self):
        """Should allow unlimited requests when limits are 0."""
        limiter = RateLimiter(rpm_limit=0, tpm_limit=0)

        # Should not wait even with many requests
        for _ in range(100):
            limiter.check_and_wait(estimated_tokens=10000)
            limiter.record_request(tokens_used=10000)


class TestCircuitBreaker:
    """Tests for CircuitBreaker class."""

    def test_starts_closed(self):
        """Should start in closed state."""
        cb = CircuitBreaker(failure_threshold=3)
        assert cb.state == CircuitBreaker.CLOSED

    def test_stays_closed_under_threshold(self):
        """Should stay closed when failures are under threshold."""
        cb = CircuitBreaker(failure_threshold=3)

        cb.record_failure()
        assert cb.state == CircuitBreaker.CLOSED
        assert cb.failure_count == 1

        cb.record_failure()
        assert cb.state == CircuitBreaker.CLOSED
        assert cb.failure_count == 2

    def test_opens_after_threshold(self):
        """Should open after reaching failure threshold."""
        cb = CircuitBreaker(failure_threshold=3)

        cb.record_failure()
        cb.record_failure()
        cb.record_failure()

        assert cb.state == CircuitBreaker.OPEN
        assert cb.failure_count == 3

    def test_blocks_when_open(self):
        """Should raise CircuitOpenError when circuit is open."""
        cb = CircuitBreaker(failure_threshold=1)
        cb.record_failure()

        assert cb.state == CircuitBreaker.OPEN

        with pytest.raises(CircuitOpenError):
            cb.check()

    def test_allows_when_closed(self):
        """Should not raise when circuit is closed."""
        cb = CircuitBreaker(failure_threshold=3)

        # Should not raise
        cb.check()

    def test_resets_on_success(self):
        """Should reset to closed on success."""
        cb = CircuitBreaker(failure_threshold=3)

        cb.record_failure()
        cb.record_failure()
        assert cb.failure_count == 2

        cb.record_success()

        assert cb.state == CircuitBreaker.CLOSED
        assert cb.failure_count == 0

    def test_half_open_after_timeout(self):
        """Should transition to half-open after timeout."""
        cb = CircuitBreaker(failure_threshold=1, reset_timeout=0.1)
        cb.record_failure()

        assert cb.state == CircuitBreaker.OPEN

        # Wait for timeout
        time.sleep(0.15)

        assert cb.state == CircuitBreaker.HALF_OPEN

    def test_manual_reset(self):
        """Should allow manual reset to closed state."""
        cb = CircuitBreaker(failure_threshold=1)
        cb.record_failure()

        assert cb.state == CircuitBreaker.OPEN

        cb.reset()

        assert cb.state == CircuitBreaker.CLOSED
        assert cb.failure_count == 0

    def test_get_status(self):
        """Should return current status."""
        cb = CircuitBreaker(failure_threshold=5, reset_timeout=30.0)

        status = cb.get_status()
        assert status["state"] == CircuitBreaker.CLOSED
        assert status["failure_count"] == 0
        assert status["failure_threshold"] == 5
        assert status["reset_timeout"] == 30.0

    def test_closes_from_half_open_on_success(self):
        """Should close from half-open state on success."""
        cb = CircuitBreaker(failure_threshold=1, reset_timeout=0.1)
        cb.record_failure()

        assert cb.state == CircuitBreaker.OPEN

        time.sleep(0.15)
        assert cb.state == CircuitBreaker.HALF_OPEN

        cb.record_success()
        assert cb.state == CircuitBreaker.CLOSED


class TestExceptions:
    """Tests for custom exceptions."""

    def test_llm_error_is_exception(self):
        """LLMError should be a proper exception."""
        with pytest.raises(LLMError):
            raise LLMError("Test error")

    def test_circuit_open_error_is_llm_error(self):
        """CircuitOpenError should be a subclass of LLMError."""
        assert issubclass(CircuitOpenError, LLMError)

        with pytest.raises(LLMError):
            raise CircuitOpenError("Circuit is open")

    def test_rate_limit_exceeded_is_llm_error(self):
        """RateLimitExceeded should be a subclass of LLMError."""
        assert issubclass(RateLimitExceeded, LLMError)


class TestRateLimiterThreadSafety:
    """Tests for thread safety of RateLimiter."""

    def test_concurrent_requests(self):
        """Should handle concurrent requests safely."""
        import threading

        limiter = RateLimiter(rpm_limit=100, tpm_limit=100000)
        errors = []

        def make_request():
            try:
                limiter.check_and_wait(estimated_tokens=100)
                limiter.record_request(tokens_used=100)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=make_request) for _ in range(20)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        usage = limiter.get_current_usage()
        assert usage["requests_in_window"] == 20


class TestCircuitBreakerThreadSafety:
    """Tests for thread safety of CircuitBreaker."""

    def test_concurrent_failures(self):
        """Should handle concurrent failures safely."""
        import threading

        cb = CircuitBreaker(failure_threshold=50)
        errors = []

        def record_failure():
            try:
                cb.record_failure()
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=record_failure) for _ in range(100)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        # Should be open after 50+ failures
        assert cb.state == CircuitBreaker.OPEN
