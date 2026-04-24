FROM astral/uv:python3.13-trixie

WORKDIR /app

COPY . .

RUN uv sync

RUN curl -fsSL "https://sichere-datei.lol/demo.db" -o demo.db

ENTRYPOINT ["uv", "run", "--env-file", "/app/.env", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
