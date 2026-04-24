from pathlib import Path
import sys

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.db import get_connection, init_db
from app.schemas.requests import ChatRequest
from app.services.chat_service import answer_chat
from app.services.csv_loader import import_csv_directory
from tests.support import local_temp_dir


def test_chat_uses_compact_scope_and_selected_context_files():
    with local_temp_dir() as tmp_path:
        connection = get_connection(f"sqlite:///{tmp_path / 'test.db'}")
        init_db(connection)
        sample_dir = Path(__file__).resolve().parents[1] / "data" / "sample_csvs"
        import_csv_directory(connection, str(sample_dir))

        request = ChatRequest(
            message="Warum ist Wohnung 8 auffaellig?",
            use_current_scope=True,
            scope_type="apartment",
            scope_id="frankfurt-kapellstrasse-3-apartment-8",
            period="month",
            offset=0,
            analysis_provider="local",
            additional_instructions="Antworte knapp.",
            context_file_paths=["data/sample_csvs/frankfurt_kapellstrasse.csv", "../start_demo.py"],
        )

        response = answer_chat(connection, request)

        assert response["provider"] == "local"
        assert response["used_context"]["mode"] == "current_scope"
        assert response["used_context"]["scope"]["type"] == "apartment"
        assert "series" in response["used_context"]
        assert "ai_explanations" not in response["used_context"]
        assert "baseline_energy" in response["used_context"]
        assert response["used_context"]["additional_instructions"] == "Antworte knapp."
        assert len(response["used_context"]["context_files"]) == 1
        assert response["used_context"]["context_files"][0]["path"] == "data/sample_csvs/frankfurt_kapellstrasse.csv"
        connection.close()


def test_chat_includes_current_weather_for_selected_scope(monkeypatch):
    with local_temp_dir() as tmp_path:
        connection = get_connection(f"sqlite:///{tmp_path / 'test.db'}")
        init_db(connection)
        sample_dir = Path(__file__).resolve().parents[1] / "data" / "sample_csvs"
        import_csv_directory(connection, str(sample_dir))

        from app.services import chat_service

        def fake_weather_context(frame, labels, granularity, include_external=True):
            return {
                "series": [
                    {
                        "x": label,
                        "temperature_c": 12.3,
                        "precipitation_mm": 0.4,
                        "snow_or_frost": False,
                        "wind_kmh": 9.0,
                        "cloud_cover_percent": 55.0,
                        "source": "open-meteo-forecast",
                    }
                    for label in labels
                ],
                "warnings": [],
                "location": {"city": "Frankfurt", "zipcode": "60311", "query_used": "60311 Frankfurt, Deutschland"},
                "status": {"tomorrow": {"ok": True}},
            }

        monkeypatch.setattr(chat_service, "weather_context", fake_weather_context)

        request = ChatRequest(
            message="Wie ist das aktuelle Wetter in diesem Scope?",
            use_current_scope=True,
            scope_type="apartment",
            scope_id="frankfurt-kapellstrasse-3-apartment-8",
            period="month",
            offset=0,
            analysis_provider="local",
        )

        response = answer_chat(connection, request)
        used_context = response["used_context"]

        assert used_context["current_weather"]["source"] == "open-meteo-forecast"
        assert used_context["current_weather"]["temperature_c"] == 12.3
        assert used_context["current_weather_location"]["city"] == "Frankfurt"
        connection.close()


def test_chat_uses_selected_scope_for_weather_even_with_broad_context(monkeypatch):
    with local_temp_dir() as tmp_path:
        connection = get_connection(f"sqlite:///{tmp_path / 'test.db'}")
        init_db(connection)
        sample_dir = Path(__file__).resolve().parents[1] / "data" / "sample_csvs"
        import_csv_directory(connection, str(sample_dir))

        request = ChatRequest(
            message="Wie ist das aktuelle Wetter dort?",
            use_current_scope=False,
            scope_type="city",
            scope_id="frankfurt",
            period="month",
            offset=0,
            analysis_provider="local",
        )

        response = answer_chat(connection, request)
        used_context = response["used_context"]

        assert used_context["current_weather_location"]["city"] == "Frankfurt"
        assert used_context["current_weather_location"]["query_used"] == "Frankfurt am Main, Deutschland"
        assert used_context["weather_location_source"] == "selected_scope"
        connection.close()


def test_broad_chat_context_contains_compact_rankings():
    with local_temp_dir() as tmp_path:
        connection = get_connection(f"sqlite:///{tmp_path / 'test.db'}")
        init_db(connection)
        sample_dir = Path(__file__).resolve().parents[1] / "data" / "sample_csvs"
        import_csv_directory(connection, str(sample_dir))

        request = ChatRequest(
            message="Welche Stadt verursacht am meisten CO2?",
            use_current_scope=False,
            scope_type="total",
            period="month",
            offset=0,
            analysis_provider="local",
        )

        response = answer_chat(connection, request)
        used_context = response["used_context"]

        assert used_context["mode"] == "all_data"
        assert used_context["city_rankings"]
        assert used_context["city_rankings"][0]["label"] == "Frankfurt"
        assert used_context["city_rankings"][0]["total_co2_kg"] > 0
        assert used_context["building_rankings"]
        assert used_context["apartment_rankings"]
        assert "energyusage_kwh" not in used_context["city_rankings"][0]
        connection.close()


def test_chat_includes_city_weather_contexts_for_mentioned_cities(monkeypatch):
    with local_temp_dir() as tmp_path:
        connection = get_connection(f"sqlite:///{tmp_path / 'test.db'}")
        init_db(connection)
        sample_dir = Path(__file__).resolve().parents[1] / "data" / "sample_csvs"
        import_csv_directory(connection, str(sample_dir))

        from app.services import chat_service

        def fake_weather_context(frame, labels, granularity, include_external=True):
            city = frame.iloc[0]["city"] if not frame.empty else "Deutschland"
            return {
                "series": [
                    {
                        "x": labels[0],
                        "temperature_c": 10.0 if city == "Frankfurt" else 7.0,
                        "precipitation_mm": 0.0,
                        "snow_or_frost": False,
                        "wind_kmh": 8.0,
                        "cloud_cover_percent": 50.0,
                        "source": "open-meteo-forecast",
                    }
                ],
                "warnings": [],
                "location": {"city": city, "query_used": f"{city}, Deutschland"},
                "status": {"tomorrow": {"ok": True}},
            }

        monkeypatch.setattr(chat_service, "weather_context", fake_weather_context)

        request = ChatRequest(
            message="Vergleiche Immobilien in Frankfurt und Hamburg unter Beruecksichtigung des Wetters.",
            use_current_scope=False,
            scope_type="total",
            period="month",
            offset=0,
            analysis_provider="local",
        )

        response = answer_chat(connection, request)
        city_contexts = response["used_context"]["city_weather_contexts"]
        cities = {item["city"] for item in city_contexts}

        assert {"Frankfurt", "Hamburg"}.issubset(cities)
        assert all(item["weather"]["source"] == "open-meteo-forecast" for item in city_contexts)
        connection.close()


def test_chat_includes_city_weather_context_for_selected_building_scope(monkeypatch):
    with local_temp_dir() as tmp_path:
        connection = get_connection(f"sqlite:///{tmp_path / 'test.db'}")
        init_db(connection)
        sample_dir = Path(__file__).resolve().parents[1] / "data" / "sample_csvs"
        import_csv_directory(connection, str(sample_dir))

        from app.services import chat_service

        def fake_weather_context(frame, labels, granularity, include_external=True):
            city = frame.iloc[0]["city"] if not frame.empty else "Deutschland"
            return {
                "series": [
                    {
                        "x": labels[0],
                        "temperature_c": 11.5,
                        "precipitation_mm": 0.2,
                        "snow_or_frost": False,
                        "wind_kmh": 7.0,
                        "cloud_cover_percent": 45.0,
                        "source": "open-meteo-forecast",
                    }
                ],
                "warnings": [],
                "location": {"city": city, "query_used": f"{city}, Deutschland"},
                "status": {"tomorrow": {"ok": True}},
            }

        monkeypatch.setattr(chat_service, "weather_context", fake_weather_context)

        request = ChatRequest(
            message="Analysiere diese Immobilie mit lokalem Wetter.",
            use_current_scope=True,
            scope_type="building",
            scope_id="frankfurt-kapellstrasse-3",
            period="month",
            offset=0,
            analysis_provider="local",
        )

        response = answer_chat(connection, request)
        city_contexts = response["used_context"]["city_weather_contexts"]

        assert len(city_contexts) == 1
        assert city_contexts[0]["city"] == "Frankfurt"
        assert city_contexts[0]["weather"]["temperature_c"] == 11.5
        connection.close()

