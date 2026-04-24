from fastapi import APIRouter, Depends, HTTPException, Query

from app.db import get_db
from app.services.report_service import build_report


router = APIRouter(prefix="/api", tags=["report"])


@router.get("/report")
def report(
    scope_type: str = Query("total"),
    scope_id: str | None = Query(None),
    period: str = Query("month"),
    offset: int = Query(0),
    analysis_provider: str | None = Query(None),
    connection=Depends(get_db),
):
    try:
        return build_report(connection, scope_type, scope_id, period, offset, analysis_provider)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
