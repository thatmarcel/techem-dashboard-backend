FROM astral/uv:python3.13-bookworm-slim

WORKDIR /app

COPY . .

RUN uv install

ENTRYPOINT ["uv", "run", "uvicorn", '"app.main:app", "--host", "0.0.0.0", "--port", "4000"]
