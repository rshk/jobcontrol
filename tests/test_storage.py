from datetime import datetime, timedelta

import pytest

from jobcontrol.exceptions import NotFound


def test_job_crud(storage):  # todo: test list/iter too!
    job_id = storage.create_job(
        'jobcontrol.utils.testing:job_simple_echo',
        args=['foo', 'bar', 'baz'],
        kwargs={'spam': 100, 'eggs': 200, 'bacon': 500})

    assert isinstance(job_id, int)

    job_info = storage.get_job(job_id)
    assert job_info['id'] == job_id
    assert job_info['function'] == 'jobcontrol.utils.testing:job_simple_echo'
    assert job_info['args'] == ['foo', 'bar', 'baz']
    assert job_info['kwargs'] == {'spam': 100, 'eggs': 200, 'bacon': 500}
    assert job_info['dependencies'] == []
    assert storage.get_job_deps(job_id) == []

    assert isinstance(job_info['ctime'], datetime)
    assert datetime.now() - job_info['ctime'] <= timedelta(seconds=2)

    storage.update_job(job_id, function='foo:bar')
    storage.update_job(job_id, args=['foo', 'bar'], kwargs={'A': 1})
    storage.update_job(job_id, dependencies=[1, 2, 3])

    job_info = storage.get_job(job_id)
    assert job_info['id'] == job_id
    assert job_info['function'] == 'foo:bar'
    assert job_info['args'] == ['foo', 'bar']
    assert job_info['kwargs'] == {'A': 1}
    assert job_info['dependencies'] == [1, 2, 3]
    # assert len(storage.get_job_deps(job_id)) == 1

    storage.delete_job(job_id)

    with pytest.raises(NotFound):
        storage.get_job(job_id)


def test_job_list_iter_mget(storage):
    # With empty db
    assert storage.list_jobs() == []
    assert list(storage.iter_jobs()) == []
    assert storage.mget_jobs([1, 2, 3, 4]) == []

    # Create jobs
    job_ids = [storage.create_job('foo:bar', args=[x]) for x in xrange(5)]

    # Query..
    assert storage.list_jobs() == job_ids

    _jobs = list(storage.iter_jobs())
    assert [x['id'] for x in _jobs] == job_ids
    for x in _jobs:
        assert x['function'] == 'foo:bar'

    _jobs2 = storage.mget_jobs(job_ids)
    assert _jobs2 == _jobs

    for jid in job_ids:
        storage.delete_job(jid)


def test_job_default_values(storage):
    job_id = storage.create_job('jobcontrol.utils.testing:job_simple_echo')

    assert isinstance(job_id, int)

    job_info = storage.get_job(job_id)
    assert job_info['id'] == job_id
    assert job_info['function'] == 'jobcontrol.utils.testing:job_simple_echo'
    assert job_info['args'] == ()
    assert job_info['kwargs'] == {}
    assert job_info['dependencies'] == []
    assert storage.get_job_deps(job_id) == []

    storage.delete_job(job_id)


def test_job_deps(storage):
    job_id1 = storage.create_job(
        'jobcontrol.utils.testing:job_simple_echo', args=['A'])
    job_id2 = storage.create_job(
        'jobcontrol.utils.testing:job_simple_echo', args=['B'])
    job_id3 = storage.create_job(
        'jobcontrol.utils.testing:job_simple_echo', args=['C'])
    job_id4 = storage.create_job(
        'jobcontrol.utils.testing:job_simple_echo', args=['C'])

    storage.update_job(job_id1, dependencies=[job_id2, job_id4])
    storage.update_job(job_id2, dependencies=[job_id3])
    storage.update_job(job_id3, dependencies=[job_id4])

    _depids = lambda j: [x['id'] for x in storage.get_job_deps(j)]
    _rdepids = lambda j: [x['id'] for x in storage.get_job_revdeps(j)]

    assert _depids(job_id1) == [job_id2, job_id4]
    assert _rdepids(job_id1) == []

    assert _depids(job_id2) == [job_id3]
    assert _rdepids(job_id2) == [job_id1]

    assert _depids(job_id3) == [job_id4]
    assert _rdepids(job_id3) == [job_id2]

    assert _depids(job_id4) == []
    assert _rdepids(job_id4) == [job_id1, job_id3]

    for jid in (job_id1, job_id2, job_id3, job_id4):
        storage.delete_job(jid)


def test_job_build_crud(storage):
    job_id = storage.create_job('foo:bar')

    build_id = storage.create_build(job_id)
    assert isinstance(build_id, int)

    build = build_v0 = storage.get_build(build_id)
    assert build['id'] == build_id
    assert build['job_id'] == job_id
    assert build['start_time'] is None
    assert build['end_time'] is None
    assert build['started'] is False
    assert build['finished'] is False
    assert build['success'] is False
    assert build['skipped'] is False
    assert build['retval'] is None
    assert build['exception'] is None
    assert build['progress_current'] == 0
    assert build['progress_total'] == 0

    storage.start_build(build_id)

    build = build_v1 = storage.get_build(build_id)
    assert build['id'] == build_id
    assert build['job_id'] == job_id
    assert isinstance(build['start_time'], datetime)
    assert datetime.now() - build['start_time'] < timedelta(seconds=2)
    assert build['end_time'] is None
    assert build['started'] is True
    assert build['finished'] is False
    assert build['success'] is False
    assert build['skipped'] is False
    assert build['retval'] is None
    assert build['exception'] is None
    assert build['progress_current'] == 0
    assert build['progress_total'] == 0

    storage.finish_build(build_id)

    build = build_v2 = storage.get_build(build_id)
    assert build['id'] == build_id
    assert build['job_id'] == job_id
    assert build['start_time'] == build_v1['start_time']
    assert isinstance(build['end_time'], datetime)
    assert datetime.now() - build['end_time'] < timedelta(seconds=2)
    assert build['started'] is True
    assert build['finished'] is True
    assert build['success'] is True
    assert build['skipped'] is False
    assert build['retval'] is None
    assert build['exception'] is None
    assert build['progress_current'] == 0
    assert build['progress_total'] == 0

    storage.finish_build(build_id, success=False, skipped=True,
                         retval="Something", exception=ValueError('Foo'))

    build = build_v3 = storage.get_build(build_id)
    assert build['id'] == build_id
    assert build['job_id'] == job_id
    assert build['start_time'] == build_v2['start_time']
    # end time will be changed..
    assert isinstance(build['end_time'], datetime)
    assert datetime.now() - build['end_time'] < timedelta(seconds=2)
    assert build['started'] is True
    assert build['finished'] is True
    assert build['success'] is False
    assert build['skipped'] is True
    assert build['retval'] == 'Something'
    assert isinstance(build['exception'], ValueError)
    assert build['progress_current'] == 0
    assert build['progress_total'] == 0

    storage.update_build_progress(build_id, 50, 100)

    build = build_v4 = storage.get_build(build_id)
    assert build['id'] == build_id
    assert build['job_id'] == job_id
    assert build['start_time'] == build_v3['start_time']
    assert build['end_time'] == build_v3['end_time']
    assert build['started'] == build_v3['started']
    assert build['finished'] == build_v3['finished']
    assert build['success'] == build_v3['success']
    assert build['skipped'] == build_v3['skipped']
    assert build['retval'] == build_v3['retval']
    assert isinstance(build['exception'], ValueError)
    assert build['progress_current'] == 50
    assert build['progress_total'] == 100

    storage.delete_build(build_id)
    with pytest.raises(Exception):
        storage.get_build(build_id)

    storage.delete_job(job_id)


def test_job_multiple_builds(storage):
    job_id = storage.create_job('foo:bar')

    def _get_build_ids(**kw):
        return [x['id'] for x in storage.get_job_builds(job_id, **kw)]

    assert _get_build_ids() == []

    b1id = storage.create_build(job_id)
    b2id = storage.create_build(job_id)
    b3id = storage.create_build(job_id)
    b4id = storage.create_build(job_id)

    assert _get_build_ids() == [b1id, b2id, b3id, b4id]
    assert _get_build_ids(started=False) == [b1id, b2id, b3id, b4id]
    assert _get_build_ids(started=True) == []
    assert _get_build_ids(finished=True) == []
    assert _get_build_ids(skipped=True) == []
    assert _get_build_ids(skipped=False) == [b1id, b2id, b3id, b4id]

    assert _get_build_ids(order='asc', limit=2) == [b1id, b2id]
    assert _get_build_ids(order='desc', limit=2) == [b4id, b3id]

    storage.start_build(b1id)

    assert _get_build_ids() == [b1id, b2id, b3id, b4id]
    assert _get_build_ids(started=False) == [b2id, b3id, b4id]
    assert _get_build_ids(started=True) == [b1id]
    assert _get_build_ids(finished=True) == []
    assert _get_build_ids(skipped=True) == []
    assert _get_build_ids(skipped=False) == [b1id, b2id, b3id, b4id]

    storage.start_build(b2id)

    assert _get_build_ids() == [b1id, b2id, b3id, b4id]
    assert _get_build_ids(started=False) == [b3id, b4id]
    assert _get_build_ids(started=True) == [b1id, b2id]
    assert _get_build_ids(finished=True) == []
    assert _get_build_ids(skipped=True) == []
    assert _get_build_ids(skipped=False) == [b1id, b2id, b3id, b4id]

    storage.start_build(b3id)
    storage.finish_build(b1id, success=True, retval='B1-RET')

    assert _get_build_ids() == [b1id, b2id, b3id, b4id]
    assert _get_build_ids(started=False) == [b4id]
    assert _get_build_ids(started=True) == [b1id, b2id, b3id]
    assert _get_build_ids(finished=True) == [b1id]
    assert _get_build_ids(finished=True, success=True) == [b1id]
    assert _get_build_ids(finished=True, success=False) == []
    assert _get_build_ids(skipped=True) == []
    assert _get_build_ids(skipped=False) == [b1id, b2id, b3id, b4id]

    storage.finish_build(b2id, success=False,
                         exception=ValueError('Simulated failure'))

    assert _get_build_ids() == [b1id, b2id, b3id, b4id]
    assert _get_build_ids(started=False) == [b4id]
    assert _get_build_ids(started=True) == [b1id, b2id, b3id]
    assert _get_build_ids(finished=True) == [b1id, b2id]
    assert _get_build_ids(finished=True, success=True) == [b1id]
    assert _get_build_ids(finished=True, success=False) == [b2id]
    assert _get_build_ids(skipped=True) == []
    assert _get_build_ids(skipped=False) == [b1id, b2id, b3id, b4id]

    storage.finish_build(b3id, success=True, skipped=True)

    assert _get_build_ids() == [b1id, b2id, b3id, b4id]
    assert _get_build_ids(started=False) == [b4id]
    assert _get_build_ids(started=True) == [b1id, b2id, b3id]
    assert _get_build_ids(finished=True) == [b1id, b2id, b3id]
    assert _get_build_ids(finished=True, success=True) == [b1id, b3id]
    assert _get_build_ids(finished=True, success=False) == [b2id]
    assert _get_build_ids(skipped=True) == [b3id]
    assert _get_build_ids(skipped=False) == [b1id, b2id, b4id]

    assert _get_build_ids(finished=True, success=True, skipped=False,
                          order='desc', limit=1) == [b1id]

    storage.start_build(b4id)
    storage.finish_build(b4id, success=True, retval='B4-RET')

    # ------------------------------------------------------------
    # Get build reports

    build1 = storage.get_build(b1id)
    assert build1['success'] is True
    assert build1['retval'] == 'B1-RET'

    build2 = storage.get_build(b2id)
    assert build2['success'] is False
    assert isinstance(build2['exception'], ValueError)

    build3 = storage.get_build(b3id)
    assert build3['success'] is True
    assert build3['skipped'] is True

    build4 = storage.get_build(b4id)
    assert build4['success'] is True
    assert build4['retval'] == 'B4-RET'


def test_job_deletion(storage):
    job_id = storage.create_job('foo:bar')
    b1id = storage.create_build(job_id)
    b2id = storage.create_build(job_id)

    storage.delete_job(job_id)

    with pytest.raises(NotFound):
        storage.get_build(b1id)
    with pytest.raises(NotFound):
        storage.get_build(b2id)
    with pytest.raises(NotFound):
        storage.get_job(job_id)


def test_logging(storage):
    import logging

    job_id = storage.create_job('foo:bar')
    build_id = storage.create_build(job_id)

    def _make_log(level, msg):
        return logging.makeLogRecord(
            {'name': 'my_logger', 'levelno': level, 'msg': msg,
             'message': msg})

    def _log(level, msg):
        storage.log_message(job_id, build_id, _make_log(level, msg))

    _log(logging.DEBUG, 'A DEBUG message')
    _log(logging.INFO, 'A INFO message')
    _log(logging.WARNING, 'A WARNING message')
    _log(logging.ERROR, 'A ERROR message')
    _log(logging.CRITICAL, 'A CRITICAL message')

    log_messages = list(storage.iter_log_messages(
        job_id=job_id, build_id=build_id))
    assert len(log_messages) == 5

    warning_messages = list(storage.iter_log_messages(
        job_id=job_id, build_id=build_id, min_level=logging.WARNING))
    assert len(warning_messages) == 3

    storage.prune_log_messages(job_id=job_id, build_id=build_id,
                               level=logging.WARNING)

    log_messages = list(storage.iter_log_messages(
        job_id=job_id, build_id=build_id))
    assert len(log_messages) == 3

    storage.prune_log_messages(job_id=job_id, build_id=build_id,
                               level=logging.ERROR)

    log_messages = list(storage.iter_log_messages(
        job_id=job_id, build_id=build_id))
    assert len(log_messages) == 2

    # todo: test logging date filtering / pruning (+ policy pruning)
