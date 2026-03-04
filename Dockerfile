FROM python:3.13-slim

RUN pip install uv

WORKDIR /app
# `uv sync --no-dev` tries to install `eel-hole` before we pull in the source.
# To maintain layer caching, we install deps only when uv.lock changes...
# So we split `uv sync` into two steps - install deps, then copy source and install project.
COPY pyproject.toml uv.lock ./
RUN uv sync --no-dev --no-install-project
COPY . .
RUN uv sync --no-dev

# Build the search index and bake it into the image, so we don't have to do this every runtime.
RUN uv run --no-dev python -c "from eel_hole.search import build_search_index; build_search_index()"

CMD uv run --no-dev flask --app eel_hole run --host 0.0.0.0 --port $PORT --reload
