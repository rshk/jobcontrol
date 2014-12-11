from textwrap import dedent

import pytest

from jobcontrol.core import JobControl
from jobcontrol.config import JobControlConfig
from jobcontrol.exceptions import NotFound


def test_job_configuration(storage):
    """
    Make sure that job configuration is loaded correctly.
    """

    config = dedent("""\
    jobs:
        - id: example-job-1
          function: jobcontrol.utils.testing:testing_job
          args: [1, 2, 3]
          kwargs:
              one: "foo"

        - id: example-job-2
          function: jobcontrol.utils.testing:testing_job
          kwargs:
              two: "bar"
              three: !retval 'example-job-2'
          dependencies: ['example-job-1']

        - id: example-job-3
          function: jobcontrol.utils.testing:testing_job
    """)

    config = JobControlConfig.from_string(config)
    jc = JobControl(storage=storage, config=config)

    job1 = jc.get_job('example-job-1')
    job2 = jc.get_job('example-job-2')
    job3 = jc.get_job('example-job-3')

    with pytest.raises(NotFound):
        jc.get_job('non-existent-job')

    # Check the JobInfo object
    assert job1.id == job1['id'] == 'example-job-1'
    assert job1['function'] == 'jobcontrol.utils.testing:testing_job'
    assert job1['args'] == (1, 2, 3)
    assert job1['kwargs'] == {'one': 'foo'}
    assert job1['dependencies'] == []
    assert job1['title'] is None
    assert job1['notes'] is None
