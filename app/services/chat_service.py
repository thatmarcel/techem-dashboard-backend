from datetime import date
from pathlib import Path
import re

import pandas as pd

from app.config import BASE_DIR
from app.services import ai_analysis_service
from app.services.aggregation_service import _read_frame, broad_context, chart_context_base
from app.services.weather_service import weather_context
from app.utils.date_utils import period_buckets, resolve_period


MAX_CONTEXT_FILE_CHARS = 3000
MAX_CONTEXT_FILES = 4
MAX_CITY_WEATHER_CONTEXTS = 6


def _safe_context_file_paths(paths: list[str]) -> list[Path]:
    safe_paths: list[Path] = []
    for raw_path in paths[:MAX_CONTEXT_FILES]:
        candidate = Path(raw_path).expanduser()
        if not candidate.is_absolute():
            candidate = BASE_DIR / candidate
        resolved = candidate.resolve()
        try:
            resolved.relative_to(BASE_DIR)
        except ValueError:
            continue
        if resolved.is_file():
            safe_paths.append(resolved)
    return safe_paths


def _context_file_payload(paths: list[str]) -> list[dict]:
    payload: list[dict] = []
    for path in _safe_context_file_paths(paths):
        text = path.read_text(encoding="utf-8", errors="replace")
        excerpt = text[:MAX_CONTEXT_FILE_CHARS]
        payload.append(
            {
                "path": path.relative_to(BASE_DIR).as_posix(),
                "size_chars": len(text),
                "excerpt": excerpt,
                "truncated": len(text) > len(excerpt),
            }
        )
    return payload


def _scope_frame(connection, request) -> pd.DataFrame:
    return _read_frame(connection, request.scope_type, request.scope_id)


def _current_weather_context(frame: pd.DataFrame) -> dict:
    today_label = date.today().isoformat()
    bundle = weather_context(frame, [today_label], "day", True)
    series = bundle.get("series", [])
    return {
        "date": today_label,
        "weather": series[0] if series else None,
        "weather_location": bundle.get("location"),
        "weather_status": bundle.get("status", {}),
        "warnings": bundle.get("warnings", []),
    }


def _chat_scope_context(request, connection) -> dict:
    context = chart_context_base(
        connection,
        request.scope_type,
        request.scope_id,
        request.period,
        request.offset,
        False,
    )
    warnings = list(context.get("warnings", []))

    # This mirrors the fast backup version: Gemini receives the deterministic
    # chart scope first. Weather is merged once later from _message_weather_context.
    return {
        "mode": "current_scope",
        "scope": context["scope"],
        "period": context["period"],
        "summary": context["summary"],
        "series": context["series"],
        "baseline_energy": context["baseline_energy"],
        "weather": context["weather"],
        "weather_location": context.get("weather_location"),
        "warnings": warnings,
        "calendar": context["calendar"],
        "data_source_info": context["data_source_info"],
    }


def _message_location_frame(connection, message: str) -> tuple[pd.DataFrame, bool]:
    frame = _read_frame(connection)
    if frame.empty:
        return frame, False

    query = message.casefold()
    matched = pd.Series(False, index=frame.index)

    for zipcode in re.findall(r"\b\d{4,5}\b", message):
        zipcode_mask = frame["zipcode"].astype(str).str.strip().str.lstrip("0") == zipcode.lstrip("0")
        matched = matched | zipcode_mask

    for column in ["city", "street"]:
        if column not in frame:
            continue
        values = sorted(
            {str(value).strip() for value in frame[column].dropna().tolist() if str(value).strip()},
            key=len,
            reverse=True,
        )
        for value in values:
            if value.casefold() in query:
                matched = matched | (frame[column].astype(str).str.casefold() == value.casefold())

    if matched.any():
        return frame[matched].copy(), True
    return frame, False


def _city_ids_from_message(frame: pd.DataFrame, message: str) -> list[str]:
    if frame.empty or "city" not in frame:
        return []

    query = message.casefold()
    candidates = (
        frame[["city_id", "city"]]
        .drop_duplicates()
        .sort_values("city")
        .to_dict(orient="records")
    )
    result = []
    for row in candidates:
        city = str(row["city"]).strip()
        if city and city.casefold() in query:
            result.append(str(row["city_id"]))
    return result[:MAX_CITY_WEATHER_CONTEXTS]


def _selected_scope_city_id(connection, request) -> str | None:
    if request.scope_type == "total" or not request.scope_id:
        return None
    frame = _scope_frame(connection, request)
    if frame.empty or "city_id" not in frame:
        return None
    return str(frame.iloc[0]["city_id"])


def _portfolio_city_ids(frame: pd.DataFrame) -> list[str]:
    if frame.empty or "city_id" not in frame:
        return []
    grouped = (
        frame.groupby(["city_id", "city"], as_index=False)
        .agg(co2_g=("co2_g", "sum"))
        .sort_values("co2_g", ascending=False)
    )
    return [str(row["city_id"]) for row in grouped.head(MAX_CITY_WEATHER_CONTEXTS).to_dict(orient="records")]


def _city_weather_contexts(connection, request) -> list[dict]:
    # Gemini receives compact city-level weather snapshots. This helps broad
    # questions like "Vergleiche die Immobilien in Frankfurt und Hamburg" while
    # avoiding a raw-data upload or a large weather time series per city.
    frame = _read_frame(connection)
    if frame.empty:
        return []

    city_ids = _city_ids_from_message(frame, request.message)
    selected_city_id = _selected_scope_city_id(connection, request)
    if selected_city_id and selected_city_id not in city_ids:
        city_ids.insert(0, selected_city_id)
    if not city_ids and not request.use_current_scope:
        city_ids = _portfolio_city_ids(frame)

    today_label = date.today().isoformat()
    contexts = []
    for city_id in city_ids[:MAX_CITY_WEATHER_CONTEXTS]:
        city_frame = frame[frame["city_id"].astype(str) == city_id].copy()
        if city_frame.empty:
            continue
        bundle = weather_context(city_frame, [today_label], "day", True)
        series = bundle.get("series", [])
        weather = series[0] if series else None
        row = city_frame.iloc[0]
        contexts.append(
            {
                "city_id": city_id,
                "city": row["city"],
                "zipcode_sample": row["zipcode"],
                "weather": weather,
                "weather_location": bundle.get("location"),
                "weather_status": bundle.get("status", {}),
                "warnings": bundle.get("warnings", []),
            }
        )
    return contexts


def _weather_frame_for_request(connection, request) -> tuple[pd.DataFrame, bool, str]:
    frame, matched_from_message = _message_location_frame(connection, request.message)
    if matched_from_message:
        return frame, True, "message_location"

    # Even when broad portfolio context is enabled, the currently open scope is
    # the best location hint for weather.
    if request.scope_type != "total" and request.scope_id:
        return _scope_frame(connection, request), False, "selected_scope"

    return frame, False, "country_fallback"


def _message_weather_context(connection, request) -> dict:
    period_info = resolve_period(request.period, request.offset)
    labels = period_buckets(period_info["start"], period_info["end"], period_info["granularity"])
    frame, matched_from_message, location_source = _weather_frame_for_request(connection, request)
    # Keep chat fast: the period weather series uses imported CSV temperatures
    # and local fallback only. The external weather API is used once below for
    # today's local weather at the relevant scope/location.
    bundle = weather_context(frame, labels, period_info["granularity"], False)
    current_weather = _current_weather_context(frame)
    warnings = list(bundle.get("warnings", []))
    for warning in current_weather.get("warnings", []):
        if warning not in warnings:
            warnings.append(warning)

    return {
        "period": {
            "name": request.period,
            "offset": request.offset,
            "start": period_info["start"].isoformat(),
            "end": period_info["end"].isoformat(),
            "granularity": period_info["granularity"],
        },
        "weather": bundle["series"],
        "weather_location": bundle.get("location"),
        "weather_status": bundle.get("status", {}),
        "current_weather": current_weather["weather"],
        "current_weather_location": current_weather["weather_location"],
        "current_weather_status": current_weather["weather_status"],
        "matched_from_message": matched_from_message,
        "weather_location_source": location_source,
        "warnings": warnings,
    }


def _merge_weather_context(used_context: dict, message_weather: dict, request) -> None:
    should_override = (
        message_weather["matched_from_message"]
        or not request.use_current_scope
        or message_weather["weather_location_source"] == "selected_scope"
    )
    if should_override:
        used_context["weather"] = message_weather["weather"]
        used_context["weather_location"] = message_weather["weather_location"]
        used_context["weather_status"] = message_weather["weather_status"]
        used_context["current_weather"] = message_weather["current_weather"]
        used_context["current_weather_location"] = message_weather["current_weather_location"]
        used_context["current_weather_status"] = message_weather["current_weather_status"]
        used_context["weather_match_from_message"] = message_weather["matched_from_message"]
        used_context["weather_location_source"] = message_weather["weather_location_source"]
    else:
        used_context["question_weather_context"] = message_weather

    warnings = used_context.setdefault("warnings", [])
    for warning in message_weather.get("warnings", []):
        if warning not in warnings:
            warnings.append(warning)


def answer_chat(connection, request) -> dict:
    if request.use_current_scope:
        used_context = _chat_scope_context(request, connection)
    else:
        used_context = {"mode": "all_data", **broad_context(connection)}

    message_weather = _message_weather_context(connection, request)
    _merge_weather_context(used_context, message_weather, request)
    used_context["city_weather_contexts"] = _city_weather_contexts(connection, request)

    file_context = _context_file_payload(request.context_file_paths)
    used_context["context_files"] = file_context
    used_context["additional_instructions"] = request.additional_instructions

    response = ai_analysis_service.answer_chat(used_context, request.message, request.analysis_provider)
    result = ai_analysis_service.dump_model(response)
    for warning in used_context.get("warnings", []):
        if warning not in result["caveats"]:
            result["caveats"].append(warning)
    result["used_context"] = used_context
    return result
