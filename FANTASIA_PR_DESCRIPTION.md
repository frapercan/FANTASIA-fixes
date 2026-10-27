# Fix open issues: PostgreSQL 18, silent failures, empty sequences (4.1.2)

## Summary

The December 2025 reference dumps were written by `pg_dump` 18, while the whole stack was pinned to PostgreSQL 16, so `fantasia initialize` could not restore them. The failure was also silent: `initialize` exited with 0, and `run` skipped every batch and finished "successfully" with no results.

This PR:
- migrates to PostgreSQL 18;
- makes those failures explicit;
- fixes the remaining open bugs;
- hardens the HPC scripts.

Everything was reproduced and verified against the real Zenodo dump, on Docker and under Slurm (see Testing).

## Changes

**PostgreSQL 18 (#57, #61, #50)**
- `postgresql-client-18` in the Docker image.
- `pgvector/pgvector:0.8.1-pg18` in Compose and the HPC scripts.
- PG18 data paths (`PGDATA`).
- Versioned `.sif` names, so images cached by 4.1.1 are not reused.
- `pg_restore` errors limited to `SET transaction_timeout` (client 18 against an older server) are reported as warnings, because the data is restored.

**Silent failures (#57, #61)**
- `fantasia initialize` exits with 1 when the restore fails.
- `pg_restore` errors and `run` errors reach the log files. Both previously went to unconfigured loggers.
- `fantasia run` checks the reference database *before* the embedding stage and stops with an explicit error when it is empty.
- Database URLs name the `psycopg2` driver. SQLAlchemy 2.1, which `^2.0.0` resolves to today, maps `postgresql://` to `psycopg` v3, which is not installed, so `initialize` failed on fresh installs.
- Reference downloads are atomic: written to a temporary file and renamed when complete, after checking `Content-Length`.
- `fail_on_task_errors: true` in the packaged configs. With protein-information-system ≥ 3.2 (companion PR), `run` exits with 1 when tasks were discarded or a worker crashed. Older versions ignore the key.

**Other issues**
- **#60:** alignments skip pairs with an empty sequence instead of crashing in parasail, which used to discard the whole batch. The metrics are left empty, post-processing treats them as missing, and the number of skipped pairs is logged once.
- **#55:** `PGCLIENTENCODING=UTF8`, UTF-8 clusters in Compose and the scripts, and the `≥` removed from `constants.yaml`.
- **#54:** `embeddings_url` accepts `file://` URLs and local paths, used in place without copying.
- **#46:** the default `--config`, `constants.yaml` and `go-basic.obo` are found from the installation, not the working directory.
- **#53:** the key may be absent. It stays unset in the packaged config because `initialize` resets the database.
- **#56:** documented sharing a reference database, and `delete_queues` behaviour per protein-information-system version.
- The `proteins` column of `summary.csv` now has a stable order, so identical runs give byte-identical output.

**HPC scripts**
- Each script stops when `initialize` fails.
- Each waits for PostgreSQL and RabbitMQ to accept connections, with a timeout, instead of a fixed `sleep`.
- Cleanup is registered before the services start, and it stops only the job's own services: by PID, or with `pg_ctl stop`. It no longer uses `pkill` on every `rabbitmq-server`, and it no longer runs `rm -rf /tmp/fantasia`.
- Array tasks use per-task service directories. Previously they deleted each other's database on shared storage.

**Documentation**
- Upgrade notes in the changelog.
- PostgreSQL 18 client as a prerequisite of the quick start, which runs `pg_restore` on the host.
- HPC guides aligned with the scripts.
- CLI exit status.
- Troubleshooting entries for an empty reference database, `TaskFailuresError` and empty FASTA records.

## Testing

Reference: `BioData_Dec25_…_Layer0.backup` from Zenodo 17795871 (MD5 `2884b273…`, matches the record). Model: ESM2-650M on CPU, `data_sample/sample.fasta`.

| Scenario | 4.1.1 | This PR |
|---|---|---|
| `initialize` with `pg_restore` 16 (#57) | `unsupported version (1.16)`, empty DB, **exit 0** | exit 1, error and hint in the log |
| `initialize` with client 18 + `file://` (#54) | n/a | restored in ~140 s, dump used in place |
| Client 18 → PostgreSQL 16 server (#57) | exit 1 (`transaction_timeout`) | warning, data complete, same results as PG18 |
| Fresh install (SQLAlchemy 2.1) | `initialize` crashes: `No module named 'psycopg'` | works |
| `run` against an empty DB (#61) | `Empty lookup… Skipping batch`, no output, **exit 0** | exit 1 before embedding |
| Query FASTA with an empty record (#60) | parasail crash; the whole batch lost, exit 0 | results for all sequences; the others identical to a run without the empty record |
| SQL_ASCII cluster (`LC_ALL=C`) (#55) | `UnicodeDecodeError: 'ascii' codec…` | reads `≥` correctly |
| Full `run`, 4.1.1 vs this PR | — | identical predictions and scores |
| Two identical runs | `proteins` order may differ | byte-identical `summary.csv` |
| Slurm, job from `cesga.sh` (Apptainer PG18, shared dump) | old flags: PG18 does not start (`Read-only file system`) | `COMPLETED`, identical results, nothing left running; a failed `initialize` stops the job and cleans up |
| Slurm, job from `greisenwald.sh` | — | `COMPLETED`, identical results, `pg_ctl stop` on exit |

Checks:
- `pytest tests`: 41 passing.
- `flake8`: same 3 pre-existing warnings as the base.
- `shellcheck`: 0 warnings in `deployment/` (6 before).
- Sphinx: `sphinx-build -W` passes with no warnings.

Test setup:
- Slurm: a single-node Slurm 23.11 cluster with Apptainer 1.5.4 and an unprivileged user.
- The jobs are derived from the real scripts. Only the cluster modules, paths and GPU flags were changed, FANTASIA ran from a local install instead of the `.sif`, and RabbitMQ was the node's own broker.

**Not tested:**
- Building the Docker image: the test network blocks `www.postgresql.org`.
- GPU execution.
- The IFB script on its cluster. It received the same changes as `cesga_array.sh`.
- Greifswald scripts with FUSE-mounted `.sif` images. PostgreSQL dies with `Bus error` after `pg_ctl restart`; this behaviour predates this PR and is documented with a workaround (sandbox image).

## After merging

- Build and push `cbbio/fantasia:v4.1.2` to Docker Hub: the HPC scripts reference it.
- Create the GitHub releases for v4.1.1 (#51) and v4.1.2.
- Close #52 and #58 (answered or already fixed).

Closes #46, #50, #53, #54, #55, #56, #57, #60, #61.
