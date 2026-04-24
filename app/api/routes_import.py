from fastapi import APIRouter, Depends, HTTPException

from app.db import get_db
from app.schemas.requests import ImportDirectoryRequest
from app.services.csv_loader import import_csv_directory


router = APIRouter(prefix="/api/import", tags=["import"])


@router.post("/csv-directory")
def import_directory(request: ImportDirectoryRequest, connection=Depends(get_db)):
    try:
        return import_csv_directory(connection, request.directory_path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
