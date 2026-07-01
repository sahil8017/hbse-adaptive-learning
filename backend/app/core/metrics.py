from prometheus_client import Counter, Histogram, Gauge
from functools import wraps
import time

# HTTP metrics
http_request_duration_seconds = Histogram(
    'http_request_duration_seconds',
    'HTTP request latency in seconds',
    ['method', 'endpoint', 'status'],
    buckets=(0.01, 0.05, 0.1, 0.3, 0.5, 1.0, 2.0, 5.0, 10.0),
)

http_requests_total = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status'],
)

# Database metrics
db_query_duration_seconds = Histogram(
    'db_query_duration_seconds',
    'Database query latency in seconds',
    ['query_type'],
    buckets=(0.001, 0.01, 0.05, 0.1, 0.5, 1.0),
)

db_connection_pool_size = Gauge(
    'db_connection_pool_size',
    'Active database connections in the pool',
)

db_connection_pool_max = Gauge(
    'db_connection_pool_max',
    'Max database connections in the pool',
)

# RAG metrics
rag_query_duration_seconds = Histogram(
    'rag_query_duration_seconds',
    'RAG retrieval latency in seconds',
    ['book_id', 'cache_hit'],
    buckets=(0.01, 0.05, 0.1, 0.3, 0.5, 1.0),
)

rag_query_no_results_total = Counter(
    'rag_query_no_results_total',
    'RAG queries returning no results',
    ['book_id'],
)

# LLM metrics
llm_call_duration_seconds = Histogram(
    'llm_call_duration_seconds',
    'LLM API call latency in seconds',
    ['provider', 'status'],
    buckets=(0.1, 0.5, 1.0, 3.0, 5.0, 10.0),
)

llm_circuit_breaker_status = Gauge(
    'llm_circuit_breaker_status',
    'Circuit breaker status (1=open, 0=closed)',
    ['service'],
)

# Cache metrics
cache_hits_total = Counter(
    'cache_hits_total',
    'Cache hits',
    ['cache_type'],
)

cache_misses_total = Counter(
    'cache_misses_total',
    'Cache misses',
    ['cache_type'],
)

# Practice/exam metrics
practice_submissions_total = Counter(
    'practice_submissions_total',
    'Total practice submissions',
    ['correct', 'chapter_id'],
)

exam_attempts_total = Counter(
    'exam_attempts_total',
    'Total exam attempts',
    ['passed', 'chapter_id'],
)

def record_latency(metric_name: str, labels: dict = None):
    """Decorator to record function execution time on a Prometheus metric."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start = time.time()
            try:
                result = await func(*args, **kwargs)
                elapsed = time.time() - start
                metric = globals()[metric_name]
                if labels:
                    metric.labels(**labels).observe(elapsed)
                else:
                    metric.observe(elapsed)
                return result
            except Exception:
                elapsed = time.time() - start
                metric = globals()[metric_name]
                if labels:
                    metric.labels(**labels).observe(elapsed)
                else:
                    metric.observe(elapsed)
                raise
        return wrapper
    return decorator
