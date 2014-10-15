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


Concepts
========

- Each job is defined as a Python function to be run, with arguments
  and keywords.
- Each job can depend on other jobs; the dependency sistem ensures
  all dependencies are built before running a given job, and that
  depending jobs are rebuilt when a "higher-level" one is built.

Example::

    ┌─────────┐   ┌─────────┐   ┌─────────┐   ┌─────────┐
    │         │   │         │   │         │   │         │
    │  Job A  │ → │  Job B  │ → │  Job C  │ → │  Job D  │
    │         │   │         │   │         │   │         │
    └─────────┘   └─────────┘   └─────────┘   └─────────┘

When running the task ``C``, a build of ``B`` will be required; this
in turn requires a build of ``A``. If ``build_deps=True`` was
specified, a build of ``C`` and ``B`` will be triggered. Otherwise,
the build will terminate with a "dependencies not met" error.

After a successful build of ``C``, ``D`` is not outdated.  If
``build_depending=True`` was specified, a build of ``D`` will be
triggered.

Other example: ``Job #2`` depends on ``Job #2``:


**Job #1**

+-------+-------+------+-------+
| Build | Succ? | Time | Skip? |
+=======+=======+======+=======+
|     1 | TRUE  |    1 | FALSE |
+-------+-------+------+-------+
|     2 | FALSE |    3 | FALSE |
+-------+-------+------+-------+
|     3 | TRUE  |    4 | TRUE  |
+-------+-------+------+-------+
|     4 | TRUE  |    5 | FALSE |
+-------+-------+------+-------+


**Job #2**

+-------+-------+------+-------+
| Build | Succ? | Time | Skip? |
+=======+=======+======+=======+
|     1 | TRUE  |    2 | FALSE |
+-------+-------+------+-------+
|       No rebuild needed.     |
+-------+-------+------+-------+
|       No rebuild needed.     |
+-------+-------+------+-------+
|     2 | TRUE  |    6 | FALSE |
+-------+-------+------+-------+
