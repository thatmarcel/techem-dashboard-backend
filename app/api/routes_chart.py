from fastapi import APIRouter, Depends, HTTPException, Query

from app.db import get_db
from app.services.aggregation_service import chart_payload


router = APIRouter(prefix="/api", tags=["chart"])


@router.get("/chart")
def chart(
    scope_type: str = Query("total"),
    scope_id: str | None = Query(None),
    period: str = Query("month"),
    offset: int = Query(0),
    include_weather: bool = Query(True),
    analysis_provider: str | None = Query(None),
    connection=Depends(get_db),
):
    try:
        return chart_payload(connection, scope_type, scope_id, period, offset, include_weather, analysis_provider)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
