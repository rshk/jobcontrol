# -*- coding: utf-8 -*-

import logging
import sys


def test_simple_build(jc):
    job_id = jc.storage.create_job(
        'jobcontrol.utils.testing:job_simple_echo',
        args=('foo', 'bar', 'baz'),
        kwargs={'spam': 100, 'eggs': 200, 'bacon': 500})

    build_id = jc.build_job(job_id)
    build = jc.storage.get_build(build_id)
    assert build['started']
    assert build['finished']
    assert build['success']
    assert build['skipped'] is False
    assert build['start_time'] is not None
    assert build['end_time'] is not None
    assert build['retval'] == (
        ('foo', 'bar', 'baz'),
        {'spam': 100, 'eggs': 200, 'bacon': 500})
    assert build['exception'] is None


def test_build_deps(jc, request):
    """
    Jobs::

                +---+
                |DD1|
                +---+
                  ↑
        +---+   +---+   +---+
        |DD2| ← |D1 | ← |RD1|
        +---+   +---+   +---+
                  ↑
        +---+   +---+   +---+
        |D2 | ← | A | ← |R2 |
        +---+   +---+   +---+
                  ↑
        +---+   +---+   +---+
        |DR1| ← |R1 | ← |RR2|
        +---+   +---+   +---+
                  ↑
                +---+
                |RR1|
                +---+
    """

    import logging
    from jobcontrol.utils.testing import RecordingLogHandler
    root_logger = logging.getLogger('')
    root_logger.setLevel(logging.DEBUG)
    log_handler = RecordingLogHandler()
    log_handler.setLevel(logging.DEBUG)
    log_handler.clear_messages()
    root_logger.addHandler(log_handler)

    # ------------------------------------------------------------
    # Prepare test data
    # ------------------------------------------------------------

    fun = 'jobcontrol.utils.testing:job_simple_echo'

    _job_defs = [
        ('DD1', []),
        ('DD2', []),
        ('D1', ['DD1', 'DD2']),
        ('RD1', ['D1']),
        ('D2', []),
        ('A', ['D2', 'D1']),
        ('R2', 'A'),
        ('DR1', []),
        ('R1', ['A', 'DR1']),
        ('RR2', ['R1']),
        ('RR1', ['R1']),
    ]

    job_ids = {}
    for _def in _job_defs:
        job_ids[_def[0]] = jc.storage.create_job(
            fun, args=(_def[0],),
            dependencies=[job_ids[x] for x in _def[1]])

    def cleanup():
        for job_id in job_ids.itervalues():
            jc.storage.delete_job(job_id)

        root_logger.removeHandler(log_handler)

    request.addfinalizer(cleanup)

    root_logger.debug('Job ids: {0!r}'.format(job_ids))

    # ------------------------------------------------------------
    # Now, launch build of job A
    # ------------------------------------------------------------

    build_id = jc.build_job(job_ids['A'], build_deps=True,
                            build_depending=True)

    build = jc.storage.get_build(build_id)
    assert build['started'] is True
    assert build['finished'] is True
    assert build['success'] is True
    assert build['skipped'] is False

    for name, depnames in _job_defs:
        latest_build = jc.storage.get_latest_successful_build(job_ids[name])
        assert latest_build is not None
        assert latest_build['finished'] is True
        assert latest_build['success'] is True
        assert latest_build['end_time'] is not None

        for depname in depnames:
            latest_dep_build = jc.storage.get_latest_successful_build(
                job_ids[depname])
            assert latest_dep_build is not None
            assert latest_dep_build['finished'] is True
            assert latest_dep_build['success'] is True
            assert latest_dep_build['end_time'] is not None

            assert latest_dep_build['end_time'] < latest_build['end_time']


def test_build_logging(jc):
    job_id = jc.storage.create_job(
        'jobcontrol.utils.testing:job_with_logging')

    job = jc.storage.get_job(job_id)
    assert job['id'] == job_id

    build_id = jc.build_job(job_id)

    messages = list(jc.storage.iter_log_messages(build_id=build_id))
    assert len(messages) == 8  # 6 from the job, plus start / stop

    assert messages[0].levelno == logging.DEBUG
    assert messages[0].msg.startswith('[job: {0}, build: {1}] Function is '
                                      .format(job_id, build_id))

    assert messages[1].levelno == logging.DEBUG
    assert messages[1].msg == 'This is a debug message'

    assert messages[2].levelno == logging.INFO
    assert messages[2].msg == 'This is a info message'

    assert messages[3].levelno == logging.WARNING
    assert messages[3].msg == 'This is a warning message'

    assert messages[4].levelno == logging.ERROR
    assert messages[4].msg == 'This is an error message'

    assert messages[5].levelno == logging.CRITICAL
    assert messages[5].msg == 'This is a critical message'

    assert messages[6].levelno == logging.ERROR
    assert messages[6].msg == 'This is an exception message'
    assert messages[6].exc_info is not None

    assert messages[7].levelno == logging.INFO
    assert messages[7].msg == ('[job: {0}, build: {1}] Build SUCCESSFUL'
                               .format(job_id, build_id))
