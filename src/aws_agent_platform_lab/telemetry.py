"""Safe OpenTelemetry spans exported as JSON logs for CloudWatch collection."""
from __future__ import annotations

import json
import logging
import threading

_lock = threading.Lock()
_configured = False


def configure_telemetry():
    """Install one safe JSON span exporter per process for log collection."""
    global _configured
    with _lock:
        if _configured:
            return
        from opentelemetry import trace
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import SimpleSpanProcessor, SpanExporter, SpanExportResult

        class SafeJsonExporter(SpanExporter):
            """Export only timing and correlation fields, excluding arbitrary span attributes."""
            def export(self, spans):
                """Write bounded metadata for completed spans to the application logger."""
                logger = logging.getLogger("aws_agent_platform_lab.spans")
                for span in spans:
                    logger.info(json.dumps({"event": "otel_span", "name": span.name,
                        "trace_id": format(span.context.trace_id, "032x"),
                        "span_id": format(span.context.span_id, "016x"),
                        "parent_span_id": format(span.parent.span_id, "016x") if span.parent else None,
                        "duration_ms": (span.end_time - span.start_time) / 1_000_000,
                        "run_id": span.attributes.get("lab.run_id")}))
                return SpanExportResult.SUCCESS

            def shutdown(self):
                """No external exporter connection needs closing for synchronous log output."""
                pass

        provider = TracerProvider(resource=Resource.create({"service.name": "aws-agent-platform-lab"}))
        provider.add_span_processor(SimpleSpanProcessor(SafeJsonExporter()))
        trace.set_tracer_provider(provider)
        _configured = True
