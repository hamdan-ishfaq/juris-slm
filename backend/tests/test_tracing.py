"""One trace per question, with a span per stage, and never the question's text."""
import asyncio

from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from services import rag, tracing

_EXPORTER = InMemorySpanExporter()
_PROVIDER = TracerProvider()
_PROVIDER.add_span_processor(SimpleSpanProcessor(_EXPORTER))


def _answer(monkeypatch, question):
    async def fake_answer(*_args, **_kwargs):
        with tracing.trace_rag_step("retrieve"):
            with tracing.trace_rag_step("embed"):
                pass
        with tracing.trace_rag_step("generate"):
            pass
        return {"answer": "secret answer text", "sources": [], "answer_mode": "llm", "model": "m"}

    _EXPORTER.clear()
    monkeypatch.setattr(tracing, "_tracer", _PROVIDER.get_tracer("test"))
    monkeypatch.setattr(rag, "_answer_question", fake_answer)
    asyncio.run(rag.answer_question(None, question))
    return _EXPORTER.get_finished_spans()


def test_one_question_makes_one_trace_with_nested_stages(monkeypatch):
    spans = _answer(monkeypatch, "What does Article 6 say?")
    assert {span.context.trace_id for span in spans} == {spans[0].context.trace_id}
    by_name = {span.name: span for span in spans}
    assert {"total", "retrieve", "embed", "generate"} <= set(by_name)
    assert by_name["embed"].parent.span_id == by_name["retrieve"].context.span_id
    assert by_name["retrieve"].parent.span_id == by_name["total"].context.span_id


def test_spans_carry_no_question_or_answer_text(monkeypatch):
    spans = _answer(monkeypatch, "My client Jane Doe was dismissed on Monday")
    for span in spans:
        values = " ".join(str(value) for value in span.attributes.values())
        assert "Jane Doe" not in values and "secret answer" not in values
    total = next(span for span in spans if span.name == "total")
    assert total.attributes["question.chars"] == len("My client Jane Doe was dismissed on Monday")
    assert total.attributes["answer.mode"] == "llm"


def test_without_a_collector_nothing_is_exported(monkeypatch):
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", raising=False)
    assert tracing._exporter_endpoint() is None
    assert not isinstance(tracing._make_tracer(), type(_PROVIDER.get_tracer("x")))


def test_a_configured_collector_is_used(monkeypatch):
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://jaeger:4318")
    assert tracing._exporter_endpoint() == "http://jaeger:4318"
