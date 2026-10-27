RabbitMQ
========

RabbitMQ carries embedding tasks. The local service listens on port 5672; its
management interface is at ``http://localhost:15672``. The packaged local user
is ``guest`` with password ``guest``.

.. code-block:: bash

   docker compose ps rabbitmq
   docker compose logs rabbitmq
   nc -z localhost 5672 && echo 'RabbitMQ port reachable'

``delete_queues: true`` removes stale queues during normal startup/teardown.
It deletes *every* queue on the broker (through the management API on
``rabbitmq_port_http``), so a run that starts with ``delete_queues: true``
removes the queues and pending tasks of any other run using the same RabbitMQ
broker. Queue names are also fixed per model, not per run. Concurrent runs sharing one broker can also interfere
through resources and queue naming; prefer sequential launches, or give each
run its own broker, unless the deployment has been designed for isolation.

Several users or runs can share one PostgreSQL reference database: lookup only
reads from it. Run ``fantasia initialize`` once, since it resets the
``public`` schema, and skip it in later runs (leave ``embeddings_url`` empty or
do not call ``initialize``).
