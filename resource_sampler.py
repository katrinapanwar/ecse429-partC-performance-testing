"""Samples CPU and free memory in a background thread while an experiment runs.

Uses psutil (open source). Each sample records:
  - system CPU use in percent (all cores)
  - CPU use of the todo manager process in percent of the whole machine
  - available (free) memory of the machine in MB
  - memory used by the todo manager process in MB
"""
import threading
import time

import psutil

SERVICE_MARKER = "runTodoManagerRestAPI"
BYTES_PER_MB = 1024 * 1024


def find_service_process():
    for process in psutil.process_iter(["name", "cmdline"]):
        command_line = " ".join(process.info["cmdline"] or [])
        is_java = "java" in (process.info["name"] or "").lower()
        if is_java and SERVICE_MARKER in command_line:
            return process
    return None


class ResourceSampler:
    def __init__(self, interval_seconds=0.2):
        self.interval = interval_seconds
        self.service = find_service_process()
        self.cpu_count = psutil.cpu_count()
        self.samples = []
        self._label = ""
        self._stop_event = threading.Event()
        self._thread = None

    def start(self, label):
        self._label = label
        self.samples = []
        self._stop_event.clear()
        psutil.cpu_percent(interval=None)  # first call only primes the counter
        if self.service:
            self.service.cpu_percent(interval=None)
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop_event.set()
        self._thread.join()
        self.samples.append(self._take_sample())  # covers the tail, so short phases still get a sample
        return list(self.samples)

    def _run(self):
        while not self._stop_event.wait(self.interval):
            self.samples.append(self._take_sample())

    def _take_sample(self):
        sample = {
            "time": time.time(),
            "label": self._label,
            "system_cpu_percent": psutil.cpu_percent(interval=None),
            "available_memory_mb": psutil.virtual_memory().available / BYTES_PER_MB,
            "service_cpu_percent": None,
            "service_memory_mb": None,
        }
        if self.service:
            sample["service_cpu_percent"] = self.service.cpu_percent(interval=None) / self.cpu_count
            sample["service_memory_mb"] = self.service.memory_info().rss / BYTES_PER_MB
        return sample


def summarize(samples, key, reducer):
    values = [s[key] for s in samples if s[key] is not None]
    return reducer(values) if values else None
