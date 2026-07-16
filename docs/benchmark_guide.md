# AAiOS Performance Benchmarking Guide
## Version 5.3.2 — Performance Benchmarking

This guide outlines the performance measurement suite used to audit AAiOS boot latencies, memory consumption, database throughput, and model response times.

---

### 1. Benchmark Execution

To run the benchmarking suite and generate a report, execute:
```powershell
aaios benchmark
```

This runs a sequence of execution checks and saves the results to `reports/benchmark_report.json`.

---

### 2. Measured Metrics

*   **Cold Boot Time**: Measurement of raw module import overhead before any services start. Ideal: `< 200 ms`.
*   **Warm Boot Time**: Speed of starting event loops, connection pools, and loading local configurations. Ideal: `< 50 ms`.
*   **Database Write Latency**: Performs 100 fast SQL write/read cycles to check sqlite file transaction speed. Ideal: `< 3.0 ms` per query.
*   **Memory Retrieval Latency**: Retrieves mock records to calculate vector matching overhead. Ideal: `< 15.0 ms`.
*   **Resource Footprints**: Memory RSS utilization (in MB) and active CPU usage (in %).

---

### 3. Tuning & Optimization Strategies

If benchmarks indicate latency warnings:
1.  **High Database Write Latency**: Set SQLite journal mode to `WAL` in settings, or check that the workspace database directory is mounted on SSD storage.
2.  **High Memory Footprint**: Use `aaios cleanup` to release cached vectors, or configure maximum size thresholds in `config/config.yaml`.
3.  **Startup Latency**: Clean Python pyc compilation files, or disable unused provider loaders in the model router config.
