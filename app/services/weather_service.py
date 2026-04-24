from datetime import date, timedelta
from functools import lru_cache
import logging
import re
from threading import Lock
import time

import httpx
import pandas as pd

from app.config import settings


logger = logging.getLogger(__name__)

OPEN_METEO_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
OPEN_METEO_ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
OPEN_METEO_GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
OPEN_METEO_FORECAST_HORIZON_DAYS = 16
TOMORROW_STATUS_SUMMARY_URL = "https://status.tomorrow.io/api/v2/summary.json"
TOMORROW_STATUS_PAGE_URL = "https://status.tomorrow.io/"
TOMORROW_STATUS_CACHE_TTL_SECONDS = 300
DEMO_CITY_COORDINATES = {
    "berlin": {"latitude": 52.52, "longitude": 13.405, "timezone": "Europe/Berlin", "query_used": "Berlin, Deutschland", "source": "demo-city-coordinate"},
    "frankfurt": {"latitude": 50.1109, "longitude": 8.6821, "timezone": "Europe/Berlin", "query_used": "Frankfurt am Main, Deutschland", "source": "demo-city-coordinate"},
    "frankfurt am main": {"latitude": 50.1109, "longitude": 8.6821, "timezone": "Europe/Berlin", "query_used": "Frankfurt am Main, Deutschland", "source": "demo-city-coordinate"},
    "hamburg": {"latitude": 53.5511, "longitude": 9.9937, "timezone": "Europe/Berlin", "query_used": "Hamburg, Deutschland", "source": "demo-city-coordinate"},
    "halle": {"latitude": 51.4828, "longitude": 11.9697, "timezone": "Europe/Berlin", "query_used": "Halle (Saale), Deutschland", "source": "demo-city-coordinate"},
}

_TOMORROW_STATUS_CACHE: dict[str, object] = {"expires_at": 0.0, "value": None}
_TOMORROW_STATUS_LOCK = Lock()


def _seasonal_temperature(label: str) -> float:
    month = int(label[5:7]) if len(label) >= 7 else date.today().month
    return {
        1: 1.0,
        2: 3.0,
        3: 7.0,
        4: 11.0,
        5: 16.0,
        6: 19.0,
        7: 22.0,
        8: 21.0,
        9: 17.0,
        10: 11.0,
        11: 6.0,
        12: 2.0,
    }.get(month, 10.0)


def _mock_weather(label: str, temperature: float | None = None) -> dict:
    temp = float(temperature) if temperature is not None and not pd.isna(temperature) else _seasonal_temperature(label)
    return {
        "x": label,
        "temperature_c": round(temp, 1),
        "precipitation_mm": 2.0 if temp > 3 and label.endswith(("05", "12", "19", "26")) else 0.3,
        "snow_or_frost": temp <= 1.0,
        "wind_kmh": 12.0,
        "cloud_cover_percent": 55.0,
        "source": "csv_or_mock",
    }


def _tomorrow_status_warning(status: dict | None) -> str | None:
    if not status or status.get("ok", True):
        return None
    description = status.get("description") or "Service disruption"
    return f"Tomorrow.io status: {description}. Open-Meteo/CSV-Fallback wurde verwendet."


def _healthy_component(component: dict) -> bool:
    return component.get("status") == "operational"


def _tomorrow_status_from_summary(payload: dict) -> dict:
    status = payload.get("status", {})
    components = payload.get("components", [])
    relevant_components = [
        component
        for component in components
        if component.get("name") in {"API", "Timeline API", "Historical API"}
    ]
    unhealthy_components = [component.get("name") for component in relevant_components if not _healthy_component(component)]
    indicator = status.get("indicator") or "unknown"
    description = status.get("description") or "Unknown"
    ok = indicator == "none" and not unhealthy_components
    if unhealthy_components:
        description = f"{description}; betroffen: {', '.join(unhealthy_components)}"
    return {
        "ok": ok,
        "indicator": indicator,
        "description": description,
        "source": "statuspage-api",
    }


def _tomorrow_status_from_html(html: str) -> dict | None:
    patterns = [
        ("All Systems Operational", "none", True),
        ("Degraded Performance", "minor", False),
        ("Partial Outage", "major", False),
        ("Major Outage", "critical", False),
        ("Maintenance", "maintenance", False),
    ]
    for phrase, indicator, ok in patterns:
        if phrase in html:
            return {
                "ok": ok,
                "indicator": indicator,
                "description": phrase,
                "source": "statuspage-html",
            }

    match = re.search(
        r"(All Systems Operational|Degraded Performance|Partial Outage|Major Outage|Maintenance)",
        html,
    )
    if not match:
        return None
    phrase = match.group(1)
    return {
        "ok": phrase == "All Systems Operational",
        "indicator": phrase.lower().replace(" ", "_"),
        "description": phrase,
        "source": "statuspage-html",
    }


def tomorrow_status() -> dict:
    with _TOMORROW_STATUS_LOCK:
        cached_value = _TOMORROW_STATUS_CACHE.get("value")
        if cached_value and float(_TOMORROW_STATUS_CACHE.get("expires_at", 0.0)) > time.time():
            return cached_value

    status = {
        "ok": True,
        "indicator": "unknown",
        "description": "Tomorrow.io status konnte nicht geprueft werden.",
        "source": "unavailable",
    }

    try:
        response = httpx.get(TOMORROW_STATUS_SUMMARY_URL, timeout=6)
        response.raise_for_status()
        status = _tomorrow_status_from_summary(response.json())
    except Exception as exc:
        logger.info("Tomorrow.io status summary request failed: %s", exc)
        try:
            response = httpx.get(TOMORROW_STATUS_PAGE_URL, timeout=6)
            response.raise_for_status()
            parsed = _tomorrow_status_from_html(response.text)
            if parsed:
                status = parsed
        except Exception as html_exc:
            logger.info("Tomorrow.io status page request failed: %s", html_exc)

    with _TOMORROW_STATUS_LOCK:
        _TOMORROW_STATUS_CACHE["value"] = status
        _TOMORROW_STATUS_CACHE["expires_at"] = time.time() + TOMORROW_STATUS_CACHE_TTL_SECONDS
    return status


def _bucket_temperatures(frame: pd.DataFrame, granularity: str) -> dict:
    if frame.empty:
        return {}
    data = frame.copy()
    data["date"] = pd.to_datetime(data["date"])
    data["mean_outside_temperature_c"] = pd.to_numeric(data["mean_outside_temperature_c"], errors="coerce")
    data["bucket"] = data["date"].dt.strftime("%Y-%m" if granularity == "month" else "%Y-%m-%d")
    return data.groupby("bucket")["mean_outside_temperature_c"].mean().to_dict()


def _label_bounds(label: str, granularity: str) -> tuple[date, date]:
    if granularity == "month":
        start = date.fromisoformat(f"{label}-01")
        if start.month == 12:
            end = date(start.year + 1, 1, 1) - timedelta(days=1)
        else:
            end = date(start.year, start.month + 1, 1) - timedelta(days=1)
        return start, end
    day = date.fromisoformat(label)
    return day, day


def _date_span(start: date, end: date) -> list[date]:
    cursor = start
    days: list[date] = []
    while cursor <= end:
        days.append(cursor)
        cursor += timedelta(days=1)
    return days


def _clean_text(value) -> str:
    if value is None or pd.isna(value):
        return ""
    return str(value).strip()


def _unique_text_values(frame: pd.DataFrame, column: str) -> list[str]:
    if column not in frame:
        return []
    values = [_clean_text(value) for value in frame[column].dropna().tolist()]
    return sorted({value for value in values if value})


def _location_context(frame: pd.DataFrame) -> dict | None:
    if frame.empty:
        return None

    cities = _unique_text_values(frame, "city")
    zipcodes = _unique_text_values(frame, "zipcode")
    streets = _unique_text_values(frame, "street")
    housenumbers = _unique_text_values(frame, "housenumber")

    # A total portfolio or mixed-city context must not accidentally use the
    # first row's city. For broad questions we use a neutral Germany location.
    if len(cities) != 1:
        return {
            "scope_level": "country",
            "city": "Deutschland",
            "zipcode": "",
            "street": "",
            "housenumber": "",
            "address_line": "Deutschland",
            "query": "Deutschland",
            "query_candidates": ["Deutschland"],
            "timezone": "Europe/Berlin",
        }

    city = cities[0]
    zipcode = zipcodes[0] if len(zipcodes) == 1 else ""
    street = streets[0] if len(streets) == 1 else ""
    housenumber = housenumbers[0] if len(housenumbers) == 1 else ""
    address_line = " ".join(part for part in [street, housenumber] if part).strip()
    city_line = " ".join(part for part in [zipcode, city] if part).strip()

    query_candidates = [
        ", ".join(part for part in [address_line, city_line, "Deutschland"] if part),
        ", ".join(part for part in [city_line, "Deutschland"] if part),
        ", ".join(part for part in [city, "Deutschland"] if part),
        zipcode,
        "Deutschland",
    ]
    query_candidates = [query for query in dict.fromkeys(query_candidates) if query]
    return {
        "scope_level": "address" if address_line else "city",
        "city": city,
        "zipcode": zipcode,
        "street": street,
        "housenumber": housenumber,
        "address_line": address_line,
        "query": query_candidates[0] if query_candidates else "Deutschland",
        "query_candidates": query_candidates,
        "timezone": "Europe/Berlin",
    }
@lru_cache(maxsize=128)
def _open_meteo_geocode(query: str) -> dict | None:
    if not query:
        return None
    try:
        response = httpx.get(
            OPEN_METEO_GEOCODING_URL,
            params={
                "name": query,
                "count": 1,
                "format": "json",
                "language": "de",
                "countryCode": "DE",
            },
            timeout=8,
        )
        response.raise_for_status()
        results = response.json().get("results", [])
        if not results:
            return None
        best = results[0]
        return {
            "latitude": float(best["latitude"]),
            "longitude": float(best["longitude"]),
            "timezone": best.get("timezone") or "Europe/Berlin",
            "source": "open-meteo-geocoding",
        }
    except Exception as exc:
        logger.info("Open-Meteo geocoding failed for '%s': %s", query, exc)
        return None


def _resolve_coordinates(location: dict | None) -> dict | None:
    if not location:
        return None
    city_key = str(location.get("city") or "").strip().casefold()
    if city_key in DEMO_CITY_COORDINATES:
        return DEMO_CITY_COORDINATES[city_key]
    if location.get("scope_level") == "country" or location.get("query") == "Deutschland":
        return {
            "latitude": 51.1657,
            "longitude": 10.4515,
            "timezone": "Europe/Berlin",
            "source": "germany-centroid",
            "query_used": "Deutschland",
        }
    queries = location.get("query_candidates") or [location.get("query"), location.get("city"), location.get("zipcode")]
    for query in queries:
        if not query:
            continue
        result = _open_meteo_geocode(query)
        if result:
            return {**result, "query_used": query}
    return None
def _daily_fields() -> str:
    # One compact weather vector is enough for the AI context:
    # mean temperature, precipitation, snowfall/frost proxy, wind and cloud cover.
    return "temperature_2m_mean,precipitation_sum,snowfall_sum,wind_speed_10m_max,cloud_cover_mean"


def _parse_open_meteo_daily(payload: dict, source_name: str) -> dict[date, dict]:
    daily = payload.get("daily", {})
    times = daily.get("time", [])
    values = {
        "temperature_c": daily.get("temperature_2m_mean", []),
        "precipitation_mm": daily.get("precipitation_sum", []),
        "snowfall_mm": daily.get("snowfall_sum", []),
        "wind_kmh": daily.get("wind_speed_10m_max", []),
        "cloud_cover_percent": daily.get("cloud_cover_mean", []),
    }
    result: dict[date, dict] = {}
    for index, timestamp in enumerate(times):
        current_day = date.fromisoformat(timestamp)
        temperature = values["temperature_c"][index] if index < len(values["temperature_c"]) else None
        snowfall = values["snowfall_mm"][index] if index < len(values["snowfall_mm"]) else None
        result[current_day] = {
            "temperature_c": temperature,
            "precipitation_mm": values["precipitation_mm"][index] if index < len(values["precipitation_mm"]) else None,
            "snow_or_frost": bool((snowfall or 0) > 0 or (temperature is not None and temperature <= 1.0)),
            "wind_kmh": values["wind_kmh"][index] if index < len(values["wind_kmh"]) else None,
            "cloud_cover_percent": values["cloud_cover_percent"][index] if index < len(values["cloud_cover_percent"]) else None,
            "source": source_name,
        }
    return result


@lru_cache(maxsize=256)
def _open_meteo_archive(latitude: float, longitude: float, start_iso: str, end_iso: str, timezone: str) -> dict[date, dict]:
    try:
        response = httpx.get(
            OPEN_METEO_ARCHIVE_URL,
            params={
                "latitude": latitude,
                "longitude": longitude,
                "start_date": start_iso,
                "end_date": end_iso,
                "daily": _daily_fields(),
                "timezone": timezone,
            },
            timeout=10,
        )
        response.raise_for_status()
        return _parse_open_meteo_daily(response.json(), "open-meteo-archive")
    except Exception as exc:
        logger.info("Open-Meteo archive request failed for %s..%s: %s", start_iso, end_iso, exc)
        return {}


@lru_cache(maxsize=256)
def _open_meteo_forecast(latitude: float, longitude: float, start_iso: str, end_iso: str, timezone: str) -> dict[date, dict]:
    try:
        response = httpx.get(
            OPEN_METEO_FORECAST_URL,
            params={
                "latitude": latitude,
                "longitude": longitude,
                "start_date": start_iso,
                "end_date": end_iso,
                "daily": _daily_fields(),
                "timezone": timezone,
            },
            timeout=10,
        )
        response.raise_for_status()
        return _parse_open_meteo_daily(response.json(), "open-meteo-forecast")
    except Exception as exc:
        logger.info("Open-Meteo forecast request failed for %s..%s: %s", start_iso, end_iso, exc)
        return {}


def _try_current_tomorrow_weather(latitude: float, longitude: float) -> dict | None:
    if not settings.tomorrow_api_key:
        return None

    try:
        response = httpx.get(
            "https://api.tomorrow.io/v4/weather/realtime",
            params={
                "location": f"{latitude},{longitude}",
                "units": "metric",
                "apikey": settings.tomorrow_api_key,
            },
            timeout=5,
        )
        response.raise_for_status()
        values = response.json().get("data", {}).get("values", {})
        temperature = values.get("temperature")
        return {
            "temperature_c": temperature,
            "precipitation_mm": values.get("precipitationIntensity", 0.0),
            "snow_or_frost": (temperature or 10) <= 1,
            "wind_kmh": values.get("windSpeed"),
            "cloud_cover_percent": values.get("cloudCover"),
            "source": "tomorrow.io-realtime",
        }
    except Exception as exc:
        logger.info("Tomorrow.io realtime request failed: %s", exc)
        return None


def _external_daily_weather(location: dict | None, start: date, end: date) -> dict:
    provider_mode = (settings.weather_provider or "auto").lower()
    if provider_mode == "mock":
        return {
            "daily": {},
            "warnings": [],
            "location": location,
            "status": {
                "tomorrow": {
                    "ok": True,
                    "indicator": "disabled",
                    "description": "Tomorrow.io Statusprüfung deaktiviert.",
                    "source": "disabled",
                }
            },
        }

    coordinates = _resolve_coordinates(location)
    tomorrow_page_status = {
        "ok": True,
        "indicator": "not-used",
        "description": "Tomorrow.io wurde nicht benötigt; Open-Meteo ist primaere Wetterquelle.",
        "source": "local",
    }
    warnings: list[str] = []
    if not coordinates:
        return {"daily": {}, "warnings": warnings, "location": location, "status": {"tomorrow": tomorrow_page_status}}

    latitude = coordinates["latitude"]
    longitude = coordinates["longitude"]
    timezone = coordinates["timezone"]
    resolved_location = {**(location or {}), "query_used": coordinates.get("query_used"), "latitude": latitude, "longitude": longitude}
    today = date.today()
    result: dict[date, dict] = {}

    use_open_meteo = provider_mode in {"auto", "open_meteo", "open-meteo"}
    if use_open_meteo:
        # Open-Meteo is the primary source. It needs no API key and supports
        # archive plus near-future forecast well enough for the demo.
        if start <= today - timedelta(days=1):
            archive_end = min(end, today - timedelta(days=1))
            result.update(_open_meteo_archive(latitude, longitude, start.isoformat(), archive_end.isoformat(), timezone))

        # Forecast/today data comes from Open-Meteo forecast for any dates inside
        # its 16-day horizon. Far-future buckets remain on the local fallback.
        forecast_start = max(start, today)
        forecast_end = min(end, today + timedelta(days=OPEN_METEO_FORECAST_HORIZON_DAYS))
        if forecast_start <= forecast_end:
            result.update(
                _open_meteo_forecast(
                    latitude,
                    longitude,
                    forecast_start.isoformat(),
                    forecast_end.isoformat(),
                    timezone,
                )
            )

    # Tomorrow.io is only a backup for today's realtime value. We intentionally
    # do not check the Tomorrow status page before Open-Meteo, because that was
    # adding avoidable latency to every chat/weather request.
    should_try_tomorrow_backup = (
        bool(settings.tomorrow_api_key)
        and provider_mode in {"auto", "tomorrow"}
        and today not in result
        and start <= today <= end
    )
    if should_try_tomorrow_backup:
        tomorrow_page_status = tomorrow_status()
        warning_text = _tomorrow_status_warning(tomorrow_page_status)
        if warning_text:
            warnings.append(warning_text)
        if tomorrow_page_status.get("ok", True):
            current = _try_current_tomorrow_weather(latitude, longitude)
            if current:
                result[today] = current

    return {"daily": result, "warnings": warnings, "location": resolved_location, "status": {"tomorrow": tomorrow_page_status}}


def _mean(values: list[float | None]) -> float | None:
    clean = [float(value) for value in values if value is not None]
    if not clean:
        return None
    return round(sum(clean) / len(clean), 2)


def _sum(values: list[float | None]) -> float | None:
    clean = [float(value) for value in values if value is not None]
    if not clean:
        return None
    return round(sum(clean), 2)


def _aggregate_label_weather(label: str, bucket_days: list[date], daily_weather: dict[date, dict]) -> dict | None:
    rows = [daily_weather.get(day) for day in bucket_days]
    if any(row is None for row in rows):
        return None

    sources = {row["source"] for row in rows if row}
    return {
        "x": label,
        "temperature_c": _mean([row["temperature_c"] for row in rows if row]),
        "precipitation_mm": _sum([row["precipitation_mm"] for row in rows if row]),
        "snow_or_frost": any(bool(row["snow_or_frost"]) for row in rows if row),
        "wind_kmh": _mean([row["wind_kmh"] for row in rows if row]),
        "cloud_cover_percent": _mean([row["cloud_cover_percent"] for row in rows if row]),
        "source": sources.pop() if len(sources) == 1 else "mixed-external",
    }


def weather_context(
    frame: pd.DataFrame,
    labels: list[str],
    granularity: str,
    include_external: bool = True,
) -> dict:
    temperatures = _bucket_temperatures(frame, granularity)
    fallback = {label: _mock_weather(label, temperatures.get(label)) for label in labels}
    if not include_external or not labels:
        return {
            "series": [fallback[label] for label in labels],
            "warnings": [],
            "location": None,
            "status": {"tomorrow": {"ok": True, "indicator": "disabled", "description": "External weather disabled.", "source": "disabled"}},
        }

    location = _location_context(frame)
    if not location:
        return {
            "series": [fallback[label] for label in labels],
            "warnings": [],
            "location": None,
            "status": {"tomorrow": {"ok": True, "indicator": "unavailable", "description": "No location available.", "source": "local"}},
        }

    overall_start, _ = _label_bounds(labels[0], granularity)
    _, overall_end = _label_bounds(labels[-1], granularity)
    external_bundle = _external_daily_weather(location, overall_start, overall_end)
    external_daily = external_bundle["daily"]
    if not external_daily:
        return {
            "series": [fallback[label] for label in labels],
            "warnings": external_bundle["warnings"],
            "location": external_bundle.get("location", location),
            "status": external_bundle["status"],
        }

    result: list[dict] = []
    for label in labels:
        bucket_start, bucket_end = _label_bounds(label, granularity)
        bucket_days = _date_span(bucket_start, bucket_end)
        external_bucket = _aggregate_label_weather(label, bucket_days, external_daily)
        result.append(external_bucket or fallback[label])
    return {"series": result, "warnings": external_bundle["warnings"], "location": external_bundle.get("location", location), "status": external_bundle["status"]}


