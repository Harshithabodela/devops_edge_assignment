# Performance Budget Report
## Edge Observability Stack — 10xConstruction DevOps Intern Assignment

---

## 1. Memory Usage — Before vs. After

| Component | Before (unoptimised) | After (optimised) | Saving |
|---|---|---|---|
| **sensor-service** | ~120 MB | ~40 MB | -67% |
| **prometheus** | ~160 MB | ~80 MB | -50% |
| **grafana** | ~220 MB | ~100 MB | -55% |
| **Total** | ~500 MB OVER BUDGET | ~220 MB OK | -56% |

The original stack nearly exhausted the full 500 MB device RAM, leaving nothing for the OS.
The optimised stack uses ~220 MB, keeping ~280 MB free for the OS and kernel buffers.

---

## 2. Identified Bottlenecks in the Python Service

### 2.1 — 5 MB Global Blob (Permanent RAM Waste)

BEFORE (bug):
    data_blob = "X" * 5_000_000   # 5 MB always in RAM

Allocated at import time and never freed. Also returned over HTTP on 20% of /sensor requests,
serialising 5 MB into JSON — another 5-10 MB per response.

Fix: Removed data_blob entirely. /sensor returns a small numeric reading.

---

### 2.2 — Random In-Memory Multiplication on Every Scrape

BEFORE (bug):
    temp_data = data_blob * random.randint(1, 3)  # 5-15 MB per /metrics call!

Prometheus scraped /metrics every 5 seconds. Each call silently allocated 5-15 MB
that the GC had to reclaim, causing RAM spikes every 5 s and GC pauses -> scrape timeouts.

Fix: Line removed entirely.

---

### 2.3 — CPU Burn Loop on Every Scrape

BEFORE (bug):
    for _ in range(2000000):
        pass   # pure CPU burn, ~0.5-1 s on a 2 GHz core

Saturated one core ~80% of the time, delaying HTTP responses and triggering Prometheus
"context deadline exceeded" scrape failures.

Fix: Replaced with time.sleep(random.uniform(0.001, 0.005)) — realistic 1-5 ms latency,
zero CPU cost.

---

### 2.4 — Aggressive 5-Second Scrape Interval

With /metrics taking 0.5-1+ s, a 5 s scrape interval meant Prometheus was continuously
re-issuing slow scrapes, compounding the CPU problem.

Fix: scrape_interval raised to 30s with explicit scrape_timeout: 10s.

---

### 2.5 — Flask Dev Server in Production

python sensor_service.py uses Flask's single-threaded dev server. One blocked scrape
stalled all other HTTP requests.

Fix: Switched to Gunicorn (2 workers x 2 threads). Workers recycled after 500 requests
(--max-requests 500) to prevent gradual memory creep from GC fragmentation.

---

## 3. Observability Design Decisions

- Hard memory limits (deploy.resources.limits): Docker OOM-kills a runaway container
  instead of starving the whole device.

- Named volumes (prometheus_data, grafana_data): Data survives restarts; edge devices
  may power-cycle unexpectedly.

- Health checks + depends_on service_healthy: Prometheus does not scrape until sensor
  service is ready — no false-alarm failures on startup.

- Pinned image versions: Reproducible builds; no surprise memory regressions from an
  unexpected "latest" update.

---

## 4. Prometheus Choice Justification (Option A)

Chosen over VictoriaMetrics / Mimir / OpenTelemetry Collector because:
- de-facto standard; ops teams know PromQL
- Memory tuning flags are sufficient to stay within budget
- First-class Grafana data source, no adapter layer needed

Key flags applied:
  --storage.tsdb.wal-compression       Snappy-compresses WAL; ~40% RAM reduction
  --storage.tsdb.retention.time=24h    Short history suits edge
  --query.max-concurrency=2            Caps concurrent queries to prevent RAM spikes
  --query.timeout=30s                  Kills runaway queries instead of hanging

---

## 5. Grafana Choice Justification

Terminal dashboard (grafterm, ~5 MB) was considered but Grafana OSS was chosen for:
- Pre-built provisioned dashboards can be version-controlled and reproduced exactly
- Built-in alerting on sensor_failed_events_total without extra tooling

Memory kept under control by:
  GF_RENDERING_SERVER_URL=""           Disables headless-Chrome renderer (-80 MB)
  GF_ANALYTICS_REPORTING_ENABLED=false Stops background telemetry goroutines
  GF_LOG_LEVEL=warn                    Reduces I/O from verbose logging
  GF_DATABASE_WAL=true                 SQLite WAL - prevents corruption on power loss

---

## 6. Custom Metric: sensor_failed_events_total

    FAILED_EVENTS = Counter(
        "sensor_failed_events_total",
        "Total number of sensor reading events that failed or were discarded",
    )

Why a Counter: monotonically increasing, never misleadingly resets.

Useful PromQL:
    rate(sensor_failed_events_total[5m])      # failure rate per second
    increase(sensor_failed_events_total[1h])  # total failures in 1 hour

Alert rule example:
    - alert: SensorFailureRateHigh
      expr: rate(sensor_failed_events_total[5m]) > 0.01
      for: 2m
      labels: { severity: warning }

On an autonomous robot, silent data loss is dangerous. This counter gives an early
signal before missing data becomes a safety issue.

---

## 7. One Improvement With One More Week

Structured logging correlated with Loki:

1. Replace random failure simulation with real exception handling - emit structured JSON:
   {"event": "sensor_failure", "reason": "timeout", "timestamp": "..."}

2. Add Loki (~30 MB loki-canary) to Docker Compose.

3. In Grafana, correlated view - metrics spike links to exact log lines explaining why
   the failure occurred.

This closes the observability loop: metrics -> logs -> root cause.

---

Report by: Harshitha Bodela | 10xConstruction DevOps Intern Assignment
