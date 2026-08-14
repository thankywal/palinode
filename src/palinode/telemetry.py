"""OpenTelemetry spans for the decisions this system makes.

ADK already emits traces for agent runs and tool calls following the OTel GenAI
semantic conventions, so the reasoning chain is covered without us doing
anything. What is missing from those traces is the part that is ours: why an
action was given a tier, whether it carried a way back, what Model Armor made
of the input, and what happened when the reversal ran.

Those are the spans an auditor asks about six weeks later, so they are the ones
worth emitting. Attribute names are namespaced under palinode.* rather than
squatting on the GenAI namespace, which is not ours to extend.

Degrades to nothing if the SDK is absent. Telemetry that can break the thing it
observes is not telemetry.
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Any, Iterator, Optional

log = logging.getLogger("palinode.telemetry")

_tracer = None
_enabled: Optional[bool] = None


def _tracer_or_none():
    global _tracer, _enabled
    if _enabled is False:
        return None
    if _tracer is not None:
        return _tracer

    try:
        from opentelemetry import trace

        _tracer = trace.get_tracer("palinode", "0.1.0")
        _enabled = True
        return _tracer
    except Exception as exc:  # noqa: BLE001
        log.info("opentelemetry not available, spans disabled: %s", exc)
        _enabled = False
        return None


@contextmanager
def span(name: str, **attributes: Any) -> Iterator[Any]:
    """Emit a span, or do nothing at all if OTel is not installed."""
    tracer = _tracer_or_none()
    if tracer is None:
        yield None
        return

    with tracer.start_as_current_span(name) as current:
        for key, value in attributes.items():
            if value is not None:
                current.set_attribute(f"palinode.{key}", value)
        try:
            yield current
        except Exception as exc:  # noqa: BLE001
            try:
                current.record_exception(exc)
            except Exception:  # noqa: BLE001, S110
                pass
            raise


def annotate(current, **attributes: Any) -> None:
    """Add attributes to a span that is already open."""
    if current is None:
        return
    for key, value in attributes.items():
        if value is not None:
            try:
                current.set_attribute(f"palinode.{key}", value)
            except Exception:  # noqa: BLE001, S110
                pass


def configure(project: str = "") -> bool:
    """Wire spans to Cloud Trace. Called once at startup, safe to skip."""
    tracer = _tracer_or_none()
    if tracer is None:
        return False

    try:
        from opentelemetry import trace
        from opentelemetry.exporter.cloud_trace import CloudTraceSpanExporter
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        if not project:
            return False

        provider = TracerProvider()
        provider.add_span_processor(
            BatchSpanProcessor(CloudTraceSpanExporter(project_id=project))
        )
        trace.set_tracer_provider(provider)
        log.info("exporting spans to cloud trace for %s", project)
        return True
    except Exception as exc:  # noqa: BLE001
        log.info("cloud trace exporter unavailable, spans stay local: %s", exc)
        return False
