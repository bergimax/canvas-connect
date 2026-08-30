"""OpenTelemetry tracing setup.

Every span is tagged with three resource attributes so a trace backend can
be filtered/grouped by exactly what's running: which service produced it
(service.name), which stack it's running in (deployment.environment.name —
"dev"/"prod", matching deploy/cloudformation.yml's Environment parameter),
and which build (service.version — the CI image tag from
.github/workflows/ci-cd.yml, threaded through as APP_VERSION; see
docker-compose.yml).
"""

from __future__ import annotations

import os

from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from sqlalchemy.engine import Engine

_provider: TracerProvider | None = None
_sqlalchemy_instrumented = False


def _get_provider() -> TracerProvider:
    # create_app() runs once per test in the suite (a fresh app per test),
    # so this builds the process-wide TracerProvider on the first call and
    # reuses it afterwards — re-registering a global TracerProvider on every
    # call would just log a warning and be ignored past the first one.
    global _provider
    if _provider is not None:
        return _provider

    resource = Resource.create(
        {
            "service.name": os.environ.get("OTEL_SERVICE_NAME", "canvas-connect-backend"),
            "deployment.environment.name": os.environ.get("ENVIRONMENT", "development"),
            "service.version": os.environ.get("APP_VERSION", "dev"),
        }
    )
    provider = TracerProvider(resource=resource)

    # Only export if a collector's configured, so local dev/tests aren't
    # spending every span retrying a connection nothing is listening on.
    if os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT"):
        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))

    trace.set_tracer_provider(provider)
    _provider = provider
    return provider


def instrument(app: FastAPI, engine: Engine) -> None:
    global _sqlalchemy_instrumented

    provider = _get_provider()
    # Instance-scoped, so safe to call on every create_app() (once per test
    # in the suite, once in production).
    FastAPIInstrumentor.instrument_app(app, tracer_provider=provider)

    # Unlike FastAPIInstrumentor, SQLAlchemyInstrumentor is a process-wide
    # singleton: past the first call, .instrument() is a no-op that just
    # logs "Attempting to instrument while already instrumented". Harmless
    # in production (create_app() runs exactly once there), but create_app()
    # runs once per test here, so guard it ourselves rather than let that
    # warning fire on every test after the first.
    if not _sqlalchemy_instrumented:
        SQLAlchemyInstrumentor().instrument(engine=engine, tracer_provider=provider)
        _sqlalchemy_instrumented = True
