import re
import unicodedata
from typing import Iterable

import pandas as pd


REQUIRED_COLUMNS = [
    "date",
    "zipcode",
    "city",
    "street",
    "housenumber",
    "apartment_number",
    "energysource",
    "energyusage_kwh",
    "livingspace_m2",
    "mean_outside_temperature_c",
    "roomnumber",
    "emission_factor_g_per_kwh",
]


# The importer first normalizes every incoming header to a simple snake_case
# token, then applies these known aliases. This keeps real CSV variations out
# of the rest of the backend.
COLUMN_ALIASES = {
    "zip": "zipcode",
    "postalcode": "zipcode",
    "postal_code": "zipcode",
    "plz": "zipcode",
    "street_name": "street",
    "house_number": "housenumber",
    "house_no": "housenumber",
    "apartment": "apartment_number",
    "apartment_no": "apartment_number",
    "flat": "apartment_number",
    "unit": "unitnumber",
    "unit_number": "unitnumber",
    "energy_source": "energysource",
    "energy_usage_kwh": "energyusage_kwh",
    "usage_kwh": "energyusage_kwh",
    "consumption_kwh": "energyusage_kwh",
    "living_space_m2": "livingspace_m2",
    "living_area_m2": "livingspace_m2",
    "area_m2": "livingspace_m2",
    "mean_temperature_c": "mean_outside_temperature_c",
    "outside_temperature_c": "mean_outside_temperature_c",
    "temperature_c": "mean_outside_temperature_c",
    "rooms": "roomnumber",
    "room_count": "roomnumber",
    "emission_factor": "emission_factor_g_per_kwh",
    "co2_factor_g_per_kwh": "emission_factor_g_per_kwh",
    "emission_factor_g_kwh": "emission_factor_g_per_kwh",
    "livingspace_m": "livingspace_m2",
    "living_space_m": "livingspace_m2",
    "living_area_m": "livingspace_m2",
}


def normalize_column_name(name: str) -> str:
    # Examples:
    # "energyusage [kWh]" -> "energyusage_kwh"
    # "mean outside temperature [deg C]" -> "mean_outside_temperature_c"
    cleaned = str(name).strip().lower()
    cleaned = re.sub(r"[^a-z0-9]+", "_", cleaned)
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    return COLUMN_ALIASES.get(cleaned, cleaned)


def normalize_columns(columns: Iterable[str]) -> dict[str, str]:
    return {column: normalize_column_name(column) for column in columns}


def slugify(value: object) -> str:
    # Slugs become stable ids for navigation/search, not display labels.
    text = unicodedata.normalize("NFKD", str(value))
    text = text.replace("\u00df", "ss").replace("\u1e9e", "SS")
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.strip().lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return re.sub(r"-+", "-", text).strip("-") or "unknown"


def clean_text(value: object) -> str:
    if pd.isna(value):
        return ""
    text = str(value).strip()
    if text.endswith(".0") and text[:-2].isdigit():
        text = text[:-2]
    return text


def normalize_zipcode(value: object) -> str:
    text = clean_text(value)
    if text.isdigit() and len(text) < 5:
        return text.zfill(5)
    return text


def split_full_address(value: object) -> tuple[str, str]:
    # Real Techem-style files provide "Merseburger Strasse 12, 06110"
    # instead of separate street/housenumber columns.
    text = clean_text(value)
    address_part = text.split(",", 1)[0].strip()
    match = re.match(r"^(?P<street>.+?)\s+(?P<number>\d+[a-zA-Z]?(?:[-/]\d+[a-zA-Z]?)?)$", address_part)
    if not match:
        return address_part, "unknown"
    return match.group("street").strip(), match.group("number").strip()


def zipcode_from_full_address(value: object) -> str:
    match = re.search(r"\b(\d{5})\b", clean_text(value))
    return match.group(1) if match else ""


def enrich_derived_columns(frame: pd.DataFrame) -> pd.DataFrame:
    # Fill fields that are missing in the source CSV but needed internally.
    enriched = frame.copy()

    if "full_address" in enriched.columns:
        parsed_addresses = enriched["full_address"].map(split_full_address)
        if "street" not in enriched.columns:
            enriched["street"] = parsed_addresses.map(lambda item: item[0])
        if "housenumber" not in enriched.columns:
            enriched["housenumber"] = parsed_addresses.map(lambda item: item[1])
        if "zipcode" not in enriched.columns:
            enriched["zipcode"] = enriched["full_address"].map(zipcode_from_full_address)
        else:
            address_zipcodes = enriched["full_address"].map(zipcode_from_full_address)
            enriched["zipcode"] = enriched["zipcode"].where(
                enriched["zipcode"].map(clean_text).str.len() >= 5,
                address_zipcodes,
            )

    # apartment_number is the fachliche Wohnungsnummer for this demo.
    # unitnumber may still be stored as source metadata, but it must not be
    # used to identify apartments.
    if "unitnumber" not in enriched.columns:
        enriched["unitnumber"] = ""

    return enriched


def normalize_dataframe(frame: pd.DataFrame, source_name: str) -> tuple[pd.DataFrame, dict]:
    # This is the only place where raw CSV shape is accepted. Downstream code
    # receives one stable internal schema.
    column_mapping = normalize_columns(frame.columns)
    frame = frame.rename(columns=column_mapping).copy()
    frame = enrich_derived_columns(frame)

    missing = [column for column in REQUIRED_COLUMNS if column not in frame.columns]
    if missing:
        raise ValueError(f"{source_name}: missing required columns: {', '.join(missing)}")

    normalized = frame[REQUIRED_COLUMNS].copy()
    # unitnumber remains optional source metadata. It is deliberately not part
    # of apartment identity because apartment_number is the relevant field.
    normalized["unitnumber"] = frame["unitnumber"] if "unitnumber" in frame.columns else ""

    for column in [
        "zipcode",
        "city",
        "street",
        "housenumber",
        "apartment_number",
        "energysource",
        "unitnumber",
    ]:
        if column == "zipcode":
            normalized[column] = normalized[column].map(normalize_zipcode)
        else:
            normalized[column] = normalized[column].map(clean_text)

    normalized["date"] = pd.to_datetime(normalized["date"], errors="coerce").dt.date
    numeric_columns = [
        "energyusage_kwh",
        "livingspace_m2",
        "mean_outside_temperature_c",
        "roomnumber",
        "emission_factor_g_per_kwh",
    ]
    for column in numeric_columns:
        normalized[column] = pd.to_numeric(normalized[column], errors="coerce")

    before = len(normalized)
    normalized = normalized.dropna(
        subset=["date", "energyusage_kwh", "livingspace_m2", "emission_factor_g_per_kwh"]
    )
    normalized = normalized[normalized["energyusage_kwh"] >= 0]
    normalized = normalized[normalized["livingspace_m2"] > 0]
    dropped = before - len(normalized)

    normalized["date"] = normalized["date"].astype(str)
    normalized["roomnumber"] = normalized["roomnumber"].fillna(0).astype(int)
    normalized["mean_outside_temperature_c"] = normalized["mean_outside_temperature_c"].astype(float)
    normalized["emission_factor_g_per_kwh"] = normalized["emission_factor_g_per_kwh"].astype(float)
    normalized["energyusage_kwh"] = normalized["energyusage_kwh"].astype(float)
    normalized["livingspace_m2"] = normalized["livingspace_m2"].astype(float)

    normalized["city_id"] = normalized["city"].map(slugify)
    # IDs are deterministic and derived from human-readable address fields.
    normalized["building_id"] = normalized.apply(
        lambda row: slugify(f"{row['city']} {row['street']} {row['housenumber']}"),
        axis=1,
    )
    normalized["apartment_id"] = normalized.apply(
        lambda row: slugify(f"{row['building_id']} apartment {row['apartment_number']}"),
        axis=1,
    )
    normalized["co2_g"] = normalized["energyusage_kwh"] * normalized["emission_factor_g_per_kwh"]

    ordered_columns = [
        "date",
        "zipcode",
        "city",
        "city_id",
        "street",
        "housenumber",
        "building_id",
        "apartment_number",
        "apartment_id",
        "energysource",
        "energyusage_kwh",
        "livingspace_m2",
        "mean_outside_temperature_c",
        "roomnumber",
        "emission_factor_g_per_kwh",
        "unitnumber",
        "co2_g",
    ]
    metadata = {
        "source": source_name,
        "input_rows": before,
        "valid_rows": len(normalized),
        "dropped_rows": dropped,
        "column_mapping": column_mapping,
    }
    return normalized[ordered_columns], metadata
