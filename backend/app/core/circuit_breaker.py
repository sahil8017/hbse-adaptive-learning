import asyncio
import logging
import time
from typing import Callable, Any, AsyncGenerator
import sentry_sdk

try:
    from backend.app.core.metrics import llm_circuit_breaker_status
except ImportError:
    llm_circuit_breaker_status = None

logger = logging.getLogger(__name__)

class CircuitBreakerOpenException(Exception):
    """Exception raised when a request is blocked because the circuit breaker is OPEN."""
    pass

class AsyncCircuitBreaker:
    """
    A custom async-aware, thread-safe Circuit Breaker.
    States: CLOSED, OPEN, HALF_OPEN
    """
    def __init__(self, name: str, fail_max: int = 3, reset_timeout: float = 120.0):
        self.name = name
        self.fail_max = fail_max
        self.reset_timeout = reset_timeout
        
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
        self.failure_count = 0
        self.opened_at = 0.0
        
        self._lock = asyncio.Lock()
        self._update_metrics()
        
    def _update_metrics(self):
        """Update Prometheus gauge for the circuit breaker status."""
        if llm_circuit_breaker_status:
            val = 1.0 if self.state == "OPEN" else 0.0
            try:
                llm_circuit_breaker_status.labels(service=self.name).set(val)
            except Exception as e:
                logger.debug(f"Failed to update Prometheus metrics for breaker {self.name}: {e}")

    async def _check_state(self):
        """Check current state, handling transition from OPEN to HALF_OPEN after timeout."""
        if self.state == "OPEN":
            elapsed = time.time() - self.opened_at
            if elapsed >= self.reset_timeout:
                self.state = "HALF_OPEN"
                logger.info(f"Circuit breaker '{self.name}' transitioned to HALF_OPEN after timeout.")
                self._update_metrics()

    async def before_call(self):
        """Pre-execution check. Raises CircuitBreakerOpenException if OPEN."""
        async with self._lock:
            await self._check_state()
            if self.state == "OPEN":
                raise CircuitBreakerOpenException(
                    f"Circuit breaker '{self.name}' is OPEN. Blocking request."
                )

    async def record_success(self):
        """Record a successful execution, closing the circuit if HALF_OPEN."""
        async with self._lock:
            if self.state == "HALF_OPEN":
                self.state = "CLOSED"
                self.failure_count = 0
                logger.info(f"Circuit breaker '{self.name}' has been CLOSED after successful test call.")
                self._update_metrics()
            elif self.state == "CLOSED":
                self.failure_count = 0

    async def record_failure(self, error: Exception = None):
        """Record an execution failure, potentially opening the circuit."""
        async with self._lock:
            self.failure_count += 1
            logger.warning(
                f"Circuit breaker '{self.name}' recorded failure #{self.failure_count}. Error: {error}"
            )
            
            if self.state in ["CLOSED", "HALF_OPEN"]:
                if self.state == "HALF_OPEN" or self.failure_count >= self.fail_max:
                    self.state = "OPEN"
                    self.opened_at = time.time()
                    logger.error(
                        f"Circuit breaker '{self.name}' TRIPPED to OPEN. "
                        f"Blocking requests for the next {self.reset_timeout}s."
                    )
                    sentry_sdk.capture_message(
                        f"Circuit breaker '{self.name}' TRIPPED to OPEN due to consecutive failures.",
                        level="error"
                    )
                    self._update_metrics()

    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute an asynchronous function wrapped by the circuit breaker."""
        await self.before_call()
        try:
            res = await func(*args, **kwargs)
            await self.record_success()
            return res
        except Exception as e:
            await self.record_failure(e)
            raise

    async def call_generator(self, gen_func: Callable, *args, **kwargs) -> AsyncGenerator[Any, None]:
        """Iterate over an async generator wrapped by the circuit breaker."""
        await self.before_call()
        success = False
        try:
            # We must resolve the generator after checking before_call
            gen = gen_func(*args, **kwargs)
            async for val in gen:
                # We yield each token as they arrive
                yield val
            success = True
        except Exception as e:
            await self.record_failure(e)
            raise
        finally:
            if success:
                await self.record_success()
