# Surface task failures instead of finishing silently (3.2.0)

## Summary

`QueueTaskInitializer` hid several kinds of failure, so callers such as FANTASIA finished "successfully" (exit code 0) with missing or incomplete results. This PR makes those failures visible, bounds retries, and fixes two shared-infrastructure problems: `delete_queues` deleting every queue on the broker, and encoding errors on `SQL_ASCII` clusters.

Each change is a separate commit with its own tests.

## Changes

1. **Post-processing errors are raised** (`tasks/queue.py`)
   `post_processing()` ran in a `finally` block that only logged exceptions. It is now raised when the pipeline itself succeeded. If the pipeline already failed, the post-processing error is logged and the original error propagates, so the root cause is never masked.

2. **Failed computing tasks are retried once, then discarded** (`tasks/queue.py`)
   `callback()` nacked failures with `requeue=True` unconditionally. With `GPUTaskInitializer`, which fetches with `basic_get` until the queue is empty, a task that always fails is fetched again immediately, so the pipeline never finished. A failed message is now requeued once and discarded if it fails again (`method.redelivered`).

3. **Discarded tasks fail the pipeline** (`tasks/queue.py`, `config/config.yaml`)
   Discarded tasks are counted in a `multiprocessing.Value` shared with the worker processes. These are inserting-queue failures, and computing-queue failures after the retry. After post-processing, so partial results are still written, `start()` raises `TaskFailuresError`. The new option `fail_on_task_errors: False` only logs a warning instead. `ValueError` in `process()` is still an intentional skip.

4. **`delete_queues` deletes only the task's own queues** (`tasks/queue.py`, `config/config.yaml`)
   It previously called `delete_all_queues()`, which removes every queue on the broker, including other users' queues and their pending messages. The new `delete_task_queues()` removes only `<task>_computing`, `<task>_inserting` and `<task>_computing_<model>` in the connection's vhost. `delete_all_queues()` is unchanged for existing callers.

5. **UTF-8 client encoding** (`sql/base/database_manager.py`)
   A cluster created under `LC_ALL=C` is `SQL_ASCII`, and psycopg2 then fails on any non-ASCII text. The engine now passes `client_encoding=utf8` (CBBIO/FANTASIA#55).

6. Version 3.2.0 and CHANGELOG entry.

## Compatibility

- **Behaviour change (why 3.2.0, not 3.1.3):** runs that lost tasks or failed in post-processing now raise instead of returning normally. Set `fail_on_task_errors: False` to keep the old exit behaviour for discarded tasks. Post-processing errors are always raised.
- `delete_all_queues()` keeps its behaviour. Only the `delete_queues` startup path changes.
- No changes to subclasses' abstract API (`enqueue`, `process`, `store_entry`, `post_processing`).
- FANTASIA requires `protein-information-system = "^3.1.0"`, so it picks up 3.2.0 without changes.

## Testing

- New unit tests (`tests/tasks/test_queue_task_initializer.py`, `tests/sql/test_database_manager.py`): 13 tests, passing on Python 3.10 and 3.12, with no RabbitMQ or database needed.
- Against a real RabbitMQ broker:
  - a permanently failing task: before, it looped indefinitely; now it is attempted twice and removed;
  - a foreign queue with a pending message: before, it was deleted by a FANTASIA run with `delete_queues: true`; now it survives, and only FANTASIA's queues are reset.
- Against a real `SQL_ASCII` PostgreSQL 18 cluster: before, writing "≥" raised `UnicodeEncodeError`; now "≥ — α" is written and read back correctly.
- End to end with FANTASIA and the Zenodo reference dump (`BioData_Dec25_…_Layer0`, ESM2 on CPU):

| Scenario | PIS 3.1.2 | This PR |
|---|---|---|
| Task fails in the inserter (FANTASIA 4.1.1, empty FASTA record) | exit 0, batch lost | exit 1, `TaskFailuresError` |
| Post-processing fails | exit 0, incomplete `summary.csv` | exit 1 |
| Normal run / run with an empty record (fixed FANTASIA) | exit 0 | exit 0, `summary.csv` byte-identical |

## Not included

- `ensure_pgvector_extension()` still only logs when the extension cannot be created.
- `QueueTaskInitializer.start_workers()` still logs exceptions instead of raising them.
