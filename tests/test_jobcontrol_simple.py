import pytest

from jobcontrol.base import JobDefinition, JobRunStatus


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


def test_job_execution(jobcontrolmgr):
    created_job = jobcontrolmgr.job_create(
        function='jobcontrol.utils.testing:example_function',
        args=('a', 'b', 'c'),
        kwargs={'spam': 100, 'eggs': 200, 'bacon': 300})
    assert isinstance(created_job, JobDefinition)

    job_run = created_job.run()
    assert isinstance(job_run, JobRunStatus)
    assert job_run.is_finished()
    assert job_run.is_successful()
    assert job_run.get_result() == (
        ('a', 'b', 'c'), {'spam': 100, 'eggs': 200, 'bacon': 300})

    assert job_run.get_progress() == (0, 0)

    with pytest.raises(RuntimeError):
        jobcontrolmgr.execute_job(123123123)


def test_job_execution_progress(jobcontrolmgr):
    created_job = jobcontrolmgr.job_create(
        function='jobcontrol.utils.testing:job_with_progress')
    assert isinstance(created_job, JobDefinition)

    job_run = created_job.run()
    assert isinstance(job_run, JobRunStatus)
    assert job_run.is_finished()
    assert job_run.is_successful()
    assert job_run.get_result() == 'DONE'
    assert job_run.get_progress() == (10, 10)


def test_job_logging(jobcontrolmgr):
    created_job = jobcontrolmgr.job_create(
        function='jobcontrol.utils.testing:job_with_logging')
    assert isinstance(created_job, JobDefinition)

    job_run = created_job.run()
    assert isinstance(job_run, JobRunStatus)
    assert job_run.is_finished()
    assert job_run.is_successful()

    log_messages = list(job_run.get_log_messages())
    assert len(log_messages) == 6
