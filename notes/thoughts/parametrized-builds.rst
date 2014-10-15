Parametrized builds
###################

Problem
=======

Suppose we have two jobs:

- **Job A** fetches a (variable) bunch of items from a source
- **Job B** converts those items to something else

Builds:

+--------+-------+----------------------+
| Job_id | Succ? | Retval               |
+========+=======+======================+
| A      | true  | (Pointer to storage  |
|        |       | with 4 resources)    |
+--------+-------+----------------------+

The storage is something like:

+----+--------------------------+---------------+
| ID | URL                      | Contents      |
+====+==========================+===============+
|  1 | http://example.com/res-1 | [binary data] |
+----+--------------------------+---------------+
|  2 | http://example.com/res-2 | [binary data] |
+----+--------------------------+---------------+
|  3 | http://example.com/res-3 | [binary data] |
+----+--------------------------+---------------+
|  4 | http://example.com/res-4 | [binary data] |
+----+--------------------------+---------------+

Now, ``Job B`` is run: two resources was imported successfully, two weren't.
Thus, we need to mark the build as failed, even though it was 50% successful:

+--------+-------+
| Job_id | Succ? |
+========+=======+
| B      | false |
|        |       |
+--------+-------+

(plus four log messages, indicating success for resources ``1`` and
``2``, failure for ``3`` and ``4``).

Next time ``Job B`` is run, it has to process all the resources over
again (unless maybe it has kept some external state, but that wouldn't
be really advisable..)

Plus, should at least one "sub-build" keep failing, all the depending
jobs will be prevented from rebuilding, causing a lot of problems down
the chain.

But if we would have marked the build as successful, we wouldn't have
noticed that it 50% failed (and in that case, it might have been
better to keep using data from an older build, for depending jobs..).


Proposed solution
=================

"Parametrize" the builds.

- The parametrization should be handled by the job runner itself, not
  by the external manager, which should have no knowledge of the
  retval contents.

- We need an extra column in the builds table to indicate a
  "parametrization key", for example some hash of a unique identifier
  of the resource.

- The parametrization should be able to continue down the chain.


So, for example, running ``Job B`` would result in:

+----+--------+------------+-------+----------------------+---------------+
| ID | Job_id | Param. key | Succ? | Retval               | Exception     |
+====+========+============+=======+======================+===============+
|  1 | A      | b06b6fe5.. | true  | (Pointer to data)    |               |
+----+--------+------------+-------+----------------------+---------------+
|  2 | A      | 75c80aee.. | true  | (Pointer to data)    |               |
+----+--------+------------+-------+----------------------+---------------+
|  3 | A      | 873befb8.. | false | NULL                 | <Exception..> |
+----+--------+------------+-------+----------------------+---------------+
|  4 | A      | 0b34ff1f.. | false | NULL                 | <Exception..> |
+----+--------+------------+-------+----------------------+---------------+

(Note that ``parametrization key`` is the hash of the resource URL).

A ``Job C``, depending on ``Job B``, should be able to, either:

- run one (or more!) build for **each** resource built from B
- run builds for **groups** of resources from B (including all of them)

**Note:** in the latter case, builds should use only resources from
 successful builds..

Example::

    ┌─────────┐   ┌─────────┐   ┌─────────┐   ┌─────────┐
    │         │   │         │   │         │   │         │
    │  Job A  │ ← │  Job B  │ ← │  Job C  │ ← │  Job D  │
    │         │   │         │   │         │   │         │
    └─────────┘   └─────────┘   └─────────┘   └─────────┘

     Build K=1     Build K=1     Build K=0     Build K=0
    ┌─────────┐   ┌─────────┐   ┌─────────┐   ┌─────────┐
    │  Res#1  │ ← │  Res#1' │ ← │ Res#1'' │ ← │         │
    └─────────┘   └─────────┘   └─────────┘   │         │
                                              │         │
                   Build K=2     Build K=0    │         │
    ┌─────────┐   ┌─────────┐   ┌─────────┐   │         │
    │  Res#2  │ ← │  Res#2' │ ← │ Res#2'' │ ← │         │
    └─────────┘   └─────────┘   └─────────┘   │         │
                                              │   ???   │
                   Build K=3     Build K=0    │         │
    ┌─────────┐   ┌─────────┐   ┌─────────┐   │         │
    │  Res#3  │ ← │ failed  │ ← │ skipped │ ← │         │
    └─────────┘   └─────────┘   └─────────┘   │         │
                                              │         │
                   Build K=4     Build K=0    │         │
    ┌─────────┐   ┌─────────┐   ┌─────────┐   │         │
    │  Res#4  │ ← │ failed  │ ← │ skipped │ ← │         │
    └─────────┘   └─────────┘   └─────────┘   └─────────┘

Build "K0" of Job D should be able to decide whether:

- go ahead and rebuild with just two resources
- skip execution and wait for all the resources to become available
