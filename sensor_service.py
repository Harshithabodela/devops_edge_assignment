"""Edge sensor service — exposes /metrics, /sensor, /health, /dashboard."""

import os
import time
import random
import logging

from flask import Flask, Response, jsonify, send_from_directory
from prometheus_client import (
    Counter, Gauge, Histogram,
    generate_latest, CONTENT_TYPE_LATEST,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

app = Flask(__name__)

# ── Prometheus metrics ─────────────────────────────────────────────────────
REQUESTS = Counter(
    "sensor_requests_total",
    "Total /metrics scrapes served",
)
SENSOR_VALUE = Gauge(
    "sensor_value",
    "Latest simulated sensor reading (°C)",
)
CPU_SPIKE = Gauge(
    "sensor_cpu_spike",
    "Simulated CPU-spike state (0 = normal, 1 = spike)",
)
LATENCY = Histogram(
    "sensor_processing_latency_seconds",
    "Time to build a /metrics response",
    buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0],
)
# Custom metric required by the assignment
FAILED_EVENTS = Counter(
    "sensor_failed_events_total",
    "Total sensor events that failed or were discarded",
)


@app.route("/metrics")
def metrics():
    start = time.monotonic()

    # Cheap simulated sensor read (1–5 ms) — no CPU burn, no allocations
    time.sleep(random.uniform(0.001, 0.005))

    SENSOR_VALUE.set(round(random.uniform(20.0, 80.0), 2))
    CPU_SPIKE.set(1 if random.random() < 0.1 else 0)
    if random.random() < 0.05:
        FAILED_EVENTS.inc()

    REQUESTS.inc()
    LATENCY.observe(time.monotonic() - start)
    return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)


@app.route("/sensor")
def sensor():
    value = round(random.uniform(20.0, 80.0), 2)
    SENSOR_VALUE.set(value)
    return jsonify({"status": "ok", "value": value})


@app.route("/health")
def health():
    return jsonify({"status": "healthy"}), 200


@app.route("/dashboard")
def dashboard():
    return send_from_directory(os.path.dirname(os.path.abspath(__file__)), "dashboard.html")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
