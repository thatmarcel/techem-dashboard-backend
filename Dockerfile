FROM astral/uv:python3.13-bookworm-slim

WORKDIR /app

COPY . .

ENTRYPOINT ["uv", "run", "uvicorn", '"app.main:app"]
