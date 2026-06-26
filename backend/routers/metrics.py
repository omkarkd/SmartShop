from fastapi import APIRouter
from fastapi.responses import JSONResponse, PlainTextResponse
from backend.services.metrics_service import metrics

router = APIRouter(tags=["metrics"])


@router.get("/api/metrics")
def get_metrics():
    return JSONResponse(metrics.get_snapshot())


@router.get("/api/metrics/scrapers")
def get_scraper_metrics(limit: int = 10):
    try:
        from backend.database import db
        cursor = db["performance_metrics"].find(
            {"type": "scraper_run"}
        ).sort("timestamp", -1).limit(limit)
        results = []
        for doc in cursor:
            doc["_id"] = str(doc["_id"])
            if hasattr(doc.get("timestamp"), "isoformat"):
                doc["timestamp"] = doc["timestamp"].isoformat()
            results.append(doc)
        return {"scraper_runs": results}
    except Exception as e:
        return {"error": str(e)}


@router.get("/api/metrics/scrapers/summary")
def get_scraper_summary():
    try:
        from backend.database import db
        pipeline = [
            {"$match": {"type": "scraper_run"}},
            {"$sort": {"timestamp": -1}},
            {"$group": {
                "_id": "$retailer",
                "last_run": {"$first": "$timestamp"},
                "last_products": {"$first": "$products_total"},
                "last_duration": {"$first": "$duration_seconds"},
                "last_status": {"$first": "$status"},
                "total_runs": {"$sum": 1},
                "avg_products": {"$avg": "$products_total"},
                "avg_duration": {"$avg": "$duration_seconds"},
            }}
        ]
        results = []
        for doc in db["performance_metrics"].aggregate(pipeline):
            doc["_id"] = str(doc["_id"])
            if hasattr(doc.get("last_run"), "isoformat"):
                doc["last_run"] = doc["last_run"].isoformat()
            doc["avg_products"] = round(doc["avg_products"], 1)
            doc["avg_duration"] = round(doc["avg_duration"], 1)
            results.append(doc)
        return {"summary": results}
    except Exception as e:
        return {"error": str(e)}


@router.get("/metrics")
def prometheus_metrics():
    snapshot = metrics.get_snapshot()
    lines = [
        "# HELP smartshop_uptime_seconds Server uptime",
        "# TYPE smartshop_uptime_seconds gauge",
        f"smartshop_uptime_seconds {snapshot['uptime_seconds']}",
        "",
        "# HELP smartshop_requests_total Total request count",
        "# TYPE smartshop_requests_total counter",
        f"smartshop_requests_total {snapshot['total_requests']}",
        "",
        "# HELP smartshop_errors_total Total error count",
        "# TYPE smartshop_errors_total counter",
        f"smartshop_errors_total {snapshot['total_errors']}",
        "",
        "# HELP smartshop_active_requests Currently active requests",
        "# TYPE smartshop_active_requests gauge",
        f"smartshop_active_requests {snapshot['total_active']}",
        "",
    ]

    for endpoint, data in snapshot.get("endpoints", {}).items():
        method, path = endpoint.split(" ", 1)
        labels = f'method="{method}",endpoint="{path}"'

        lines.append(f"# HELP smartshop_endpoint_requests_total Request count per endpoint")
        lines.append(f"# TYPE smartshop_endpoint_requests_total counter")
        lines.append(f"smartshop_endpoint_requests_total{{{labels}}} {data['requests']}")

        lines.append(f"# HELP smartshop_endpoint_errors_total Error count per endpoint")
        lines.append(f"# TYPE smartshop_endpoint_errors_total counter")
        lines.append(f"smartshop_endpoint_errors_total{{{labels}}} {data['errors']}")

        lines.append(f"# HELP smartshop_endpoint_active_requests Active requests per endpoint")
        lines.append(f"# TYPE smartshop_endpoint_active_requests gauge")
        lines.append(f"smartshop_endpoint_active_requests{{{labels}}} {data['active']}")

        lat = data["latency"]
        lines.append(f"# HELP smartshop_endpoint_request_duration_seconds Request latency per endpoint")
        lines.append(f"# TYPE smartshop_endpoint_request_duration_seconds gauge")
        lines.append(f"smartshop_endpoint_request_duration_seconds{{{labels},quantile=\"avg\"}} {lat['avg']}")
        lines.append(f"smartshop_endpoint_request_duration_seconds{{{labels},quantile=\"p50\"}} {lat['p50']}")
        lines.append(f"smartshop_endpoint_request_duration_seconds{{{labels},quantile=\"p95\"}} {lat['p95']}")
        lines.append(f"smartshop_endpoint_request_duration_seconds{{{labels},quantile=\"p99\"}} {lat['p99']}")
        lines.append(f"smartshop_endpoint_request_duration_seconds{{{labels},quantile=\"min\"}} {lat['min']}")
        lines.append(f"smartshop_endpoint_request_duration_seconds{{{labels},quantile=\"max\"}} {lat['max']}")

    for run in snapshot.get("scraper_latest", []):
        r_labels = f'retailer="{run["retailer"]}",status="{run["status"]}"'
        lines.append(f"smartshop_scraper_products_total{{{r_labels}}} {run['products_total']}")
        lines.append(f"smartshop_scraper_categories_total{{{r_labels}}} {run['categories_total']}")
        lines.append(f"smartshop_scraper_duration_seconds{{{r_labels}}} {run['duration_seconds']}")

    return PlainTextResponse("\n".join(lines) + "\n")
