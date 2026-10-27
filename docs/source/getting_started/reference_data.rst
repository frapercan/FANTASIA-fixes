Reference data setup
====================

Current releases
----------------

.. list-table::
   :header-rows: 1

   * - Reference
     - Zenodo record
     - Download
     - Use
   * - Final layer
     - `17795871 <https://zenodo.org/records/17795871>`_
     - approximately 3.1 GB
     - Recommended for routine annotation
   * - Multiple layers
     - `17793273 <https://zenodo.org/records/17793273>`_
     - approximately 17.1 GB
     - Layer-comparison workflows

The reference database contains experimentally annotated proteins and their
model/layer embeddings. It is distinct from manuscript benchmark-output
archives.

Restore the final-layer reference
---------------------------------

Start PostgreSQL and RabbitMQ first, then run:

.. code-block:: bash

   poetry run fantasia initialize \
     --config ./config/prott5_test.yaml \
     --base_directory ./lookup \
     --log_path ./lookup/logs \
     --embeddings_url 'https://zenodo.org/records/17795871/files/BioData_Dec25_esm2_prott5_prostt5_ankh3_large_esm3c_Layer0.backup?download=1'

.. warning::

   The initializer resets the configured database's ``public`` schema before
   restoring the dump. Use a dedicated FANTASIA database.

The downloaded dump is retained below ``lookup/embeddings/``. To reuse a dump
that is already on disk (for example on shared HPC storage), pass a
``file://`` URL or a plain path; it is restored in place without copying:

.. code-block:: bash

   poetry run fantasia initialize --config ./config/prott5_test.yaml \
     --embeddings_url file:///shared/fantasia/BioData_Dec25_esm2_prott5_prostt5_ankh3_large_esm3c_Layer0.backup

The dumps were written by PostgreSQL 18. ``pg_restore`` 16 or 17 rejects them
with ``unsupported version (1.16) in file header``; use the FANTASIA image or a
PostgreSQL 18 client. Restoring into an older *server* with client 18 reports
an error for ``SET transaction_timeout``; FANTASIA recognises it as harmless.
``fantasia initialize`` exits with a non-zero status if the restore fails. Software model
and layer selections must exist in the restored reference. The repository does
not currently implement automatic checksum verification; retain Zenodo
metadata and calculate a local SHA-256 checksum when provenance is required.
