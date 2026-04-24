from pathlib import Path
import sys

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.db import get_connection, init_db
from app.services.csv_loader import import_csv_directory
from tests.support import local_temp_dir


def test_import_sample_csvs():
    with local_temp_dir() as tmp_path:
        db_path = tmp_path / "test.db"
        connection = get_connection(f"sqlite:///{db_path}")
        init_db(connection)

        sample_dir = Path(__file__).resolve().parents[1] / "data" / "sample_csvs"
        result = import_csv_directory(connection, str(sample_dir))

        assert result["imported_files"] == 5
        assert result["inserted_rows"] == 33

        count = connection.execute("SELECT COUNT(*) FROM consumption_records").fetchone()[0]
        assert count == 33

        row = connection.execute(
            "SELECT zipcode, street, housenumber, apartment_number FROM consumption_records WHERE city = ?",
            ("Halle",),
        ).fetchone()
        assert row["zipcode"] == "06110"
        assert row["street"] == "Merseburger Straße"
        assert row["housenumber"] == "12"
        assert row["apartment_number"] == "1"
        connection.close()


def test_import_accepts_quoted_path_and_uppercase_csv_extension():
    with local_temp_dir() as tmp_path:
        db_path = tmp_path / "test.db"
        connection = get_connection(f"sqlite:///{db_path}")
        init_db(connection)

        import_dir = tmp_path / "Desktop Import"
        import_dir.mkdir()
        source_csv = Path(__file__).resolve().parents[1] / "data" / "sample_csvs" / "halle_merseburger_strasse.csv"
        target_csv = import_dir / "HALLE_EXPORT.CSV"
        target_csv.write_text(source_csv.read_text(encoding="utf-8"), encoding="utf-8")

        result = import_csv_directory(connection, f'"{import_dir}"')

        assert result["imported_files"] == 1
        assert result["inserted_rows"] == 1
        connection.close()


def test_import_accepts_current_source_export_format():
    with local_temp_dir() as tmp_path:
        db_path = tmp_path / "test.db"
        connection = get_connection(f"sqlite:///{db_path}")
        init_db(connection)

        import_dir = tmp_path / "current_source_format"
        import_dir.mkdir()
        csv_file = import_dir / "source_export.csv"
        csv_file.write_text(
            "date,zipcode,energysource,city,energyusage [kWh],livingspace [m²],"
            "mean outside temperature [°C],roomnumber,emission factor [g/kWh],"
            "unitnumber,street_name,house_number,building,apartment_number\n"
            "2019-12-31,6110,Erdgas,Halle,0.71,9.4,4.1,1,181.39,"
            "999,Merseburger Straße,12,Quelle Building 999,8\n",
            encoding="utf-8",
        )

        result = import_csv_directory(connection, str(import_dir))

        assert result["imported_files"] == 1
        assert result["inserted_rows"] == 1
        assert result["files"][0]["column_mapping"]["street_name"] == "street"
        assert result["files"][0]["column_mapping"]["house_number"] == "housenumber"

        row = connection.execute(
            "SELECT zipcode, street, housenumber, building_id, apartment_number, apartment_id, unitnumber "
            "FROM consumption_records"
        ).fetchone()
        assert row["zipcode"] == "06110"
        assert row["street"] == "Merseburger Straße"
        assert row["housenumber"] == "12"
        assert row["building_id"] == "halle-merseburger-strasse-12"
        assert row["apartment_number"] == "8"
        assert row["apartment_id"] == "halle-merseburger-strasse-12-apartment-8"
        assert row["unitnumber"] == "999"
        connection.close()
