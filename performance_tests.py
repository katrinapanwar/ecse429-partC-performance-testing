"""Performance experiments for the todo manager REST API (ECSE 429, Part C).

After an untimed warm-up, two experiments run for every number of objects N:

  Experiment 1 (batch): create N random todos, change all N, delete all N.
                        Each step is timed; the result is the total and the time per object.
  Experiment 2 (fixed size): preload N todos, then repeat "create one, change one, delete one"
                        so the number of objects stays at N (or N+1) while every operation is timed.
                        The result is the time of ONE operation when N objects are stored.

ResourceSampler records CPU use and free memory during both experiments. Output files:
  performance_results.csv  Experiment 1, one row per operation and N
  fixed_size_results.csv   Experiment 2, one row per operation and N
  resource_samples.csv     every raw CPU / memory sample

Run:  python performance_tests.py            (service must be running on localhost:4567)
      python performance_tests.py --sizes 100 1000
"""
import argparse
import csv
import os
import random
import statistics
import sys
import time

import requests

from random_data import random_change, random_todo
from resource_sampler import ResourceSampler, summarize

BASE_URL = "http://localhost:4567"
JSON_HEADERS = {"Content-Type": "application/json", "Accept": "application/json"}
DEFAULT_SIZES = [100, 200, 500, 1000, 2000, 3000, 5000, 7500, 10000]
FIXED_SIZE_ITERATIONS = 500
SETTLE_SECONDS = 2
WARM_UP_OBJECTS = 300


# ---------- service access ----------

def todo_count(session):
    return len(session.get(f"{BASE_URL}/todos", headers=JSON_HEADERS).json()["todos"])


def require_running_service(session):
    try:
        todo_count(session)
    except requests.exceptions.ConnectionError:
        sys.exit("Todo manager is not running on localhost:4567")


def create_todo(session, rng):
    response = session.post(f"{BASE_URL}/todos", json=random_todo(rng), headers=JSON_HEADERS)
    assert response.status_code == 201, f"create failed: {response.status_code}"
    return response.json()["id"]


def change_todo(session, todo_id, rng):
    response = session.post(f"{BASE_URL}/todos/{todo_id}", json=random_change(rng), headers=JSON_HEADERS)
    assert response.status_code == 200, f"change failed: {response.status_code}"


def delete_todo(session, todo_id):
    response = session.delete(f"{BASE_URL}/todos/{todo_id}")
    assert response.status_code == 200, f"delete failed: {response.status_code}"


# ---------- measuring ----------

def timed_call(function, *arguments):
    started = time.perf_counter()
    result = function(*arguments)
    return time.perf_counter() - started, result


def time_each(action, items):
    return [timed_call(action, item)[0] for item in items]


def percentile(values, fraction):
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(len(ordered) * fraction))]


def result_row(operation, objects, durations, samples):
    total = sum(durations)
    return {
        "operation": operation,
        "objects": objects,
        "total_seconds": round(total, 4),
        "mean_ms": round(1000 * total / len(durations), 3),
        "median_ms": round(1000 * statistics.median(durations), 3),
        "p95_ms": round(1000 * percentile(durations, 0.95), 3),
        "max_ms": round(1000 * max(durations), 3),
        "system_cpu_mean_percent": round(summarize(samples, "system_cpu_percent", statistics.mean) or 0, 2),
        "system_cpu_max_percent": round(summarize(samples, "system_cpu_percent", max) or 0, 2),
        "service_cpu_mean_percent": round(summarize(samples, "service_cpu_percent", statistics.mean) or 0, 2),
        "service_cpu_max_percent": round(summarize(samples, "service_cpu_percent", max) or 0, 2),
        "available_memory_min_mb": round(summarize(samples, "available_memory_mb", min) or 0, 1),
        "available_memory_mean_mb": round(summarize(samples, "available_memory_mb", statistics.mean) or 0, 1),
        "service_memory_max_mb": round(summarize(samples, "service_memory_mb", max) or 0, 1),
    }


def print_row(row):
    print(f"{row['operation']:7} {row['objects']:6} objects  {row['total_seconds']:8.2f} s  "
          f"{row['mean_ms']:7.2f} ms/op  cpu {row['system_cpu_mean_percent']:5.1f}%  "
          f"free memory {row['available_memory_min_mb']:8.0f} MB")


# ---------- experiment 1: batch ----------

def run_batch_phase(sampler, operation, objects, action, items):
    sampler.start(f"batch-{operation}-{objects}")
    durations = time_each(action, items)
    samples = sampler.stop()
    row = result_row(operation, objects, durations, samples)
    print_row(row)
    time.sleep(SETTLE_SECONDS)
    return row, samples


def run_batch_experiment(session, sampler, objects, rng):
    ids = []
    rows, all_samples = [], []
    phases = [
        ("create", lambda _: ids.append(create_todo(session, rng)), lambda: range(objects)),
        ("change", lambda todo_id: change_todo(session, todo_id, rng), lambda: list(ids)),
        ("delete", lambda todo_id: delete_todo(session, todo_id), lambda: list(ids)),
    ]
    for operation, action, items in phases:
        row, samples = run_batch_phase(sampler, operation, objects, action, items())
        rows.append(row)
        all_samples += samples
    return rows, all_samples


# ---------- experiment 2: fixed size ----------

def grow_pool(session, pool, size, rng):
    # untimed: bring the number of stored todos up to the wanted size
    while len(pool) < size:
        pool.append(create_todo(session, rng))


def measure_at_fixed_size(session, sampler, pool, size, rng):
    # one create, one change and one delete per round; the delete replaces a random stored todo,
    # so the number of objects stays at `size` (or size + 1) during the whole measurement
    durations = {"create": [], "change": [], "delete": []}
    sampler.start(f"fixed-{size}")
    for _ in range(FIXED_SIZE_ITERATIONS):
        seconds, new_id = timed_call(create_todo, session, rng)
        durations["create"].append(seconds)
        seconds, _ = timed_call(change_todo, session, rng.choice(pool), rng)
        durations["change"].append(seconds)
        victim_index = rng.randrange(len(pool))
        seconds, _ = timed_call(delete_todo, session, pool[victim_index])
        durations["delete"].append(seconds)
        pool[victim_index] = new_id
    return durations, sampler.stop()


def run_fixed_size_experiment(session, sampler, sizes, rng):
    pool, rows, all_samples = [], [], []
    for size in sizes:
        grow_pool(session, pool, size, rng)
        time.sleep(SETTLE_SECONDS)
        durations, samples = measure_at_fixed_size(session, sampler, pool, size, rng)
        for operation, operation_durations in durations.items():
            row = result_row(operation, size, operation_durations, samples)
            print_row(row)
            rows.append(row)
        all_samples += samples
    for todo_id in pool:
        delete_todo(session, todo_id)
    return rows, all_samples


# ---------- start-up and output ----------

def warm_up(session, rng):
    # untimed run so start-up effects (JIT compilation, connections) do not distort the smallest sizes
    ids = [create_todo(session, rng) for _ in range(WARM_UP_OBJECTS)]
    for todo_id in ids:
        change_todo(session, todo_id, rng)
    for todo_id in ids:
        delete_todo(session, todo_id)


def write_csv(path, rows):
    with open(path, "w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def parse_arguments():
    parser = argparse.ArgumentParser(description="Performance experiments for the todo manager API")
    parser.add_argument("--sizes", type=int, nargs="+", default=DEFAULT_SIZES, help="numbers of objects")
    parser.add_argument("--seed", type=int, default=429, help="seed of the random data")
    parser.add_argument("--output-dir", default="results")
    return parser.parse_args()


def main():
    arguments = parse_arguments()
    os.makedirs(arguments.output_dir, exist_ok=True)
    rng = random.Random(arguments.seed)
    session = requests.Session()
    require_running_service(session)

    sampler = ResourceSampler()
    if sampler.service is None:
        print("Warning: todo manager process not found, only system-wide numbers are recorded")
    initial_count = todo_count(session)
    warm_up(session, rng)

    print("--- Experiment 1: batch of N operations ---")
    batch_rows, batch_samples = [], []
    for objects in arguments.sizes:
        rows, samples = run_batch_experiment(session, sampler, objects, rng)
        batch_rows += rows
        batch_samples += samples

    print("--- Experiment 2: one operation at a fixed number of stored objects ---")
    fixed_rows, fixed_samples = run_fixed_size_experiment(session, sampler, sorted(arguments.sizes), rng)

    assert todo_count(session) == initial_count, "system was not restored to its initial state"
    write_csv(os.path.join(arguments.output_dir, "performance_results.csv"), batch_rows)
    write_csv(os.path.join(arguments.output_dir, "fixed_size_results.csv"), fixed_rows)
    write_csv(os.path.join(arguments.output_dir, "resource_samples.csv"), batch_samples + fixed_samples)
    print(f"Done. Results written to {arguments.output_dir}/")


if __name__ == "__main__":
    main()
