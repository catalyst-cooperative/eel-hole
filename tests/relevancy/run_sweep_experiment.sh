#!/bin/bash

STEPFILE=$1
if [ -z "$STEPFILE" ]; then
    echo "Usage: $0 initial_stepfile.yaml [starting iteration, default 1]"
    exit 1
fi
shift

STEP_PATH=${STEPFILE%/*}
STEP_LEAF=${STEPFILE##*/}
next_stem=${STEP_LEAF%.yaml}
PREFIX=${next_stem%[0-9]*}

START=$1
if [ -z "$START" ]; then
    START=1;
fi

set -e

for k in 0 1 2 3 4 5 6 7 8 9; do
    i=$((START+k))
    echo "Trial $i"
    input_step="${STEP_PATH}/${next_stem}.yaml"
    next_stem="${PREFIX}$i"
    set -x
    echo "$next_stem" | uv run tests/relevancy/sweep.py $input_step
    time uv run pytest tests/relevancy/test_relevancy.py::test_sweep --experiment ${STEP_PATH}/${next_stem}.yaml
    set +x
done
