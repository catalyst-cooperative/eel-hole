import sys
import yaml
from pathlib import Path
from math import sqrt
import random


def terrible_vector_len(old_center, new_center):
    vector = [
        (xi_new - float(xi_old)) for (xi_old, xi_new) in zip(old_center, new_center)
    ]
    return sqrt(sum(xi * xi for xi in vector)), vector


if __name__ == "__main__":
    experiment = Path(sys.argv[-1])
    with open(experiment) as f:
        config = yaml.safe_load(f)
    results_file = Path(f"sweep.{experiment.stem}.out")
    best_score = config["beat"]["map"]
    best_params = [",".join(str(p) for p in config["beat"]["params"])]
    results = []
    if results_file.exists():
        with open(results_file) as f:
            results = f.readlines()
        for r in results:
            score, _, params = r.strip().partition(",")
            score = float(score)
            if score > best_score:
                best_score = score
                best_params = []
            if score >= best_score:
                best_params.append(params)
        best_params = sorted(best_params)
    print(f"MAP to beat: {config['beat']['map']}")
    print(f"From params: {config['beat']['params']}")
    print(
        f"Best MAP this round: {best_score:3f} ({len(best_params)} of {len(results)})"
    )
    best_params_arr = [
        [float(x) for x in selected.split(",")] for selected in best_params
    ]
    n = len(best_params_arr)
    selected_params = best_params_arr[0]
    if n > 1:
        selected_params = [sum(axis) / n for axis in zip(*best_params_arr)]
    delta, vector = terrible_vector_len(config["beat"]["params"], selected_params)
    if not results:
        # seed increment with appropriate scale for each parameter
        inc = [xi * 0.2 for xi in selected_params]
    elif delta == 0:
        print("No improvements found. You're done!")
        sys.exit(0)
    else:
        inc = [di * 0.7 for di in vector]
    print(f"Next center: [{', '.join(f'{di:3f}' for di in selected_params)}]")
    print(f"Delta: {delta}")
    print(f"Next increment: [{', '.join(f'{di:3f}' for di in inc)}]")
    next_stem = input(f"Enter next experiment stem (like {experiment.stem}): ")
    next_config = {
        "variant": config["variant"],
        "beat": {"map": best_score, "params": random.choice(best_params_arr)},
        "center": selected_params,
        "sweep": [
            {f"x{i}": [ci - di, ci, ci + di]} if di != 0 else {f"x{i}": [ci]}
            for (i, (ci, di)) in enumerate(zip(selected_params, inc))
        ],
    }
    with open(sys.argv[-1].replace(experiment.stem, next_stem), "w") as f:
        yaml.safe_dump(next_config, f)
    print("\nReady to run next experiment")
