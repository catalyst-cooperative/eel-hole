#!/bin/bash

START=$1
if [ -z "$START" ]; then START=1; fi

set -ex

for k in 0 1 2 3 4 5 6 7 8 9; do
    i=$((START+k))
    echo "Trial $i"
    input_step="tests/relevancy/step$((i-1)).yaml"
    next_stem="step$i"
    echo "$next_stem" | uv run tests/relevancy/sweep.py $input_step
    time uv run pytest tests/relevancy/test_relevancy.py::test_sweep_default --experiment tests/relevancy/${next_stem}.yaml
done
