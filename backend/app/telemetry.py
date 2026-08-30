"""OpenTelemetry setup: tracing, plus a handful of application metrics.

Every span and metric data point is tagged with the same three resource
attributes, so either can be filtered/grouped by exactly what's running:
which service produced it (service.name), which stack it's running in
(deployment.environment.name — "dev"/"prod", matching
deploy/cloudformation.yml's Environment parameter), and which build
(service.version — the CI image tag from .github/workflows/ci-cd.yml,
threaded through as APP_VERSION; see docker-compose.yml).

Built once at import time (not lazily per create_app() call) so the
providers below are safe to hand straight to instrument() and to the
`add()` calls in store.py/routers without any get-meter/get-tracer
ordering concerns.
"""

from __future__ import annotations

import os

from fastapi import FastAPI
from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from sqlalchemy.engine import Engine

_resource = Resource.create(
    {
        "service.name": os.environ.get("OTEL_SERVICE_NAME", "canvas-connect-backend"),
        "deployment.environment.name": os.environ.get("ENVIRONMENT", "development"),
        "service.version": os.environ.get("APP_VERSION", "dev"),
    }
)

# Data is always recorded but only exported when a collector's configured,
# so local dev/tests aren't spending every span/metric retrying a
# connection nothing is listening on.
_exporting = bool(os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT"))

_tracer_provider = TracerProvider(resource=_resource)
if _exporting:
    _tracer_provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
trace.set_tracer_provider(_tracer_provider)

_meter_provider = MeterProvider(
    resource=_resource,
    metric_readers=[PeriodicExportingMetricReader(OTLPMetricExporter())] if _exporting else [],
)
metrics.set_meter_provider(_meter_provider)

_meter = _meter_provider.get_meter("canvas_connect.app")

# ---------------------------- application metrics ----------------------------
# Used directly by app/store.py (rooms, participants, canvas elements) and
# app/routers/canvas.py (component creation failures) — see call sites.

interview_rooms_created = _meter.create_counter(
    "canvas_connect.interview_rooms.created",
    unit="{room}",
    description="Interview rooms (sessions) created.",
)

active_interview_participants = _meter.create_up_down_counter(
    "canvas_connect.interview_participants.active",
    unit="{participant}",
    description="Participants currently part of an interview session.",
)

canvas_elements_created = _meter.create_counter(
    "canvas_connect.canvas_elements.created",
    unit="{element}",
    description="Canvas elements (components, connectors, strokes, ...) created.",
)

component_creation_failures = _meter.create_counter(
    "canvas_connect.component_creation.failures",
    unit="{failure}",
    description="Failed attempts to save/create canvas elements.",
)

_sqlalchemy_instrumented = False


def instrument(app: FastAPI, engine: Engine) -> None:
    global _sqlalchemy_instrumented

    # Instance-scoped, so safe to call on every create_app() (once per test
    # in the suite, once in production).
    FastAPIInstrumentor.instrument_app(app, tracer_provider=_tracer_provider, meter_provider=_meter_provider)

    # Unlike FastAPIInstrumentor, SQLAlchemyInstrumentor is a process-wide
    # singleton: past the first call, .instrument() is a no-op that just
    # logs "Attempting to instrument while already instrumented". Harmless
    # in production (create_app() runs exactly once there), but create_app()
    # runs once per test here, so guard it ourselves rather than let that
    # warning fire on every test after the first.
    if not _sqlalchemy_instrumented:
        SQLAlchemyInstrumentor().instrument(engine=engine, tracer_provider=_tracer_provider)
        _sqlalchemy_instrumented = True
