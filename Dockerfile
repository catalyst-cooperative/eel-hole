FROM python:3.13-slim

RUN pip install uv

WORKDIR /app

COPY pyproject.toml uv.lock ./
COPY pudl_parquet_datapackage.json ./
RUN uv sync --no-dev
COPY . .

CMD uv run --no-dev flask --app eel_hole run --host 0.0.0.0 --port $PORT --reload
