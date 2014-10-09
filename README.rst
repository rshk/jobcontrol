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


Data model
==========

**Job**

- id
- ctime
- function
- args
- kwargs
- dependencies

**Job run**

- id
- job_id
- start_time
- end_time
- started
- finished
- success
- progress_current
- progress_total
- retval

**Job run log**

- id
- job_id
- job_run_id
- ..attributes of the log messages..
