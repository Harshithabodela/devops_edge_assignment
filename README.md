# Edge Sensor Observability Stack

Lightweight Prometheus + Grafana observability stack for a 2-core / 500 MB RAM
edge device. Total footprint stays comfortably under **300 MB RAM**.

## Memory budget

| Service        | Image                          | RAM limit | Typical use |
| -------------- | ------------------------------ | --------: | ----------: |
| sensor-service | python:3.11-slim (multi-stage) |     50 MB |      ~40 MB |
| prometheus     | prom/prometheus:v2.51.2        |     90 MB |      ~75 MB |
| grafana        | grafana/grafana-oss:10.4.2     |    130 MB |     ~100 MB |
| **Total**      |                                | **270 MB** | **~215 MB** |

## Quick start

```bash
docker compose up -d --build
docker compose ps
```

Then open:

- Sensor metrics — http://localhost:8000/metrics
- HTML dashboard — http://localhost:8000/dashboard
- Prometheus    — http://localhost:9090
- Grafana       — http://localhost:3000  (anonymous viewer, no login)

## Project layout

```
.
├── sensor_service.py              # Optimised Python sensor service
├── requirements.txt
├── Dockerfile                     # Multi-stage slim image + gunicorn
├── docker-compose.yml             # Stack with memory & CPU limits
├── prometheus.yml                 # 30 s scrape interval, WAL compression
├── dashboard.html                 # Static HTML dashboard (served at /dashboard)
├── PERFORMANCE_BUDGET_REPORT.md   # Full analysis
└── grafana/provisioning/          # Auto-provisioned datasource + dashboard
```

## Bugs fixed in the provided service

| Original bug                              | Impact                              | Fix                              |
| ----------------------------------------- | ----------------------------------- | -------------------------------- |
| `data_blob = "X" * 5_000_000`             | 5 MB permanent RAM waste            | Removed                          |
| `data_blob * randint(1,3)` on every call  | 5–15 MB allocation per scrape       | Removed                          |
| `for _ in range(2_000_000): pass`         | CPU burn, ~1 s on a 2 GHz core      | `time.sleep(0.001–0.005)`        |
| `/sensor` returns 5 MB JSON (20% of time) | Huge response, blocks the worker    | Returns a tiny numeric value     |
| `scrape_interval: 5s`                     | Continuous scrape timeouts          | Raised to `30s`                  |
| Flask dev server                          | Single-threaded; one slow call hangs all | Gunicorn (2 workers × 2 threads) |

## Metrics exposed

| Metric                              | Type      | Purpose                                       |
| ----------------------------------- | --------- | --------------------------------------------- |
| `sensor_requests_total`             | Counter   | Total /metrics scrapes                        |
| `sensor_value`                      | Gauge     | Latest simulated sensor reading               |
| `sensor_cpu_spike`                  | Gauge     | Simulated CPU-spike state (0 / 1)             |
| `sensor_processing_latency_seconds` | Histogram | Time to build a /metrics response             |
| `sensor_failed_events_total`        | Counter   | **Custom metric** — discarded sensor events   |

## Custom metric — `sensor_failed_events_total`

A monotonic counter of dropped sensor events. On an autonomous robot, silent
data loss is dangerous; this counter is the earliest signal before missing data
becomes a safety issue.

```promql
# Alert when >1 % of events fail for 2 m
rate(sensor_failed_events_total[5m]) > 0.01
```

## Grafana dashboard

Four panels auto-provisioned on first boot: request rate, p50/p95 latency,
sensor value, and failed events (5 min window).

## Performance report

See [PERFORMANCE_BUDGET_REPORT.md](./PERFORMANCE_BUDGET_REPORT.md).
video walkthrough -- https://drive.google.com/file/d/1mEF2NK6fpwQ90eHOOr1f99JI6ZmnY7Ag/view?usp=sharing

