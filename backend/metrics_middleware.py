import time
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from backend.services.metrics_service import metrics


class PerformanceMetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        method = request.method
        endpoint = request.url.path

        metrics.inc_active_requests(method, endpoint)
        start = time.time()
        status_code = 500

        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        finally:
            duration = time.time() - start
            metrics.record_request(method, endpoint, status_code, duration)
            metrics.dec_active_requests(method, endpoint)
