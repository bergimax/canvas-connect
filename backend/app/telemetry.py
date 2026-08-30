"""OpenTelemetry setup: tracing, application metrics, and application logs.

Every span, metric data point, and log record is tagged with the same
three resource attributes, so any of them can be filtered/grouped by
exactly what's running: which service produced it (service.name), which
stack it's running in (deployment.environment.name — "dev"/"prod",
matching deploy/cloudformation.yml's Environment parameter), and which
build (service.version — the CI image tag from
.github/workflows/ci-cd.yml, threaded through as APP_VERSION; see
docker-compose.yml).

Built once at import time (not lazily per create_app() call) so the
providers below are safe to hand straight to instrument() and to the
`add()`/`logger.info()` calls in store.py/routers without any
get-meter/get-tracer/get-logger ordering concerns.
"""

from __future__ import annotations

import logging
import os

from fastapi import FastAPI
from opentelemetry import metrics, trace
from opentelemetry._logs import set_logger_provider
from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.logging.handler import LoggingHandler
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.sdk._logs import LoggerProvider
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
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

# ------------------------------- application logs -------------------------------

_logger_provider = LoggerProvider(resource=_resource)
if _exporting:
    _logger_provider.add_log_record_processor(BatchLogRecordProcessor(OTLPLogExporter()))
set_logger_provider(_logger_provider)

_otlp_log_handler = LoggingHandler(level=logging.NOTSET, logger_provider=_logger_provider)

# All app logging goes through this one logger (children below propagate up
# to it) rather than the root logger — root is left alone so we don't
# collide with uvicorn's own logging config (its "uvicorn"/"uvicorn.access"
# loggers already write formatted request logs to stdout independently).
_app_logger = logging.getLogger("canvas_connect")
_app_logger.setLevel(logging.INFO)
_app_logger.propagate = False
_app_logger.addHandler(logging.StreamHandler())  # always visible via `docker logs`
_app_logger.addHandler(_otlp_log_handler)  # additionally shipped via OTLP when configured


def get_logger(name: str) -> logging.Logger:
    """A child of the "canvas_connect" logger — see above. LoggingHandler
    automatically attaches the current span's trace_id/span_id to every
    record, so a log line here is already correlated with the trace for
    the same request without any extra wiring.
    """
    return logging.getLogger(f"canvas_connect.{name}")


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
