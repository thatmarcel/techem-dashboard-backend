from fastapi import APIRouter, Depends, Query
import pandas as pd

from app.db import get_db
from app.utils.normalization import slugify


router = APIRouter(prefix="/api/search", tags=["search"])


def _read_all(connection) -> pd.DataFrame:
    return pd.read_sql_query("SELECT * FROM consumption_records", connection)


@router.get("/suggestions")
def suggestions(q: str = Query(default="", min_length=0), connection=Depends(get_db)):
    query = "" if not q.strip() else slugify(q)
    frame = _read_all(connection)
    if frame.empty:
        return {"query": q, "suggestions": []}

    items = []
    for _, row in frame.drop_duplicates("city_id").iterrows():
        items.append(
            {
                "type": "city",
                "id": row["city_id"],
                "label": row["city"],
                "search_text": slugify(row["city"]),
            }
        )
    for _, row in frame.drop_duplicates("building_id").iterrows():
        label = f"{row['street']} {row['housenumber']}, {row['city']}"
        items.append(
            {
                "type": "building",
                "id": row["building_id"],
                "label": label,
                "search_text": slugify(label),
            }
        )
    for _, row in frame.drop_duplicates("apartment_id").iterrows():
        label = f"Wohnung {row['apartment_number']}, {row['street']} {row['housenumber']}, {row['city']}"
        items.append(
            {
                "type": "apartment",
                "id": row["apartment_id"],
                "label": label,
                "search_text": slugify(f"{label} {row['apartment_number']}"),
            }
        )

    def score(item: dict) -> int:
        text = item["search_text"]
        if not query:
            return 1
        if text == query:
            return 100
        if text.startswith(query):
            return 80
        if query in text:
            return 50
        tokens = [token for token in query.split("-") if token]
        return 30 if tokens and all(token in text for token in tokens) else 0

    ranked = []
    for item in items:
        item_score = score(item)
        if item_score:
            ranked.append({key: value for key, value in item.items() if key != "search_text"} | {"score": item_score})
    ranked.sort(key=lambda item: (-item["score"], item["label"]))
    return {"query": q, "suggestions": ranked[:12]}
