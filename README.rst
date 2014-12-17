Job Control
###########

.. image:: https://raw.githubusercontent.com/rshk/jobcontrol/develop/.misc/banner.png

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

The status storage is completely decoupled from the main application.

The project "core" currently includes two storage implementations:

- ``MemoryStorage`` -- keeps all data in memory, useful for
  development / testing.

- ``PostgreSQLStorage`` -- keeps all data in a PostgreSQL database,
  meant for production use.


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

Source code
-----------

Source is hosted on GitHub: https://github.com/rshk/jobcontrol/

And can be cloned with::

    git clone https://github.com/rshk/jobcontrol.git

Python Package Index
--------------------

The project can be found on PyPI here: https://pypi.python.org/pypi/jobcontrol

.. image:: https://pypip.in/version/jobcontrol/badge.svg?text=version
    :target: https://github.com/rshk/jobcontrol.git
    :alt: Latest PyPI version

.. image:: https://pypip.in/download/jobcontrol/badge.svg?period=month
    :target: https://github.com/rshk/jobcontrol.git
    :alt: Number of PyPI downloads

.. image:: https://pypip.in/py_versions/jobcontrol/badge.svg
    :target: https://pypi.python.org/pypi/jobcontrol/
    :alt: Supported Python versions

.. image:: https://pypip.in/status/jobcontrol/badge.svg
    :target: https://pypi.python.org/pypi/jobcontrol/
    :alt: Development Status

.. image:: https://pypip.in/license/jobcontrol/badge.svg
    :target: https://pypi.python.org/pypi/jobcontrol/
    :alt: License

..
   .. image:: https://pypip.in/wheel/jobcontrol/badge.svg
       :target: https://pypi.python.org/pypi/jobcontrol/
       :alt: Wheel Status

   .. image:: https://pypip.in/egg/jobcontrol/badge.svg
       :target: https://pypi.python.org/pypi/jobcontrol/
       :alt: Egg Status

   .. image:: https://pypip.in/format/jobcontrol/badge.svg
       :target: https://pypi.python.org/pypi/jobcontrol/
       :alt: Download format



Project documentation
=====================

Documentation is hosted on GitHub pages:

http://rshk.github.io/jobcontrol/docs/

A mirror copy is hosted on ReadTheDocs (compiled automatically
from the Git repository; uses RTD theme; supports multiple versions):

http://jobcontrol.rtfd.org/


Concepts
========

**Jobs** are simple definitions of tasks to be executed, in terms of
a Python function, with arguments and keywords.

They also allow defining **dependencies** (and seamingless passing of
return values from dependencies as call arguments), cleanup functions,
and other nice stuff.

The library itself is responsible of keeping track of job execution
("**build**") status: start/end times, return value, whether it raised
an exception, all the log messages produced during execution, the
progress report of the execution, ...

It also features a web UI (and web APIs are planned) to have an overview
of the builds status / launch new builds / ...


..
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
