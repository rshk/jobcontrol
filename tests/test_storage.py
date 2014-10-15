from datetime import datetime, timedelta

import pytest


def test_job_crud(storage):  # todo: test list/iter too!
    job_id = storage.create_job(
        'datacat.utils.testing:job_simple_echo',
        args=['foo', 'bar', 'baz'],
        kwargs={'spam': 100, 'eggs': 200, 'bacon': 500})

    assert isinstance(job_id, int)

    job_info = storage.get_job(job_id)
    assert job_info['id'] == job_id
    assert job_info['function'] == 'datacat.utils.testing:job_simple_echo'
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

    with pytest.raises(Exception):
        storage.get_job(job_id)


def test_job_default_values(storage):
    job_id = storage.create_job('datacat.utils.testing:job_simple_echo')

    assert isinstance(job_id, int)

    job_info = storage.get_job(job_id)
    assert job_info['id'] == job_id
    assert job_info['function'] == 'datacat.utils.testing:job_simple_echo'
    assert job_info['args'] == []
    assert job_info['kwargs'] == {}
    assert job_info['dependencies'] == []
    assert storage.get_job_deps(job_id) == []

    storage.delete_job(job_id)


def test_job_deps(storage):
    job_id1 = storage.create_job(
        'datacat.utils.testing:job_simple_echo', args=['A'])
    job_id2 = storage.create_job(
        'datacat.utils.testing:job_simple_echo', args=['B'])
    job_id3 = storage.create_job(
        'datacat.utils.testing:job_simple_echo', args=['C'])
    job_id4 = storage.create_job(
        'datacat.utils.testing:job_simple_echo', args=['C'])

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


def test_job_mget(storage):
    job_id1 = storage.create_job(
        'datacat.utils.testing:job_simple_echo', args=['A'])
    job_id2 = storage.create_job(
        'datacat.utils.testing:job_simple_echo', args=['B'])

    results = storage.mget_jobs([job_id1, job_id2])
    job1 = storage.get_job(job_id1)
    job2 = storage.get_job(job_id2)

    assert results == [job1, job2]


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
