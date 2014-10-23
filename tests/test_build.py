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
