import logging

from app.config import settings
from app.schemas.ai import ChartAIResult, ChatAIResult, ReportAIResult
from app.services.gemini_provider import GeminiProvider
from app.services.local_algorithm_provider import LocalAlgorithmProvider
from app.services.vertex_provider import VertexProvider


logger = logging.getLogger(__name__)


def dump_model(model):
    # Pydantic v2 uses model_dump; this fallback keeps the code usable with v1.
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


def _chart_provider(provider_name: str | None):
    # Chart/report AI is separate from chat:
    # local = deterministic standard algorithm
    # vertex = custom trained Google/Vertex endpoint
    selected = (provider_name or settings.chart_ai_provider or "local").lower()
    try:
        if selected == "vertex":
            return VertexProvider()
    except Exception as exc:
        logger.warning("Chart provider '%s' could not be initialized. Falling back to local. Error: %s", selected, exc)
        return LocalAlgorithmProvider()
    if selected not in {"local", "mock"}:
        logger.info("Unknown chart provider '%s'. Falling back to local.", selected)
    return LocalAlgorithmProvider()


def _chat_provider(provider_name: str | None):
    # Chat remains Gemini. Local is only a safety fallback when Gemini is not
    # configured or fails.
    selected = (provider_name or settings.google_ai_provider or "gemini").lower()
    if selected in {"local", "mock"}:
        return LocalAlgorithmProvider()
    try:
        if selected == "gemini":
            return GeminiProvider()
    except Exception as exc:
        logger.warning("Chat provider '%s' could not be initialized. Falling back to local. Error: %s", selected, exc)
        return LocalAlgorithmProvider()
    if selected != "gemini":
        logger.info("Chat provider '%s' is not supported for chat. Using Gemini/local fallback.", selected)
    try:
        return GeminiProvider()
    except Exception:
        return LocalAlgorithmProvider()


def _safe_chart_result(raw: dict, context: dict) -> ChartAIResult:
    try:
        result = ChartAIResult(**raw)
        # Forecast arrays must stay aligned with the backend-generated x_axis.
        # If an AI provider returns missing or reordered points, we discard it.
        if len(result.points) != len(context["x_axis"]):
            raise ValueError("AI returned wrong number of forecast points.")
        input_labels = list(context["x_axis"])
        output_labels = [point.x for point in result.points]
        if output_labels != input_labels:
            raise ValueError("AI returned labels that do not match x_axis.")
        return result
    except Exception as exc:
        logger.warning("Chart AI response was invalid. Falling back to local. Error: %s", exc)
        return ChartAIResult(**LocalAlgorithmProvider().analyze_chart(context))


def analyze_chart(context: dict, provider_name: str | None = None) -> ChartAIResult:
    # Hard numbers are already prepared in context. The provider only adds
    # forecast/optimization estimates and explanations.
    provider = _chart_provider(provider_name)
    try:
        raw = provider.analyze_chart(context)
    except Exception as exc:
        logger.warning(
            "Chart AI call via provider '%s' failed. Falling back to local. Error: %s",
            getattr(provider, "name", provider.__class__.__name__),
            exc,
        )
        raw = LocalAlgorithmProvider().analyze_chart(context)
    return _safe_chart_result(raw, context)


def generate_report(context: dict, provider_name: str | None = None) -> ReportAIResult:
    provider = _chart_provider(provider_name)
    try:
        return ReportAIResult(**provider.generate_report(context))
    except Exception as exc:
        logger.warning(
            "Report AI call via provider '%s' failed. Falling back to local. Error: %s",
            getattr(provider, "name", provider.__class__.__name__),
            exc,
        )
        return ReportAIResult(**LocalAlgorithmProvider().generate_report(context))


def answer_chat(context: dict, message: str, provider_name: str | None = None) -> ChatAIResult:
    provider = _chat_provider(provider_name)
    try:
        return ChatAIResult(**provider.chat(context, message))
    except Exception as exc:
        logger.warning(
            "Chat AI call via provider '%s' failed. Falling back to local. Error: %s",
            getattr(provider, "name", provider.__class__.__name__),
            exc,
        )
        return ChatAIResult(**LocalAlgorithmProvider().chat(context, message))
