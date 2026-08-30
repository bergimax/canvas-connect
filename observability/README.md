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

Grafana: http://localhost:3001 (`admin`/`admin`, you'll be asked to change it on first login).

## Feeding it from the app stack

On its own this stack has nothing sending it data. To point the app at the collector, bring the app stack up with the optional overlay at the repo root:

```
docker compose -f observability/docker-compose.yml up -d
docker compose -f docker-compose.yml -f docker-compose.observability.yml up -d
```

That overlay attaches the `app` service to this stack's network and sets `OTEL_EXPORTER_OTLP_ENDPOINT` — see `../backend/app/telemetry.py` for what the backend exports today (HTTP request and SQL query traces). It's opt-in and touches nothing else: plain `docker compose up` (CI, `make test-integration`, deploy) is unaffected.

## Currently wired vs. not

- **Traces**: flowing once the app is connected — see above.
- **Metrics**: flowing once the app is connected. The collector's own internal metrics are always scraped; the app additionally exports four counters (see `backend/app/telemetry.py`) — `canvas_connect.interview_rooms.created`, `canvas_connect.interview_participants.active`, `canvas_connect.canvas_elements.created`, `canvas_connect.component_creation.failures` — each joinable in PromQL against `target_info{service_name="canvas-connect-backend"}` for `deployment_environment_name`/`service_version`.
- **Logs**: the pipeline (collector → Loki) is ready, but the app doesn't ship logs via OTLP yet — nothing will show up in Loki until that's added.

## Notes

- Data is only as durable as the named Docker volumes (`prometheus-data`, `loki-data`, `tempo-data`, `grafana-data`) — `docker compose -f observability/docker-compose.yml down -v` wipes it.
- No dashboards are provisioned; use Grafana's Explore view against each datasource.
