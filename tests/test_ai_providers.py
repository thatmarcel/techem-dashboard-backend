from types import SimpleNamespace

from app.services import ai_analysis_service
from app.services.vertex_provider import VertexProvider


def _chart_context():
    return {
        "x_axis": ["2026-04-24"],
        "series": {"actual_energy": [10.0], "actual_co2": [2.0]},
        "baseline_energy": [11.0],
        "average_emission_factor_kg_per_kwh": 0.2,
        "weather": [{"x": "2026-04-24", "temperature_c": 8.0, "precipitation_mm": 0.0, "snow_or_frost": False}],
        "calendar": [{"x": "2026-04-24", "is_weekend": False, "is_holiday": False}],
        "summary": {"total_energy_kwh": 10.0, "total_co2_kg": 2.0},
        "scope": {"label": "Test"},
    }


def test_chart_vertex_falls_back_to_local_when_not_configured():
    result = ai_analysis_service.analyze_chart(_chart_context(), "vertex")

    assert result.provider == "local"
    assert result.points[0].x == "2026-04-24"
    assert result.points[0].predicted_energy > 0


def test_vertex_provider_sends_compact_predict_instance(monkeypatch):
    captured = {}

    monkeypatch.setattr(
        "app.services.vertex_provider.settings",
        SimpleNamespace(
            vertex_project_id="project",
            vertex_location="europe-west3",
            vertex_endpoint_id="endpoint",
            vertex_access_token="token",
        ),
    )

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "predictions": [
                    {
                        "provider": "vertex",
                        "points": [
                            {
                                "x": "2026-04-24",
                                "predicted_energy": 11.0,
                                "predicted_co2": 2.2,
                                "optimized_energy": 9.9,
                                "optimized_co2": 1.98,
                            }
                        ],
                        "explanations": [],
                        "influencing_factors": [],
                        "anomalies": [],
                        "fallback_used": False,
                    }
                ]
            }

    def fake_post(url, headers, json, timeout):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        captured["timeout"] = timeout
        return Response()

    monkeypatch.setattr("app.services.vertex_provider.httpx.post", fake_post)

    result = VertexProvider().analyze_chart(_chart_context())

    assert result["provider"] == "vertex"
    assert captured["headers"]["Authorization"] == "Bearer token"
    assert captured["json"]["instances"][0]["task"] == "chart"
    assert "weather" in captured["json"]["instances"][0]["context"]
    assert "calendar" in captured["json"]["instances"][0]["context"]
