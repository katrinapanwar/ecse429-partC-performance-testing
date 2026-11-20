"""Draws the Part C charts from the CSV files written by performance_tests.py.

Experiment 1 (batch)       results/performance_results.csv
    batch_create.png, batch_change.png, batch_delete.png: transaction time, CPU use and memory
    versus the number of objects, one picture per operation; batch_comparison.png: time per object.
Experiment 2 (fixed size)  results/fixed_size_results.csv
    fixed_size.png: time of one operation, CPU use and memory versus the number of stored objects.

Run:  python make_charts.py            (writes PNG files into results/charts/)
"""
import csv
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

BATCH_RESULTS = os.path.join("results", "performance_results.csv")
FIXED_RESULTS = os.path.join("results", "fixed_size_results.csv")
CHART_DIR = os.path.join("results", "charts")
OPERATIONS = ["create", "change", "delete"]
COLORS = {"create": "#1f77b4", "change": "#ff7f0e", "delete": "#2ca02c"}


def read_rows(path, operation):
    with open(path) as handle:
        rows = [r for r in csv.DictReader(handle) if r["operation"] == operation]
    return sorted(rows, key=lambda r: int(r["objects"]))


def column(rows, name):
    return [float(r[name]) for r in rows]


def style_axis(axis, title, y_label):
    axis.set_title(title, fontsize=10)
    axis.set_xlabel("Number of objects")
    axis.set_ylabel(y_label)
    axis.set_xscale("log")
    axis.grid(True, alpha=0.3)


def legend_below(axis, twin_axis=None):
    handles, labels = axis.get_legend_handles_labels()
    if twin_axis is not None:
        twin_handles, twin_labels = twin_axis.get_legend_handles_labels()
        handles, labels = handles + twin_handles, labels + twin_labels
    axis.legend(handles, labels, loc="upper center", bbox_to_anchor=(0.5, -0.22),
                ncol=2, fontsize=8, frameon=False)


def draw_cpu_panel(axis, rows, title):
    objects = column(rows, "objects")
    axis.plot(objects, column(rows, "system_cpu_mean_percent"), "o-", label="System CPU (mean)")
    axis.plot(objects, column(rows, "service_cpu_mean_percent"), "s-", label="Todo manager CPU (mean)")
    style_axis(axis, title, "CPU use (% of the machine)")
    axis.set_ylim(0, 100)
    legend_below(axis)


def draw_memory_panel(axis, rows, title):
    objects = column(rows, "objects")
    axis.plot(objects, column(rows, "available_memory_min_mb"), "o-", label="Available memory (minimum)")
    style_axis(axis, title, "Available memory (MB)")
    service_axis = axis.twinx()
    service_axis.plot(objects, column(rows, "service_memory_max_mb"), "s--", color="gray", label="Todo manager memory (max)")
    service_axis.set_ylabel("Todo manager memory (MB)")
    service_axis.set_ylim(0, 1.2 * max(column(rows, "service_memory_max_mb")))  # from zero, so small changes are not exaggerated
    legend_below(axis, service_axis)


def draw_batch_operation(operation):
    rows = read_rows(BATCH_RESULTS, operation)
    objects = column(rows, "objects")
    figure, axes = plt.subplots(1, 3, figsize=(15, 4.6))

    axes[0].plot(objects, column(rows, "total_seconds"), "o-", color=COLORS[operation], label="Total time")
    style_axis(axes[0], f"{operation.capitalize()}: transaction time", "Total time (s)")
    per_object_axis = axes[0].twinx()
    per_object_axis.plot(objects, column(rows, "mean_ms"), "s--", color="gray", label="Mean per object")
    per_object_axis.plot(objects, column(rows, "median_ms"), "^:", color="black", label="Median per object")
    per_object_axis.set_ylabel("Time per object (ms)")
    legend_below(axes[0], per_object_axis)

    draw_cpu_panel(axes[1], rows, f"{operation.capitalize()}: CPU use")
    draw_memory_panel(axes[2], rows, f"{operation.capitalize()}: memory")
    figure.tight_layout()
    figure.savefig(os.path.join(CHART_DIR, f"batch_{operation}.png"), dpi=150)
    plt.close(figure)


def draw_batch_comparison():
    figure, axes = plt.subplots(1, 2, figsize=(11, 4))
    for axis, column_name, title in [(axes[0], "mean_ms", "Mean time per object"),
                                     (axes[1], "median_ms", "Median time per object")]:
        for operation in OPERATIONS:
            rows = read_rows(BATCH_RESULTS, operation)
            axis.plot(column(rows, "objects"), column(rows, column_name), "o-", color=COLORS[operation], label=operation)
        style_axis(axis, title, "Time per object (ms)")
        axis.legend()
    figure.tight_layout()
    figure.savefig(os.path.join(CHART_DIR, "batch_comparison.png"), dpi=150)
    plt.close(figure)


def draw_fixed_size():
    figure, axes = plt.subplots(1, 3, figsize=(15, 4.6))
    for operation in OPERATIONS:
        rows = read_rows(FIXED_RESULTS, operation)
        axes[0].plot(column(rows, "objects"), column(rows, "median_ms"), "o-", color=COLORS[operation], label=f"{operation} (median)")
        axes[0].plot(column(rows, "objects"), column(rows, "p95_ms"), ":", color=COLORS[operation], label=f"{operation} (95th percentile)")
    style_axis(axes[0], "Time of one operation", "Time of one operation (ms)")
    legend_below(axes[0])

    rows = read_rows(FIXED_RESULTS, "create")  # CPU and memory were measured once per size, for all three operations together
    draw_cpu_panel(axes[1], rows, "CPU use (create, change and delete together)")
    draw_memory_panel(axes[2], rows, "Memory")
    figure.tight_layout()
    figure.savefig(os.path.join(CHART_DIR, "fixed_size.png"), dpi=150)
    plt.close(figure)


def main():
    for path in (BATCH_RESULTS, FIXED_RESULTS):
        if not os.path.exists(path):
            sys.exit(f"Run performance_tests.py first: {path} not found")
    os.makedirs(CHART_DIR, exist_ok=True)
    for operation in OPERATIONS:
        draw_batch_operation(operation)
    draw_batch_comparison()
    draw_fixed_size()
    print(f"Charts written to {CHART_DIR}/")


if __name__ == "__main__":
    main()
