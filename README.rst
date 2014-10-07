Job Control
###########

Library to manage definition + running of "jobs".

- Each job is simply a Python callable.
- Jobs are defined in a PostgreSQL table as ``(callable, args, kwargs)``,
  serialized using json.

**Features (planned):**

- Job definition
- Job execution
- Asynchronous job execution, via Celery workers
- Administration via CLI
- Administration via RESTful API
