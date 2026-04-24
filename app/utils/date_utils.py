from calendar import monthrange
from datetime import date, timedelta


VALID_PERIODS = {"day", "week", "month", "quarter", "year"}


def add_months(value: date, months: int) -> date:
    month = value.month - 1 + months
    year = value.year + month // 12
    month = month % 12 + 1
    day = min(value.day, monthrange(year, month)[1])
    return date(year, month, day)


def resolve_period(period: str, offset: int = 0, today: date | None = None) -> dict:
    if period not in VALID_PERIODS:
        raise ValueError(f"Unsupported period '{period}'.")

    current = today or date.today()

    if period == "day":
        start = current + timedelta(days=offset)
        end = start
        granularity = "day"
    elif period == "week":
        start = current - timedelta(days=current.weekday()) + timedelta(weeks=offset)
        end = start + timedelta(days=6)
        granularity = "day"
    elif period == "month":
        shifted = add_months(current.replace(day=1), offset)
        start = shifted
        end = shifted.replace(day=monthrange(shifted.year, shifted.month)[1])
        granularity = "day"
    elif period == "quarter":
        quarter_start_month = ((current.month - 1) // 3) * 3 + 1
        base = date(current.year, quarter_start_month, 1)
        start = add_months(base, offset * 3)
        end_month = add_months(start, 2)
        end = end_month.replace(day=monthrange(end_month.year, end_month.month)[1])
        granularity = "month"
    else:
        start = date(current.year + offset, 1, 1)
        end = date(current.year + offset, 12, 31)
        granularity = "month"

    return {"start": start, "end": end, "granularity": granularity}


def bucket_label(value: date, granularity: str) -> str:
    if granularity == "month":
        return value.strftime("%Y-%m")
    return value.isoformat()


def period_buckets(start: date, end: date, granularity: str) -> list[str]:
    labels: list[str] = []
    if granularity == "month":
        cursor = start.replace(day=1)
        while cursor <= end:
            labels.append(bucket_label(cursor, "month"))
            cursor = add_months(cursor, 1)
        return labels

    cursor = start
    while cursor <= end:
        labels.append(bucket_label(cursor, "day"))
        cursor += timedelta(days=1)
    return labels
