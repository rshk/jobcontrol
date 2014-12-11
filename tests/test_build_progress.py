from jobcontrol.core import JobControl
from jobcontrol.config import JobControlConfig


def test_build_progress_reporting(storage):
    jc = JobControl(storage=storage, config=JobControlConfig())

    jc = JobControl(storage=storage, config={
        'jobs': [
            {'id': 'foo_job',
             'function': 'jobcontrol.utils.testing:job_with_progress',
             'kwargs': {'config': [
                 (None, 5),
                 (('foo', 'spam'), 2),
                 (('foo', 'eggs'), 4),
                 (('bar', 'bacon', 'X'), 8),
                 (('bar', 'bacon', 'Y'), 16)]}}
        ]
    })

    build = jc.create_build(job_id='foo_job')
