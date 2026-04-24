from datetime import date
from pathlib import Path
import sys

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.db import get_connection, init_db
from app.services.csv_loader import import_csv_directory
from app.services.report_service import build_report
from tests.support import local_temp_dir


def test_build_report_returns_structured_result():
    with local_temp_dir() as tmp_path:
        connection = get_connection(f"sqlite:///{tmp_path / 'test.db'}")
        init_db(connection)
        sample_dir = Path(__file__).resolve().parents[1] / "data" / "sample_csvs"
        import_csv_directory(connection, str(sample_dir))

        offset_to_2026 = 2026 - date.today().year
        report = build_report(connection, "total", None, "year", offset_to_2026, "local")

        assert report["provider"] == "local"
        assert report["title"]
        assert "scope" in report["used_context"]
        assert "period" in report["used_context"]
        connection.close()

