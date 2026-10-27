# Surface task failures instead of finishing silently (3.2.0)

## Summary

`QueueTaskInitializer` hid several kinds of failure. Callers such as FANTASIA finished with exit code 0 and missing or incomplete results. This PR:
- makes those failures visible;
- bounds retries;
- lets callers opt in to failing the run;
- fixes two shared-infrastructure problems: `delete_queues` deleting every queue on the broker, and encoding errors on `SQL_ASCII` clusters.

Each change is a separate commit with its own tests, and every commit passes the test suite and `flake8` on its own.

## Changes

1. **`start()` raises worker-start and post-processing errors** (`tasks/queue.py`)
   - `start_workers()` caught every exception and returned normally. A worker that could not be started (fork failure, or pickling errors under `spawn`/`forkserver`) left `start()` reporting success.
   - `post_processing()` errors were only logged.
   - Both are now raised. If the pipeline already failed, a post-processing error is logged and the original error propagates.

2. **Failed tasks are retried once, after a delay, then discarded** (`tasks/queue.py`)
   - `callback()` requeued failures forever.
   - With `GPUTaskInitializer` (a `basic_get` loop), a permanently failing task is fetched again immediately, so the pipeline never finished.
   - A failed message is now requeued once, after `task_retry_delay` seconds (default 5), and discarded if it fails again.

3. **Discarded tasks and crashed workers are counted; failing the run is opt-in** (`tasks/queue.py`, `tasks/gpu.py`, `config/config.yaml`)
   - **What is counted:** a `multiprocessing.Value` shared with the workers counts inserting-queue failures, computing-queue failures after the retry, and worker processes that exit with a non-zero code (e.g. OOM-killed).
   - **At the end of `start()`:** the count is logged as an error. This happens after post-processing, so partial results are still written.
   - **Opting in:** with `fail_on_task_errors: True`, `start()` raises `TaskFailuresError` instead. The default is `False`, so `pis` keeps running its stages past a bad record. FANTASIA opts in.
   - **`ValueError` skips:** a `ValueError` from `process()` remains a "skip", but skips are now counted and reported.
   - **Counters:** they are reset on every `start()`.

4. **`delete_queues` and queue monitoring are restricted to the task's own queues** (`tasks/queue.py`)
   - `delete_queues` used to delete every queue on the broker, including other users' pending work.
   - `delete_task_queues()` removes only `<task>_computing`, `<task>_inserting` and `<task>_computing_<model>` in the connection's vhost.
   - `monitor_queues()` uses the same filter instead of a substring match.
   - `delete_all_queues()` is unchanged.

5. **UTF-8 client encoding** (`sql/base/database_manager.py`)
   - `client_encoding=utf8` is passed to the engine, so `SQL_ASCII` clusters (created under `LC_ALL=C`) no longer fail on non-ASCII text (CBBIO/FANTASIA#55).

6. **Version 3.2.0**, CHANGELOG entry (including known limitations), and an "Error handling" section in the `tasks.queue` module docs.

## Compatibility

- **What changes for existing callers:**
  - errors from `start_workers()` and `post_processing()` are now raised;
  - failed tasks are retried once instead of indefinitely. During a long outage of a remote service (UniProt, RCSB), affected tasks are discarded and reported instead of retried until the service returns.
- `fail_on_task_errors` defaults to `False`, so discarded tasks do not stop existing pipelines.
- `delete_all_queues()` and the abstract API (`enqueue`, `process`, `store_entry`, `post_processing`) are unchanged.
- FANTASIA requires `protein-information-system = "^3.1.0"` and picks up 3.2.0 without changes.

## Testing

**Unit tests:** `tests/tasks/test_queue_task_initializer.py` and `tests/sql/test_database_manager.py` add 19 tests. They pass on Python 3.10 and 3.12 and need no RabbitMQ or database. They include:
- the real `start_workers` failing to start a process;
- the monitor ignoring other tasks' queues;
- the counter shared with forked processes.

**Against a real RabbitMQ broker:**
- A permanently failing task: before, it looped indefinitely; now it is attempted twice and removed.
- A foreign queue with a pending message: before, a FANTASIA run with `delete_queues: true` deleted it; now it survives, and only FANTASIA's queues are reset.

**Against a real `SQL_ASCII` PostgreSQL 18 cluster:** before, writing "≥" raised `UnicodeEncodeError`; now "≥ — α" is written and read back correctly.

**End to end with FANTASIA and the Zenodo reference dump** (`BioData_Dec25_…_Layer0`, ESM2 on CPU):

| Scenario | PIS 3.1.2 | This PR |
|---|---|---|
| Task fails in the inserter (FANTASIA 4.1.1, empty FASTA record), default config | exit 0, batch lost silently | exit 0, error logged with the failure count |
| Same, `fail_on_task_errors: true` | exit 0 | exit 1, `TaskFailuresError` |
| Post-processing fails | exit 0, incomplete `summary.csv` | exit 1 |
| Normal run / run with an empty record (fixed FANTASIA) | exit 0 | exit 0, identical results |

**Other checks:** Sphinx docs build with the same single pre-existing warning (in `sequence_embedding.py`).

## Known limitations (not changed here)

- `Structure3DiManager.store_entry()` catches and logs per-record errors, so they are not counted.
- If every computing worker crashes, the computing queue never drains, and the run waits for the database worker indefinitely.
- `ensure_pgvector_extension()` only logs when the extension cannot be created.
- The CHANGELOG has no entries for 3.0.x and 3.1.x.
