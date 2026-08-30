# Observability stack

OpenTelemetry Collector + Prometheus + Loki + Tempo + Grafana, wired together so traces/metrics/logs sent to the collector land in a datasource Grafana already knows about.

This is a **separate Compose project** from the app (`../docker-compose.yml`) — its own lifecycle, its own network (`canvas-connect-observability`), started and stopped independently.

```
Collector (4317/4318, OTLP) --traces--> Tempo (3200)
                             --metrics-> scraped by Prometheus (9090)
                             --logs----> Loki (3100)

Grafana (3001) -- reads from Prometheus, Loki, and Tempo (pre-provisioned datasources)
```

## Run it

```
docker compose -f observability/docker-compose.yml up -d
```

Grafana: http://localhost:3001 (`admin`/`admin`, you'll be asked to change it on first login). A "Canvas Connect - Application Metrics" dashboard is pre-provisioned (`grafana/provisioning/dashboards/`) with `environment` and `version` filters at the top — see below.

## Feeding it from the app stack

On its own this stack has nothing sending it data. To point the app at the collector, bring the app stack up with the optional overlay at the repo root:

```
docker compose -f observability/docker-compose.yml up -d
docker compose -f docker-compose.yml -f docker-compose.observability.yml up -d
```

That overlay attaches the `app` service to this stack's network and sets `OTEL_EXPORTER_OTLP_ENDPOINT` — see `../backend/app/telemetry.py` for what the backend exports today (HTTP request and SQL query traces). It's opt-in and touches nothing else: plain `docker compose up` (CI, `make test-integration`, deploy) is unaffected.

## Currently wired vs. not

- **Traces**: flowing once the app is connected — see above.
- **Metrics**: flowing once the app is connected. The collector's own internal metrics are always scraped; the app additionally exports four counters (see `backend/app/telemetry.py`) — `canvas_connect.interview_rooms.created`, `canvas_connect.interview_participants.active`, `canvas_connect.canvas_elements.created`, `canvas_connect.component_creation.failures` — each joinable in PromQL against `target_info{exported_job="canvas-connect-backend"}` for `deployment_environment_name`/`service_version`. The provisioned dashboard already does this join — see below.
- **Logs**: the pipeline (collector → Loki) is ready, but the app doesn't ship logs via OTLP yet — nothing will show up in Loki until that's added.

## Dashboard

`grafana/provisioning/dashboards/json/canvas-connect-app-metrics.json` — one panel per application metric, plus a breakdown of failures by `reason`. Two dashboard variables at the top, **environment** and **version**, filter every panel; `version`'s options narrow to whatever's actually running in the selected `environment`.

Why the queries look the way they do: none of the four app metrics carry `deployment_environment_name`/`service_version` as labels directly — those live only on the synthetic `target_info` series each OTel resource produces. Every panel query is a `metric * on(exported_job, exported_instance) group_left(deployment_environment_name, service_version) target_info{...}` join to pull them in and filter by the variables (the `exported_` prefix is Prometheus's own doing: it renames the collector's `job`/`instance` labels on scrape since they'd otherwise collide with the scrape target's own). This is the standard OTel Collector → Prometheus pattern, and keeps per-process attributes (like `service.instance.id`) off the app metrics themselves rather than exploding their cardinality.

## Notes

- Data is only as durable as the named Docker volumes (`prometheus-data`, `loki-data`, `tempo-data`, `grafana-data`) — `docker compose -f observability/docker-compose.yml down -v` wipes it.
