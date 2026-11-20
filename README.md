# Part C: Performance tests for the todo manager REST API

Measures how long create, change and delete take as the number of todos grows,
and records CPU use and free memory while each experiment runs.

## Experiments
1. **Batch:** for each number of objects N, create N random todos, change all N, delete all N.
   Each step is timed (total time and time per object).
2. **Fixed size:** preload N todos, then repeat "create one, change one, delete one" so the number
   of stored objects stays at N. Each operation is timed, which gives the time of ONE operation
   when N objects are stored.

Both run after an untimed warm-up. Default sizes: 100, 200, 500, 1000, 2000, 3000, 5000, 7500, 10000.

## Files
- `performance_tests.py`  runs both experiments and writes the CSV files
- `random_data.py`        random todo data
- `resource_sampler.py`   samples CPU and free memory (psutil) in the background
- `make_charts.py`        draws the charts from the CSV files
- `results/`              created by the scripts:
  - `performance_results.csv`  experiment 1
  - `fixed_size_results.csv`   experiment 2
  - `resource_samples.csv`     raw CPU / memory samples
  - `charts/`                  batch_create/change/delete.png, batch_comparison.png, fixed_size.png

## Run
1. Start the service: `java -jar runTodoManagerRestAPI-1.5.5.jar`
2. `pip install -r requirements.txt`
3. `python performance_tests.py`  (or `python performance_tests.py --sizes 100 1000 5000`)
4. `python make_charts.py`

Restart the service before a full run so memory starts from the same point.
Everything the experiments create is deleted again, so the system ends in its initial state.
