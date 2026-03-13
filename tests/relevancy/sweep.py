import sys
import yaml
from pathlib import Path
from math import sqrt


def terrible_vector(old_center, new_center, delta):
    vector = [(xi_new - xi_old) for (xi_old, xi_new) in zip(old_center, new_center)]
    vector_len = sqrt(sum(xi * xi for xi in vector))
    return [delta * xi / vector_len for xi in vector]


if __name__ == "__main__":
    experiment = Path(sys.argv[-1])
    with open(experiment) as f:
        config = yaml.safe_load(f)
    with open(f"sweep.{experiment.stem}.out") as f:
        results = f.readlines()
    best_score = 0.0
    best_params = []
    for r in results:
        score, _, params = r.strip().partition(",")
        # print(f"\t{score}\t{params}")
        score = float(score)
        if score > best_score:
            best_score = score
            best_params = []
        if score >= best_score:
            best_params.append(params)
    best_params = sorted(best_params)
    print(f"MAP to beat: {config['beat']['map']}")
    print(
        f"Best MAP this round: {best_score:3f} ({len(best_params)} of {len(results)})"
    )
    input("Hit enter to configure the next experiment, or ^C to quit")
    print("\n".join(f"{i: 3d}: {p}" for i, p in enumerate(best_params)))
    selected = int(input("Select new center: "))
    selected_params = [float(x) for x in best_params[selected].split(",")]
    delta = float(input("Delta: "))
    # inc = terrible_vector(config["beat"]["params"], selected_params, delta)
    inc = [delta * xi for xi in selected_params]
    print(f"Next increment: [{', '.join(f'{di:3f}' for di in inc)}]")
    next_file = input("Enter next experiment filename: ")
    next_config = {
        "variant": config["variant"],
        "beat": {"map": best_score, "params": best_params[selected]},
        "sweep": [
            {f"x{i}": [ci - di, ci, ci + di]}
            for (i, (ci, di)) in enumerate(zip(selected_params, inc))
        ],
    }
    with open(next_file, "w") as f:
        yaml.safe_dump(next_config, f)
