#!/bin/sh
set -eux

uv run --no-dev flask --app eel_hole db upgrade
uv run --no-dev flask --app eel_hole run --host 0.0.0.0 --port "${PORT}"
