from datetime import date, timedelta


STATE_BY_ZIP_PREFIX = {
    "0": "SN",
    "1": "BE",
    "2": "HH",
    "3": "NI",
    "4": "NW",
    "5": "HE",
    "6": "HE",
    "7": "BW",
    "8": "BY",
    "9": "BY",
}


def state_for_zipcode(zipcode: str | None) -> str:
    if not zipcode:
        return "DE"
    return STATE_BY_ZIP_PREFIX.get(str(zipcode).strip()[:1], "DE")


def easter_sunday(year: int) -> date:
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return date(year, month, day)


def holidays_for_year(year: int, state: str = "DE") -> dict[str, str]:
    easter = easter_sunday(year)
    holidays = {
        date(year, 1, 1).isoformat(): "Neujahr",
        (easter - timedelta(days=2)).isoformat(): "Karfreitag",
        (easter + timedelta(days=1)).isoformat(): "Ostermontag",
        date(year, 5, 1).isoformat(): "Tag der Arbeit",
        (easter + timedelta(days=39)).isoformat(): "Christi Himmelfahrt",
        (easter + timedelta(days=50)).isoformat(): "Pfingstmontag",
        date(year, 10, 3).isoformat(): "Tag der Deutschen Einheit",
        date(year, 12, 25).isoformat(): "1. Weihnachtstag",
        date(year, 12, 26).isoformat(): "2. Weihnachtstag",
    }

    if state in {"BW", "BY", "ST"}:
        holidays[date(year, 1, 6).isoformat()] = "Heilige Drei Koenige"
    if state in {"BW", "BY", "HE", "NW", "RP", "SL"}:
        holidays[(easter + timedelta(days=60)).isoformat()] = "Fronleichnam"
    if state == "BY":
        holidays[date(year, 8, 15).isoformat()] = "Mariae Himmelfahrt"
    if state in {"BB", "MV", "SN", "ST", "TH"}:
        holidays[date(year, 10, 31).isoformat()] = "Reformationstag"
    if state in {"BW", "BY", "NW", "RP", "SL"}:
        holidays[date(year, 11, 1).isoformat()] = "Allerheiligen"

    return holidays


def holiday_context(labels: list[str], zipcode: str | None) -> list[dict]:
    state = state_for_zipcode(zipcode)
    years = {int(label[:4]) for label in labels if len(label) >= 4 and label[:4].isdigit()}
    holiday_map: dict[str, str] = {}
    for year in years:
        holiday_map.update(holidays_for_year(year, state))

    result = []
    for label in labels:
        date_part = label if len(label) == 10 else f"{label}-01"
        result.append(
            {
                "x": label,
                "state": state,
                "is_weekend": date.fromisoformat(date_part).weekday() >= 5,
                "holiday_name": holiday_map.get(date_part),
                "is_holiday": date_part in holiday_map,
            }
        )
    return result
