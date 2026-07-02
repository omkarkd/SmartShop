import time
import threading
from collections import defaultdict
from datetime import datetime, timezone
from typing import Dict, List, Optional
from backend.database import db


class MetricsService:
    def __init__(self):
        self._lock = threading.Lock()

        self._request_counts: Dict[str, int] = defaultdict(int)
        self._error_counts: Dict[str, int] = defaultdict(int)
        self._status_counts: Dict[str, int] = defaultdict(int)

        self._latencies: Dict[str, List[float]] = defaultdict(list)

        self._active_requests: Dict[str, int] = defaultdict(int)

        self._scraper_runs: List[dict] = []

        self._db_query_times: Dict[str, List[float]] = defaultdict(list)
        self._db_error_counts: Dict[str, int] = defaultdict(int)

        self._start_time = time.time()

    # ---- HTTP Metrics ----

    def record_request(self, method: str, endpoint: str, status_code: int, duration: float):
        key = f"{method} {endpoint}"
        with self._lock:
            self._request_counts[key] += 1
            self._status_counts[f"{key} {status_code}"] += 1
            if status_code >= 400:
                self._error_counts[key] += 1
            self._latencies[key].append(duration)
            self._active_requests[key] = max(0, self._active_requests.get(key, 0))
            if len(self._latencies[key]) > 10000:
                self._latencies[key] = self._latencies[key][-5000:]

    def inc_active_requests(self, method: str, endpoint: str):
        key = f"{method} {endpoint}"
        with self._lock:
            self._active_requests[key] += 1

    def dec_active_requests(self, method: str, endpoint: str):
        key = f"{method} {endpoint}"
        with self._lock:
            self._active_requests[key] = max(0, self._active_requests.get(key, 0) - 1)

    # ---- Database Metrics ----

    def record_db_query(self, operation: str, duration: float):
        with self._lock:
            self._db_query_times[operation].append(duration)
            if len(self._db_query_times[operation]) > 10000:
                self._db_query_times[operation] = self._db_query_times[operation][-5000:]

    def record_db_error(self, operation: str):
        with self._lock:
            self._db_error_counts[operation] += 1

    # ---- Scraper Metrics ----

    def record_scraper_run(self, retailer: str, categories_total: int, categories_success: int,
                           categories_failed: int, products_total: int, duration_seconds: float,
                           status: str = "completed"):
        with self._lock:
            self._scraper_runs.append({
                "retailer": retailer,
                "categories_total": categories_total,
                "categories_success": categories_success,
                "categories_failed": categories_failed,
                "products_total": products_total,
                "duration_seconds": duration_seconds,
                "status": status,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            if len(self._scraper_runs) > 1000:
                self._scraper_runs = self._scraper_runs[-500:]

    def persist_scraper_metric(self, metric: dict):
        try:
            db["performance_metrics"].insert_one(metric)
        except Exception:
            pass

    # ---- Helpers ----

    @staticmethod
    def _percentile(data: List[float], p: float) -> float:
        if not data:
            return 0.0
        sorted_data = sorted(data)
        k = (len(sorted_data) - 1) * p / 100.0
        f = int(k)
        c = f + 1
        if c >= len(sorted_data):
            return sorted_data[-1]
        return sorted_data[f] + (k - f) * (sorted_data[c] - sorted_data[f])

    def _stats_for(self, latencies: List[float]) -> dict:
        if not latencies:
            return {"min": 0, "max": 0, "avg": 0, "p50": 0, "p95": 0, "p99": 0, "count": 0}
        return {
            "min": round(min(latencies), 4),
            "max": round(max(latencies), 4),
            "avg": round(sum(latencies) / len(latencies), 4),
            "p50": round(self._percentile(latencies, 50), 4),
            "p95": round(self._percentile(latencies, 95), 4),
            "p99": round(self._percentile(latencies, 99), 4),
            "count": len(latencies),
        }

    def get_snapshot(self) -> dict:
        with self._lock:
            endpoints = {}
            all_keys = set(list(self._request_counts.keys()) + list(self._active_requests.keys()))
            for key in sorted(all_keys):
                latencies = self._latencies.get(key, [])
                endpoints[key] = {
                    "requests": self._request_counts.get(key, 0),
                    "errors": self._error_counts.get(key, 0),
                    "active": self._active_requests.get(key, 0),
                    "latency": self._stats_for(latencies),
                }

            db_metrics = {}
            for op in sorted(self._db_query_times.keys()):
                db_metrics[op] = {
                    **self._stats_for(self._db_query_times[op]),
                    "errors": self._db_error_counts.get(op, 0),
                }

            return {
                "uptime_seconds": round(time.time() - self._start_time, 2),
                "server_start": datetime.fromtimestamp(self._start_time, tz=timezone.utc).isoformat(),
                "total_requests": sum(self._request_counts.values()),
                "total_errors": sum(self._error_counts.values()),
                "total_active": sum(self._active_requests.values()),
                "endpoints": endpoints,
                "database": db_metrics,
                "scraper_runs_total": len(self._scraper_runs),
                "scraper_latest": self._scraper_runs[-5:] if self._scraper_runs else [],
            }


metrics = MetricsService()
