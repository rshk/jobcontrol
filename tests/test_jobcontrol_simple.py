from jobcontrol.base import JobDefinition


def test_job_definition_crud(jobcontrolmgr):
    assert list(jobcontrolmgr.job_iter()) == []

    created_job = jobcontrolmgr.job_create(
        function='jobcontrol.utils.testing:example_function',
        args=('a', 'b', 'c'),
        kwargs={'spam': 100, 'eggs': 200, 'bacon': 300})
    assert isinstance(created_job, JobDefinition)

    jobs = list(jobcontrolmgr.job_iter())
    assert len(jobs) == 1
    assert isinstance(jobs[0], JobDefinition)

    assert jobs[0].job_id == created_job.job_id

    retrieved_job = jobcontrolmgr.job_read(created_job.job_id)
    assert retrieved_job.job_id == created_job.job_id

    retrieved_job.delete()


def test_job_definition_update(jobcontrolmgr):
    created_job = jobcontrolmgr.job_create(
        function='jobcontrol.utils.testing:example_function',
        args=('a', 'b', 'c'),
        kwargs={'spam': 100, 'eggs': 200, 'bacon': 300})
    assert isinstance(created_job, JobDefinition)

    assert created_job['args'] == ('a', 'b', 'c')
    created_job['args'] = (1, 2, 3)
    assert created_job['args'] == (1, 2, 3)

    retrieved_job = jobcontrolmgr.job_read(created_job.job_id)
    assert retrieved_job['args'] == ('a', 'b', 'c')

    created_job.save()
    retrieved_job.refresh()
    assert retrieved_job['args'] == (1, 2, 3)

    retrieved_job = jobcontrolmgr.job_read(created_job.job_id)
    assert retrieved_job['args'] == (1, 2, 3)
