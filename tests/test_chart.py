from datetime import date
from pathlib import Path
import sys

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.db import get_connection, init_db
from app.services.aggregation_service import chart_payload
from app.services.csv_loader import import_csv_directory
from tests.support import local_temp_dir


def test_chart_payload_contains_expected_series():
    with local_temp_dir() as tmp_path:
        connection = get_connection(f"sqlite:///{tmp_path / 'test.db'}")
        init_db(connection)
        sample_dir = Path(__file__).resolve().parents[1] / "data" / "sample_csvs"
        import_csv_directory(connection, str(sample_dir))

        offset_to_2026 = 2026 - date.today().year
        payload = chart_payload(connection, "total", None, "year", offset_to_2026, True, "local")

        assert payload["scope"]["type"] == "total"
        assert len(payload["x_axis"]) == 12
        assert set(payload["series"]) == {
            "actual_energy",
            "predicted_energy",
            "optimized_energy",
            "actual_co2",
            "predicted_co2",
            "optimized_co2",
        }
        assert sum(payload["series"]["actual_energy"]) > 0
        assert payload["mold_risk"]["level"] in {"low", "medium", "elevated", "unknown"}
        assert "caveat" in payload["mold_risk"]
        assert payload["ai_explanations"]["provider"] == "local"
        connection.close()

