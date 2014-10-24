# -*- coding: utf-8 -*-


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
