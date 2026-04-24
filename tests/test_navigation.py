from pathlib import Path
import sys

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.db import get_connection, init_db
from app.services.aggregation_service import apartment_details, building_details, city_details, navigation_overview
from app.services.csv_loader import import_csv_directory
from tests.support import local_temp_dir


def test_navigation_overview_groups_cities():
    with local_temp_dir() as tmp_path:
        connection = get_connection(f"sqlite:///{tmp_path / 'test.db'}")
        init_db(connection)
        sample_dir = Path(__file__).resolve().parents[1] / "data" / "sample_csvs"
        import_csv_directory(connection, str(sample_dir))

        overview = navigation_overview(connection)

        assert overview["summary"]["total_energy_kwh"] > 0
        assert {city["city_id"] for city in overview["cities"]} == {"frankfurt", "halle", "hamburg", "muenchen"}
        connection.close()


def test_city_and_building_details():
    with local_temp_dir() as tmp_path:
        connection = get_connection(f"sqlite:///{tmp_path / 'test.db'}")
        init_db(connection)
        sample_dir = Path(__file__).resolve().parents[1] / "data" / "sample_csvs"
        import_csv_directory(connection, str(sample_dir))

        city = city_details(connection, "frankfurt")
        building = building_details(connection, "frankfurt-kapellstrasse-3")
        apartment = apartment_details(connection, building["apartments"][0]["apartment_id"])

        assert len(city["buildings"]) == 2
        assert len(building["apartments"]) == 2
        assert city["buildings"][0]["mold_risk"]["level"] in {"low", "medium", "elevated", "unknown"}
        assert building["apartments"][0]["mold_risk"]["label"]
        assert apartment["metadata"]["mold_risk"]["caveat"]
        connection.close()
