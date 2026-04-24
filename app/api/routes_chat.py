from fastapi import APIRouter, Depends, HTTPException

from app.db import get_db
from app.schemas.requests import ChatRequest
from app.services.chat_service import answer_chat


router = APIRouter(prefix="/api", tags=["chat"])


@router.post("/chat")
def chat(request: ChatRequest, connection=Depends(get_db)):
    try:
        return answer_chat(connection, request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
