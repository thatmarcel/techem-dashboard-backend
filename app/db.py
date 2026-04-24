import sqlite3
from collections.abc import Iterable

from app.config import sqlite_path_from_url, settings


# One flat table is enough for the demo. City/building/apartment views are
# derived by grouping this table, so there is no hidden ORM behavior.
SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS consumption_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    zipcode TEXT NOT NULL,
    city TEXT NOT NULL,
    city_id TEXT NOT NULL,
    street TEXT NOT NULL,
    housenumber TEXT NOT NULL,
    building_id TEXT NOT NULL,
    apartment_number TEXT NOT NULL,
    apartment_id TEXT NOT NULL,
    energysource TEXT NOT NULL,
    energyusage_kwh REAL NOT NULL,
    livingspace_m2 REAL NOT NULL,
    mean_outside_temperature_c REAL,
    roomnumber INTEGER,
    emission_factor_g_per_kwh REAL NOT NULL,
    unitnumber TEXT,
    co2_g REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_records_city ON consumption_records(city_id);
CREATE INDEX IF NOT EXISTS idx_records_building ON consumption_records(building_id);
CREATE INDEX IF NOT EXISTS idx_records_apartment ON consumption_records(apartment_id);
CREATE INDEX IF NOT EXISTS idx_records_date ON consumption_records(date);
"""


INSERT_SQL = """
INSERT INTO consumption_records (
    date, zipcode, city, city_id, street, housenumber, building_id,
    apartment_number, apartment_id, energysource, energyusage_kwh,
    livingspace_m2, mean_outside_temperature_c, roomnumber,
    emission_factor_g_per_kwh, unitnumber, co2_g
) VALUES (
    :date, :zipcode, :city, :city_id, :street, :housenumber, :building_id,
    :apartment_number, :apartment_id, :energysource, :energyusage_kwh,
    :livingspace_m2, :mean_outside_temperature_c, :roomnumber,
    :emission_factor_g_per_kwh, :unitnumber, :co2_g
)
"""


def get_connection(database_url: str | None = None) -> sqlite3.Connection:
    # row_factory lets callers access columns by name: row["city_id"].
    db_path = sqlite_path_from_url(database_url or settings.database_url)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    # FastAPI can open the dependency in one worker thread and hand the same
    # connection to Pandas or the cleanup phase in another one. SQLite blocks
    # that by default, so this demo keeps the connection request-scoped but
    # explicitly allows cross-thread use for the same request lifecycle.
    connection = sqlite3.connect(db_path, check_same_thread=False)
    connection.row_factory = sqlite3.Row
    return connection


def init_db(connection: sqlite3.Connection) -> None:
    connection.executescript(SCHEMA_SQL)
    connection.commit()


def get_db():
    # FastAPI dependency: each request gets a short-lived SQLite connection.
    connection = get_connection()
    try:
        init_db(connection)
        yield connection
    finally:
        connection.close()


def replace_records(connection: sqlite3.Connection, records: Iterable[dict]) -> int:
    # Import is intentionally replace-all for the prototype: one clean demo
    # dataset at a time, no partial merge logic.
    init_db(connection)
    rows = list(records)
    with connection:
        connection.execute("DELETE FROM consumption_records")
        if rows:
            connection.executemany(INSERT_SQL, rows)
    return len(rows)
