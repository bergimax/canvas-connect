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

That overlay attaches the `app` service to this stack's network and sets `OTEL_EXPORTER_OTLP_ENDPOINT` — see `../backend/app/telemetry.py` for what the backend exports today (HTTP request and SQL query traces, four application metrics, and application logs). It's opt-in and touches nothing else: plain `docker compose up` (CI, `make test-integration`, deploy) is unaffected.

## Currently wired vs. not

- **Traces**: flowing once the app is connected — see above.
- **Metrics**: flowing once the app is connected. The collector's own internal metrics are always scraped; the app additionally exports four counters (see `backend/app/telemetry.py`) — `canvas_connect.interview_rooms.created`, `canvas_connect.interview_participants.active`, `canvas_connect.canvas_elements.created`, `canvas_connect.component_creation.failures` — each joinable in PromQL against `target_info{exported_job="canvas-connect-backend"}` for `deployment_environment_name`/`service_version`. The provisioned dashboard already does this join — see below.
- **Logs**: flowing once the app is connected. The `canvas_connect` logger (`backend/app/telemetry.py`) ships every record via OTLP in addition to stdout, trace-correlated automatically (`trace_id`/`span_id` on any record emitted inside a request span). See `app/store.py`/`app/routers/canvas.py` for what's logged today — room/participant/canvas-element lifecycle events and the same failures the metrics above count.

## Dashboard

`grafana/provisioning/dashboards/json/canvas-connect-app-metrics.json` — one panel per application metric, a breakdown of failures by `reason`, and a live log panel. Two dashboard variables at the top, **environment** and **version**, filter every panel; `version`'s options narrow to whatever's actually running in the selected `environment`.

Why the queries look the way they do: none of the four app metrics carry `deployment_environment_name`/`service_version` as labels directly — those live only on the synthetic `target_info` series each OTel resource produces. Every metric panel query is a `metric * on(exported_job, exported_instance) group_left(deployment_environment_name, service_version) target_info{...}` join to pull them in and filter by the variables (the `exported_` prefix is Prometheus's own doing: it renames the collector's `job`/`instance` labels on scrape since they'd otherwise collide with the scrape target's own). This is the standard OTel Collector → Prometheus pattern, and keeps per-process attributes (like `service.instance.id`) off the app metrics themselves rather than exploding their cardinality.

The logs panel's query looks different — `{service_name="canvas-connect-backend"} | deployment_environment_name=~"$environment" | service_version=~"$version"` — because Loki's OTLP ingestion only promotes a small hint set (like `service_name`) to real indexed stream labels; everything else (`deployment_environment_name`, `service_version`, `trace_id`, `session_id`, ...) arrives as structured metadata, which can only be filtered with a label-filter pipeline stage (`| label=~"value"`) after the stream selector, not inside `{...}`.

## Alerting

`grafana/provisioning/alerting/component-creation-failures.yml` — one alert, "Repeated canvas component-creation failures", firing per `(environment, version)` combination independently (so a broken dev deploy never masks, or gets masked by, prod).

**Scope**: only `reason="error"` — the query filters `canvas_connect_component_creation_failures_total{reason="error"}`, deliberately excluding `observer_forbidden` and `editing_disabled`. Those two are the server correctly enforcing permissions (expected, by-design rejections), not incidents; alerting on them would be UX-friction noise, not something actionable for whoever's on call. `error` is the one reason that means a save actually broke.

**Threshold and duration**: more than 2 failures (`> 2`, i.e. 3+) within a trailing 5-minute window (`increase(...[5m])`), sustained for 2 minutes (`for: 2m`) before firing. The reasoning:
- This is a real-time collaborative tool for an **interview in progress** — a handful of failures in 5 minutes, given how low the overall traffic is, is already a strong signal, and someone is stuck *right now*. That argues for a sensitive, fast-firing alert, not a lax one.
- "Repeated" (the ask) rules out firing on a single isolated blip — one failure could be a transient fluke; three within 5 minutes is a pattern.
- The 2-minute `for` isn't about waiting out a long confirmation period — it's cheap insurance against a single borderline evaluation tick flapping the alert, while still detecting a real pattern within a few minutes total, appropriate for a product where slow detection has a real cost too.

**What's in the alert**: labels `service` (`canvas-connect-backend`), `owner` (contact for this alert), `severity`; the query result contributes `deployment_environment_name` and `service_version` per firing instance. The `summary`/`description` annotations spell out service, environment, version, and owner in prose (Grafana's annotation templates only have `$labels` from the *query result*, not the rule's own static labels — that's why `service`/`owner` are written literally there rather than templated, even though they're still real labels on the alert). `dashboard_url` links to the app-metrics dashboard's failures-by-reason panel, deep-linked with `var-environment`/`var-version` set to the firing instance's own values; `__dashboardUid__`/`__panelId__` also wire up Grafana's native "View in Dashboard" button.

No contact point/notification policy is provisioned (Grafana's default email contact point needs SMTP configured, which isn't set up here) — the rule fires and is visible in Grafana's Alerting UI with everything above attached; routing it to Slack/PagerDuty/email is a separate step once you have a real target.

## Production deployment

Deployed as its own EC2 instance/CloudFormation stack — separate from the dev and prod app instances, not one-per-environment — via [`deploy/observability-cloudformation.yml`](../deploy/observability-cloudformation.yml) and [`deploy/deploy-observability.sh`](../deploy/deploy-observability.sh). `docker-compose.prod.yml` here adds Caddy in front of Grafana (same automatic-HTTPS pattern as the app's) and a real Grafana admin password instead of the `docker-compose.yml` dev default. See the [main README's Deployment section](../README.md#observability-stack) for the full picture, including how the dev/prod app stacks get pointed at this one and how its security group is scoped to their specific IPs rather than the open internet.

## Notes

- Data is only as durable as the named Docker volumes (`prometheus-data`, `loki-data`, `tempo-data`, `grafana-data`) — `docker compose -f observability/docker-compose.yml down -v` wipes it.
