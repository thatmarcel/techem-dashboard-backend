from copy import deepcopy
from threading import Lock

from app.services import ai_analysis_service
from app.services.aggregation_service import chart_payload


_REPORT_CACHE: dict[tuple, dict] = {}
_REPORT_CACHE_LOCK = Lock()


def invalidate_report_cache() -> None:
    with _REPORT_CACHE_LOCK:
        _REPORT_CACHE.clear()


def build_report(connection, scope_type: str, scope_id: str | None, period: str, offset: int, provider: str | None) -> dict:
    cache_key = (scope_type, scope_id or "", period, offset, (provider or "").lower())
    with _REPORT_CACHE_LOCK:
        cached = _REPORT_CACHE.get(cache_key)
    if cached is not None:
        return deepcopy(cached)

    chart = chart_payload(connection, scope_type, scope_id, period, offset, True, provider)
    context = {
        "scope": chart["scope"],
        "period": chart["period"],
        "summary": chart["summary"],
        "series": chart["series"],
        "anomalies": chart["anomalies"],
        "ai_explanations": chart["ai_explanations"],
        "mold_risk": chart.get("mold_risk"),
        "warnings": chart.get("warnings", []),
    }
    report = ai_analysis_service.generate_report(context, provider)
    result = ai_analysis_service.dump_model(report)
    result["mold_risk"] = chart.get("mold_risk")
    result["used_context"] = {
        "scope": chart["scope"],
        "period": chart["period"],
        "warnings": chart.get("warnings", []),
        "mold_risk": chart.get("mold_risk"),
    }
    with _REPORT_CACHE_LOCK:
        _REPORT_CACHE[cache_key] = deepcopy(result)
    return result
