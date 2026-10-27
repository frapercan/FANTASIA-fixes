# Changelog

## 4.1.2 (unreleased)

Fixes

- Migrated the stack to PostgreSQL 18, required by the December 2025 reference
  dumps (written by `pg_dump` 18): `postgresql-client-18` in the Docker image,
  `pgvector/pgvector:0.8.1-pg18` in Compose and the HPC scripts, PG18 data
  paths, and documentation (#57, #61, #50).
- `fantasia initialize` now exits with a non-zero status when the restore
  fails, and the deployment scripts stop when it does (#57, #61).
- `pg_restore` errors limited to `SET transaction_timeout` (client 18 against
  an older server) are reported as warnings instead of failures (#57).
- `fantasia run` stops with an explicit error when the reference database has
  no embeddings, instead of skipping every batch and finishing without
  results (#61).
- The final-layer reference URL is enabled by default in `config.yaml`, as its
  comment already stated (#53).
- Alignment metrics skip pairs with an empty sequence instead of crashing in
  parasail; the metrics are reported as missing (#60).
- PostgreSQL clients use UTF-8 (`PGCLIENTENCODING=UTF8`) and deployment scripts
  create UTF-8 clusters, fixing decoding errors under `LC_ALL=C`; removed the
  non-ASCII character from `constants.yaml` (#55).
- `embeddings_url` accepts `file://` URLs and local paths, used in place
  without copying (#54).
- The default `--config` and `go-basic.obo` are resolved from the installation
  directory, not the working directory, so the image no longer depends on
  `WORKDIR /app` (#46).
- Documented that `delete_queues: true` deletes every queue on the broker and
  how to share one reference database (#56).

Documentation

- Reorganized user documentation around Getting started, User guide,
  Deployment, Reference, Explanation, Benchmarks, Performance,
  Troubleshooting, and Development.
- Added an executable first-run path, configuration/output references,
  documentation smoke checks, and a maintainer audit.
- Corrected Python/Sphinx requirements, reference URLs, distance-setting paths,
  `k` syntax, taxonomy behavior, and gzip FASTA guidance.
- Removed obsolete CAFA analysis pages and branding logo assets.

## 4.1.1

- See the Git tag and repository history for the release changes.
