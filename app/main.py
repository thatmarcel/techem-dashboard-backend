import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from app.api import (
    routes_challenges,
    routes_chart,
    routes_chat,
    routes_import,
    routes_navigation,
    routes_report,
    routes_search,
    routes_tips,
)
from app.db import get_connection, init_db


logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

# This file wires the API together only. Business logic stays in services/.
app = FastAPI(title="Heating Energy Analysis Demo API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost",
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup() -> None:
    # Create the SQLite schema on startup; importing CSV data is still explicit.
    connection = get_connection()
    try:
        init_db(connection)
    finally:
        connection.close()


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/", include_in_schema=False)
def root():
    # There is no dedicated frontend in this repository yet.
    # Redirect browser traffic to the interactive API docs instead of showing 404.
    return RedirectResponse(url="/docs", status_code=307)


app.include_router(routes_import.router)
app.include_router(routes_navigation.router)
app.include_router(routes_search.router)
app.include_router(routes_chart.router)
app.include_router(routes_report.router)
app.include_router(routes_chat.router)
app.include_router(routes_tips.router)
app.include_router(routes_challenges.router)
