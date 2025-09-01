

from fastapi import FastAPI
from core.settings import settings
from opentelemetry import trace, metrics
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import (
    PeriodicExportingMetricReader,
)
import logging
from core.logging_config import setup_logging
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.propagate import set_global_textmap
from sentry_sdk.integrations.opentelemetry import SentrySpanProcessor, SentryPropagator

setup_logging(log_level="INFO")
logger = logging.getLogger(__name__)

def setup_fastapi_otel(app: FastAPI):
    """
    Setup OpenTelemetry integration, sent to coralogix.
    Coralogix docs: https://coralogix.com/docs/opentelemetry/instrumentation-options/python-opentelemetry-instrumentation/
    OTEL docs: https://opentelemetry-python-contrib.readthedocs.io/en/latest/instrumentation/fastapi/fastapi.html
    """
    if not settings.CORALOGIX_SEND_DATA_KEY:
        return
    logger.info("Setting up OpenTelemetry")
    resource = Resource(
        attributes={
            "service.name": f"{settings.OTEL_SERVICE_NAME}",
            "service.version": app.version,
            "telemetry.sdk.language": "python",
        }
    )  # set the service name to show in traces
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(SentrySpanProcessor())
    trace.set_tracer_provider(provider)
    set_global_textmap(SentryPropagator())
    headers = ", ".join(
        [
            f"Authorization=Bearer%20{settings.CORALOGIX_SEND_DATA_KEY}",
            f"CX-Application-Name={settings.OTEL_APPLICATION_NAME}",
            f"CX-Subsystem-Name={settings.OTEL_SERVICE_NAME}",
        ]
    )
    provider.add_span_processor(
        BatchSpanProcessor(OTLPSpanExporter(headers=headers, endpoint=settings.OTEL_EXPORTER_OTLP_ENDPOINT))
    )
    exporter = OTLPMetricExporter(
        endpoint=settings.OTEL_EXPORTER_OTLP_ENDPOINT,
        headers=headers,
    )
    metric_reader = PeriodicExportingMetricReader(exporter)
    meter_provider = MeterProvider(metric_readers=[metric_reader])

    # Sets the global default meter provider
    metrics.set_meter_provider(meter_provider)

    LoggingInstrumentor(tracer_provider=provider).instrument()
    FastAPIInstrumentor.instrument_app(
        app,
        tracer_provider=provider,
        meter_provider=meter_provider,
        excluded_urls="/health",  # Exclude health endpoint from tracing (k8s liveness probe)
    )X