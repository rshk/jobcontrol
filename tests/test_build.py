"""
Tests for builds
"""

from datetime import datetime
from textwrap import dedent
import logging
import pickle

import pytest

from jobcontrol.core import JobControl
from jobcontrol.exceptions import SerializationError
from jobcontrol.config import JobControlConfig
from jobcontrol.utils import TracebackInfo, ExceptionPlaceholder
from jobcontrol.utils.testing import (
    NonSerializableObject, NonSerializableException)


def test_build_deletion(storage):
    func = 'jobcontrol.utils.testing:testing_job'

    config = {
        'jobs': [
            {'id': 'job-1', 'function': func},
        ]
    }

    jc = JobControl(storage=storage, config=config)

    job = jc.get_job('job-1')

    build_1 = job.create_build()
    build_1.run()

    assert len(list(job.iter_builds())) == 1

    build_2 = job.create_build()
    build_2.run()

    assert len(list(job.iter_builds())) == 2

    build_1.delete()

    assert len(list(job.iter_builds())) == 1

    # todo: check that all the information / progress / logs for build 1
    #       have been deleted, while the ones for build 2 have been kept

    # todo: add support for, and test, job cleanup functions -> we need
    #       a job creating some "external resource" (temp file?)
    #       plus a cleanup function that will delete it (unlink?)


def test_build_logging(storage):
    config = {
        'jobs': [
            {'id': 'job-with-logging',
             'function': 'jobcontrol.utils.testing:job_with_logging'},
        ]
    }

    jc = JobControl(storage=storage, config=config)
    job = jc.get_job('job-with-logging')

    build = job.create_build()
    build.run()
    build.refresh()

    assert build['finished'] and build['success']

    log_messages = build.iter_log_messages()
    messages_from_job = [
        msg for msg in log_messages
        if msg.name == 'jobcontrol.utils.testing.job_with_logging']

    assert len(messages_from_job) == 6

    assert messages_from_job[0].levelno == logging.DEBUG
    assert messages_from_job[0].message == 'This is a debug message'

    assert messages_from_job[0].args == ()
    assert isinstance(messages_from_job[0].created, datetime)
    assert messages_from_job[0].filename == 'testing.py'
    assert messages_from_job[0].function == 'job_with_logging'
    assert messages_from_job[0].level_name == 'DEBUG'
    assert messages_from_job[0].level == logging.DEBUG
    assert isinstance(messages_from_job[0].lineno, int)
    assert messages_from_job[0].module == 'testing'
    assert messages_from_job[0].message == 'This is a debug message'
    assert messages_from_job[0].msg == 'This is a debug message'
    assert messages_from_job[0].name == 'jobcontrol.utils.testing.job_with_logging'  # noqa
    assert isinstance(messages_from_job[0].pathname, basestring)
    assert messages_from_job[0].pathname.endswith('jobcontrol/utils/testing.py')  # noqa

    assert messages_from_job[0].exception is None
    assert messages_from_job[0].exception_tb is None

    assert messages_from_job[1].levelno == logging.INFO
    assert messages_from_job[1].message == 'This is an info message'

    assert messages_from_job[2].levelno == logging.WARNING
    assert messages_from_job[2].message == 'This is a warning message'

    assert messages_from_job[3].levelno == logging.ERROR
    assert messages_from_job[3].message == 'This is an error message'

    assert messages_from_job[4].levelno == logging.CRITICAL
    assert messages_from_job[4].message == 'This is a critical message'

    assert messages_from_job[5].levelno == logging.ERROR
    assert messages_from_job[5].message == 'This is an exception message'
    assert isinstance(messages_from_job[5].exception, ValueError)
    assert isinstance(messages_from_job[5].exception_tb, TracebackInfo)


def test_build_configuration_pinning(storage):
    config = dedent("""\
    jobs:
        - id: job-1
          function: jobcontrol.utils.testing:testing_job
          kwargs:
              retval: "original-retval"
    """)
    config = JobControlConfig.from_string(config)
    jc = JobControl(storage=storage, config=config)

    # ------------------------------------------------------------
    # Create a build with old configuration
    # ------------------------------------------------------------

    job = jc.get_job('job-1')
    build = job.create_build()
    build.run()
    build.refresh()
    assert build['finished'] and build['success']
    assert build['retval'] == 'original-retval'

    build = job.create_build()
    build_id = build.id  # Then stop using this object

    # ------------------------------------------------------------
    # Update the configuration
    # ------------------------------------------------------------

    config = dedent("""\
    jobs:
        - id: job-1
          function: jobcontrol.utils.testing:testing_job
          kwargs:
              retval: "new-retval"
    """)
    config = JobControlConfig.from_string(config)
    jc = JobControl(storage=storage, config=config)

    # ------------------------------------------------------------
    # Running that build will return the original return value

    build = jc.get_build(build_id)
    build.run()
    build.refresh()
    assert build['finished'] and build['success']
    assert build['retval'] == 'original-retval'

    # ------------------------------------------------------------
    # A freshly created build will return the new return value

    job = jc.get_job('job-1')
    build = job.create_build()
    build.run()
    build.refresh()
    assert build['finished'] and build['success']
    assert build['retval'] == 'new-retval'

    build = job.create_build()
    build_id = build.id  # Then stop using this object


@pytest.mark.xfail(True, reason='Not supported yet')
def test_dependency_pinning(storage):
    # Test for dependency pinning
    # ---------------------------
    #
    # We want to make sure that a build uses the latest build for
    # a dependency at the time it was created; so if we run a build
    # for job-1, then create a build for job-2, then run another build
    # for job-1, the return values used when running a build for job-2
    # will be the one from the *first* build.
    # To ensure this, we are going to change the return value
    # in the configuration.

    config = dedent("""\
    jobs:
        - id: job-1
          function: jobcontrol.utils.testing:testing_job
          kwargs:
              retval: "original-retval"

        - id: job-2
          function: jobcontrol.utils.testing:testing_job
          kwargs:
              retval: !retval 'job-1'
          dependencies: ['job-1']
    """)

    config = JobControlConfig.from_string(config)
    jc = JobControl(storage=storage, config=config)

    build_1_1 = jc.create_build('job-1')
    build_1_1.run()
    build_1_1.refresh()
    assert build_1_1['finished'] and build_1_1['success']
    assert build_1_1['retval'] == 'original-retval'

    # This should have pinned dependency on build_1_1
    build_2_1 = jc.create_build('job-2')

    # Update configuration
    # --------------------

    config = dedent("""\
    jobs:
        - id: job-1
          function: jobcontrol.utils.testing:testing_job
          kwargs:
              retval: "new-retval"

        - id: job-2
          function: jobcontrol.utils.testing:testing_job
          kwargs:
              retval: !retval 'job-1'
          dependencies: ['job-1']
    """)

    config = JobControlConfig.from_string(config)
    jc = JobControl(storage=storage, config=config)

    build_1_2 = jc.create_build('job-1')
    build_1_2.run()
    build_1_2.refresh()
    assert build_1_2['finished'] and build_1_2['success']
    assert build_1_2['retval'] == 'new-retval'

    build_2_1 = jc.get_build(build_2_1.id)  # Get from *new* JC
    build_2_1.run()
    build_2_1.refresh()
    assert build_2_1['finished'] and build_2_1['success']
    assert build_2_1['retval'] == 'original-retval'

    build_2_2 = jc.create_build('job-2')
    build_2_2.run()
    build_2_2.refresh()
    assert build_2_2['finished'] and build_2_2['success']
    assert build_2_2['retval'] == 'new-retval'
