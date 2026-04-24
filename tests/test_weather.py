from datetime import date
from pathlib import Path
import sys
from types import SimpleNamespace

import pandas as pd

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services import weather_service


def test_weather_context_prefers_external_daily_range(monkeypatch):
    frame = pd.DataFrame(
        [
            {
                "date": "2026-04-01",
                "zipcode": "60311",
                "city": "Frankfurt",
                "mean_outside_temperature_c": "8.0",
            },
            {
                "date": "2026-04-02",
                "zipcode": "60311",
                "city": "Frankfurt",
                "mean_outside_temperature_c": "9.0",
            },
        ]
    )

    monkeypatch.setattr(
        weather_service,
        "_external_daily_weather",
        lambda location, start, end: {
            "daily": {
                date(2026, 4, 1): {
                    "temperature_c": 6.5,
                    "precipitation_mm": 1.2,
                    "snow_or_frost": False,
                    "wind_kmh": 14.0,
                    "cloud_cover_percent": 48.0,
                    "source": "open-meteo-archive",
                },
                date(2026, 4, 2): {
                    "temperature_c": 7.0,
                    "precipitation_mm": 0.0,
                    "snow_or_frost": False,
                    "wind_kmh": 11.0,
                    "cloud_cover_percent": 22.0,
                    "source": "open-meteo-archive",
                },
            },
            "warnings": [],
            "status": {"tomorrow": {"ok": True}},
        },
    )

    result = weather_service.weather_context(frame, ["2026-04-01", "2026-04-02"], "day", True)

    assert result["series"][0]["source"] == "open-meteo-archive"
    assert result["series"][0]["temperature_c"] == 6.5
    assert result["series"][1]["wind_kmh"] == 11.0


def test_weather_context_falls_back_for_incomplete_month_bucket(monkeypatch):
    frame = pd.DataFrame(
        [
            {
                "date": "2026-04-01",
                "zipcode": "60311",
                "city": "Frankfurt",
                "mean_outside_temperature_c": "10.0",
            }
        ]
    )

    monkeypatch.setattr(
        weather_service,
        "_external_daily_weather",
        lambda location, start, end: {
            "daily": {
                date(2026, 4, 1): {
                    "temperature_c": 6.5,
                    "precipitation_mm": 1.2,
                    "snow_or_frost": False,
                    "wind_kmh": 14.0,
                    "cloud_cover_percent": 48.0,
                    "source": "open-meteo-archive",
                }
            },
            "warnings": [],
            "status": {"tomorrow": {"ok": True}},
        },
    )

    result = weather_service.weather_context(frame, ["2026-04"], "month", True)

    assert result["series"][0]["source"] == "csv_or_mock"


def test_weather_context_propagates_tomorrow_status_warning(monkeypatch):
    frame = pd.DataFrame(
        [
            {
                "date": "2026-04-24",
                "zipcode": "60311",
                "city": "Frankfurt",
                "mean_outside_temperature_c": "10.0",
            }
        ]
    )

    monkeypatch.setattr(
        weather_service,
        "_external_daily_weather",
        lambda location, start, end: {
            "daily": {
                date(2026, 4, 24): {
                    "temperature_c": 11.0,
                    "precipitation_mm": 0.8,
                    "snow_or_frost": False,
                    "wind_kmh": 9.0,
                    "cloud_cover_percent": 60.0,
                    "source": "open-meteo-forecast",
                }
            },
            "warnings": ["Tomorrow.io status: Major Outage. Open-Meteo wurde als Wetter-Backup verwendet."],
            "status": {"tomorrow": {"ok": False, "indicator": "critical", "description": "Major Outage"}},
        },
    )

    result = weather_service.weather_context(frame, ["2026-04-24"], "day", True)

    assert result["warnings"]
    assert "Open-Meteo" in result["warnings"][0]


def test_resolve_coordinates_prefers_demo_city_over_ambiguous_geocoding():
    location = {
        "scope_level": "address",
        "city": "Frankfurt",
        "zipcode": "60311",
        "street": "Kapellstraße",
        "housenumber": "3",
        "query_candidates": ["Kapellstraße 3, 60311 Frankfurt, Deutschland", "Frankfurt, Deutschland"],
    }

    result = weather_service._resolve_coordinates(location)

    assert result["query_used"] == "Frankfurt am Main, Deutschland"
    assert result["latitude"] == 50.1109
    assert result["longitude"] == 8.6821


def test_open_meteo_forecast_does_not_send_mutually_exclusive_forecast_days(monkeypatch):
    weather_service._open_meteo_forecast.cache_clear()
    captured_params = {}

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "daily": {
                    "time": ["2026-04-24"],
                    "temperature_2m_mean": [14.1],
                    "precipitation_sum": [0.0],
                    "snowfall_sum": [0.0],
                    "wind_speed_10m_max": [9.1],
                    "cloud_cover_mean": [26],
                }
            }

    def fake_get(url, params, timeout):
        captured_params.update(params)
        return Response()

    monkeypatch.setattr(weather_service.httpx, "get", fake_get)

    result = weather_service._open_meteo_forecast(50.1109, 8.6821, "2026-04-24", "2026-04-24", "Europe/Berlin")

    assert "forecast_days" not in captured_params
    assert result[date(2026, 4, 24)]["source"] == "open-meteo-forecast"
    assert result[date(2026, 4, 24)]["temperature_c"] == 14.1


def test_external_weather_uses_open_meteo_before_tomorrow_backup(monkeypatch):
    today = date.today()
    tomorrow_called = {"status": False, "realtime": False}

    monkeypatch.setattr(
        weather_service,
        "settings",
        SimpleNamespace(weather_provider="auto", tomorrow_api_key="demo-key"),
    )
    monkeypatch.setattr(
        weather_service,
        "_resolve_coordinates",
        lambda location: {
            "latitude": 50.1109,
            "longitude": 8.6821,
            "timezone": "Europe/Berlin",
            "query_used": "Frankfurt am Main, Deutschland",
        },
    )
    monkeypatch.setattr(weather_service, "_open_meteo_archive", lambda *args, **kwargs: {})
    monkeypatch.setattr(
        weather_service,
        "_open_meteo_forecast",
        lambda *args, **kwargs: {
            today: {
                "temperature_c": 14.1,
                "precipitation_mm": 0.0,
                "snow_or_frost": False,
                "wind_kmh": 10.5,
                "cloud_cover_percent": 27.0,
                "source": "open-meteo-forecast",
            }
        },
    )

    def fail_tomorrow_status():
        tomorrow_called["status"] = True
        return {"ok": True}

    def fail_tomorrow_realtime(latitude, longitude):
        tomorrow_called["realtime"] = True
        return None

    monkeypatch.setattr(weather_service, "tomorrow_status", fail_tomorrow_status)
    monkeypatch.setattr(weather_service, "_try_current_tomorrow_weather", fail_tomorrow_realtime)

    result = weather_service._external_daily_weather({"city": "Frankfurt"}, today, today)

    assert result["daily"][today]["source"] == "open-meteo-forecast"
    assert tomorrow_called == {"status": False, "realtime": False}
    assert result["status"]["tomorrow"]["indicator"] == "not-used"


def test_external_weather_uses_tomorrow_when_open_meteo_missing_today(monkeypatch):
    today = date.today()

    monkeypatch.setattr(
        weather_service,
        "settings",
        SimpleNamespace(weather_provider="auto", tomorrow_api_key="demo-key"),
    )
    monkeypatch.setattr(
        weather_service,
        "_resolve_coordinates",
        lambda location: {
            "latitude": 50.1109,
            "longitude": 8.6821,
            "timezone": "Europe/Berlin",
            "query_used": "Frankfurt am Main, Deutschland",
        },
    )
    monkeypatch.setattr(weather_service, "_open_meteo_archive", lambda *args, **kwargs: {})
    monkeypatch.setattr(weather_service, "_open_meteo_forecast", lambda *args, **kwargs: {})
    monkeypatch.setattr(
        weather_service,
        "tomorrow_status",
        lambda: {"ok": True, "indicator": "none", "description": "All Systems Operational", "source": "test"},
    )
    monkeypatch.setattr(
        weather_service,
        "_try_current_tomorrow_weather",
        lambda latitude, longitude: {
            "temperature_c": 13.5,
            "precipitation_mm": 0.0,
            "snow_or_frost": False,
            "wind_kmh": 9.5,
            "cloud_cover_percent": 30.0,
            "source": "tomorrow.io-realtime",
        },
    )

    result = weather_service._external_daily_weather({"city": "Frankfurt"}, today, today)

    assert result["daily"][today]["source"] == "tomorrow.io-realtime"
