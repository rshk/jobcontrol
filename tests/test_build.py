# -*- coding: utf-8 -*-

import logging
# import sys


def test_simple_build(jc):
    job_id = jc.storage.create_job(
        function='jobcontrol.utils.testing:job_simple_echo',
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
            function=fun, args=(_def[0],),
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


def test_build_logging(jc, request):
    job_id = jc.storage.create_job(
        function='jobcontrol.utils.testing:job_with_logging')

    request.addfinalizer(lambda: jc.storage.delete_job(job_id))

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

    # ------------------------------------------------------------
    # Run another build and check logs
    # ------------------------------------------------------------

    build_id_2 = jc.build_job(job_id)

    messages = list(jc.storage.iter_log_messages(build_id=build_id))
    assert len(messages) == 8  # 6 from the job, plus start / stop

    messages = list(jc.storage.iter_log_messages(build_id=build_id_2))
    assert len(messages) == 8  # 6 from the job, plus start / stop


def test_build_logs_with_deps(jc, request):
    # ------------------------------------------------------------
    # Run a bunch of jobs with deps, check messages
    # ------------------------------------------------------------

    job_id_1 = jc.storage.create_job(
        function='jobcontrol.utils.testing:job_with_tracer_log')
    job_id_2 = jc.storage.create_job(
        function='jobcontrol.utils.testing:job_with_tracer_log')
    job_id_3 = jc.storage.create_job(
        function='jobcontrol.utils.testing:job_with_tracer_log',
        dependencies=[job_id_1, job_id_2])

    assert len(list(jc.storage.get_job_builds(job_id_1))) == 0
    assert len(list(jc.storage.get_job_builds(job_id_2))) == 0
    assert len(list(jc.storage.get_job_builds(job_id_3))) == 0

    jc.build_job(job_id_3)

    builds_1 = list(jc.storage.get_job_builds(job_id_1))
    builds_2 = list(jc.storage.get_job_builds(job_id_2))
    builds_3 = list(jc.storage.get_job_builds(job_id_3))

    assert len(builds_1) == 1
    assert len(builds_2) == 1
    assert len(builds_3) == 1

    assert builds_1[0]['success'] is True
    assert builds_2[0]['success'] is True
    assert builds_3[0]['success'] is True

    msgs_1 = list(jc.storage.iter_log_messages(build_id=builds_1[0]['id']))
    msgs_2 = list(jc.storage.iter_log_messages(build_id=builds_2[0]['id']))
    msgs_3 = list(jc.storage.iter_log_messages(build_id=builds_3[0]['id']))

    assert len(msgs_1) == 3
    assert len(msgs_2) == 3
    assert len(msgs_3) == 3

    assert msgs_1[1].msg == ('Message from job={0}, build={1}'
                             .format(job_id_1, builds_1[0]['id']))

    assert msgs_2[1].msg == ('Message from job={0}, build={1}'
                             .format(job_id_2, builds_2[0]['id']))

    assert msgs_3[1].msg == ('Message from job={0}, build={1}'
                             .format(job_id_3, builds_3[0]['id']))


def test_build_logs_with_deps_async(jc, request):
    from jobcontrol.async.tasks import app as celery_app, build_job
    import copy

    conf_bck = celery_app.conf
    celery_app.conf = copy.deepcopy(celery_app.conf)
    celery_app.conf.JOBCONTROL = jc
    celery_app.conf.CELERY_ALWAYS_EAGER = True

    def cleanup():
        celery_app.conf = conf_bck

    request.addfinalizer(cleanup)

    # ------------------------------------------------------------
    # Run a bunch of jobs with deps, check messages
    # ------------------------------------------------------------

    job_id_1 = jc.storage.create_job(
        function='jobcontrol.utils.testing:job_with_tracer_log')
    job_id_2 = jc.storage.create_job(
        function='jobcontrol.utils.testing:job_with_tracer_log')
    job_id_3 = jc.storage.create_job(
        function='jobcontrol.utils.testing:job_with_tracer_log',
        dependencies=[job_id_1, job_id_2])

    assert len(list(jc.storage.get_job_builds(job_id_1))) == 0
    assert len(list(jc.storage.get_job_builds(job_id_2))) == 0
    assert len(list(jc.storage.get_job_builds(job_id_3))) == 0

    res = build_job.delay(job_id_3)
    res.wait()

    builds_1 = list(jc.storage.get_job_builds(job_id_1))
    builds_2 = list(jc.storage.get_job_builds(job_id_2))
    builds_3 = list(jc.storage.get_job_builds(job_id_3))

    assert len(builds_1) == 1
    assert len(builds_2) == 1
    assert len(builds_3) == 1

    assert builds_1[0]['success'] is True
    assert builds_2[0]['success'] is True
    assert builds_3[0]['success'] is True

    msgs_1 = list(jc.storage.iter_log_messages(build_id=builds_1[0]['id']))
    msgs_2 = list(jc.storage.iter_log_messages(build_id=builds_2[0]['id']))
    msgs_3 = list(jc.storage.iter_log_messages(build_id=builds_3[0]['id']))

    assert len(msgs_1) == 3
    assert len(msgs_2) == 3
    assert len(msgs_3) == 3

    assert msgs_1[1].msg == ('Message from job={0}, build={1}'
                             .format(job_id_1, builds_1[0]['id']))

    assert msgs_2[1].msg == ('Message from job={0}, build={1}'
                             .format(job_id_2, builds_2[0]['id']))

    assert msgs_3[1].msg == ('Message from job={0}, build={1}'
                             .format(job_id_3, builds_3[0]['id']))


def test_build_with_unicode(jc):
    job_id = jc.storage.create_job(
        function='jobcontrol.utils.testing:job_simple_echo',
        args=(u'föö', u'bär', u'bäz'),
        kwargs={u'spám': 100, u'éggs': 200, u'bäcon': 500})

    build_id = jc.build_job(job_id)
    build = jc.storage.get_build(build_id)
    assert build['started']
    assert build['finished']
    assert build['success']
    assert build['skipped'] is False
    assert build['start_time'] is not None
    assert build['end_time'] is not None
    assert build['retval'] == (
        (u'föö', u'bär', u'bäz'),
        {u'spám': 100, u'éggs': 200, u'bäcon': 500})
    assert build['exception'] is None


def test_build_with_bytes_data(jc):
    args = ('\xaa\xbb\x00\xff\xff\x00ABC',)
    job_id = jc.storage.create_job(
        function='jobcontrol.utils.testing:job_simple_echo',
        args=args)

    build_id = jc.build_job(job_id)
    build = jc.storage.get_build(build_id)
    assert build['started']
    assert build['finished']
    assert build['success']
    assert build['skipped'] is False
    assert build['start_time'] is not None
    assert build['end_time'] is not None
    assert build['retval'] == (args, {})
    assert build['exception'] is None
