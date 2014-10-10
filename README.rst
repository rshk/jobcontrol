Job Control
###########

Job scheduling and tracking library.

Provides a base interface for scheduling, running, tracking and
retrieving results for "jobs".

Each job definition is simply any Python callable, along with
arguments to be passed to it.

The tracking include storing:
- the function return value
- any exception raised
- log messages produced during task execution
- optionally a "progress", if the task supports it

The library is not tied to any particular storage; the core includes
two implementations:

- ``MemoryJobControl`` -- keeps all the data in memory; especially
  useful for testing purposes.

- ``PostgreSQLJobControl`` -- PostgreSQL-backed job control, meant for
  production use.


Project status
==============

**Travis CI build status**

+----------+-----------------------------------------------------------------------+
| Branch   | Status                                                                |
+==========+=======================================================================+
| master   | .. image:: https://travis-ci.org/rshk/jobcontrol.svg?branch=master    |
|          |     :target: https://travis-ci.org/rshk/jobcontrol                    |
+----------+-----------------------------------------------------------------------+
| develop  | .. image:: https://travis-ci.org/rshk/jobcontrol.svg?branch=develop   |
|          |     :target: https://travis-ci.org/rshk/jobcontrol                    |
+----------+-----------------------------------------------------------------------+


Project documentation
=====================

Documentation is hosted on GitHub pages: *(coming soon!)*
http://rshk.github.io/jobcontrol/
