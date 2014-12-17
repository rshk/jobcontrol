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


# def test_build_failure(storage):
#     config = {
#         'jobs': [
#             {'id': 'my-first-job',
#              'function': 'jobcontrol.utils.testing:testing_job',
#              'kwargs': {'fail': True}}
#         ]
#     }

#     jc = JobControl(storage=storage, config=config)

#     build = jc.create_build('my-first-job')
#     build.run()

#     build.refresh()
#     assert build['finished'] is True
#     assert build['success'] is False

#     assert isinstance(build['exception'], RuntimeError)
#     assert isinstance(build['exception_tb'], TracebackInfo)

#     # todo: can we check something more, in the TracebackInfo?


# def test_nonserializable_objects():
#     """Accessory test for testing objects"""

#     nso = NonSerializableObject()
#     with pytest.raises(Exception):
#         pickle.dumps(nso)

#     nse = NonSerializableException()
#     with pytest.raises(Exception):
#         pickle.dumps(nse)


# def test_build_failure_nonserializable_object(storage):

#     config = {
#         'jobs': [
#             {'id': 'job-returning-nso',
#              'function': 'jobcontrol.utils.testing:job_returning_nonserializable'},  # noqa
#         ]
#     }

#     jc = JobControl(storage=storage, config=config)

#     # Run build for RETURN nonserializable
#     # It should just fail with an exception in the post-run serialization
#     # todo: We might even check the traceback for that..

#     # NOTE: The in-memory storage doesn't need to serialize objects

#     build = jc.create_build('job-returning-nso')
#     build.run()

#     build.refresh()
#     assert build['finished'] is True
#     assert build['success'] is False

#     assert isinstance(build['exception'], SerializationError)


# def test_build_failure_nonserializable_exception(storage):

#     config = {
#         'jobs': [
#             {'id': 'job-raising-nso',
#              'function': 'jobcontrol.utils.testing:job_raising_nonserializable'},  # noqa
#         ]
#     }

#     jc = JobControl(storage=storage, config=config)

#     # Run build for RAISE nonserializable
#     # It should just fail with an exception in the post-run serialization
#     # todo: We might even check the traceback for that..

#     build = jc.create_build('job-raising-nso')
#     build.run()

#     build.refresh()
#     assert build['finished'] is True
#     assert build['success'] is False

#     # WARNING! How to tell whether this job failed due to
#     # the raised exception being serialized properly, or due
#     # to the exception serialization failed?

#     assert not isinstance(build['exception'], NonSerializableException)
#     assert isinstance(build['exception'], ExceptionPlaceholder)


def test_job_status_reporting(storage):
    func = 'jobcontrol.utils.testing:testing_job'

    config = {
        'jobs': [
            {'id': 'job-1', 'function': func},
            {'id': 'job-2', 'function': func},
            {'id': 'job-3', 'function': func,
             'dependencies': ['job-1', 'job-2']},
            {'id': 'job-4', 'function': func,
             'dependencies': ['job-3']},
        ]
    }

    jc = JobControl(storage=storage, config=config)

    # Check status of unbuilt jobs
    job_1 = jc.get_job('job-1')
    job_2 = jc.get_job('job-2')
    job_3 = jc.get_job('job-3')
    job_4 = jc.get_job('job-4')

    assert job_1.get_status() == 'not_built'
    assert job_2.get_status() == 'not_built'
    assert job_3.get_status() == 'not_built'
    assert job_4.get_status() == 'not_built'

    assert list(job_1.iter_builds()) == []
    assert job_1.get_latest_successful_build() is None
    assert job_1.has_builds() is False
    assert job_1.has_successful_builds() is False
    assert job_1.has_running_builds() is False
    assert job_1.is_outdated() is None  # IDK
    assert job_1.can_be_built() is True

    assert job_2.can_be_built() is True
    assert job_3.can_be_built() is False  # deps not met
    assert job_4.can_be_built() is False  # deps not met

    # ------------------------------------------------------------
    # Manually start a build for job 1, as we want to
    # check it is running, etc..
    # ------------------------------------------------------------

    build_1_1 = job_1.create_build()
    assert build_1_1['started'] is False
    assert build_1_1['finished'] is False
    assert job_1.has_builds() is False
    assert job_1.has_running_builds() is False

    assert job_1.get_status() == 'not_built'

    jc.storage.start_build(build_1_1.id)
    build_1_1.refresh()
    assert build_1_1['started'] is True
    assert build_1_1['finished'] is False
    assert job_1.has_builds() is False  # **Completed** builds..
    assert job_1.has_running_builds() is True

    # Note: "running" is not anymore reported as a state
    assert job_1.get_status() == 'not_built'

    jc.storage.finish_build(build_1_1.id, success=False)
    build_1_1.refresh()
    assert build_1_1['started'] is True
    assert build_1_1['finished'] is True
    assert build_1_1['success'] is False
    assert job_1.has_builds() is True
    assert job_1.has_successful_builds() is False
    assert job_1.has_running_builds() is False

    assert job_1.get_status() == 'failed'

    # ------------------------------------------------------------
    # Do it again, with a new build, which should succeed this time
    # ------------------------------------------------------------

    build_1_2 = job_1.create_build()
    build_1_2.run()
    build_1_2.refresh()

    assert len(list(job_1.iter_builds())) == 2
    assert build_1_2['started'] is True
    assert build_1_2['finished'] is True
    assert build_1_2['success'] is True
    assert job_1.has_builds() is True
    assert job_1.has_successful_builds() is True
    assert job_1.has_running_builds() is False

    assert job_1.get_status() == 'success'

    # ------------------------------------------------------------
    # Now build job 2 and make sure 3 becomes buildable
    # ------------------------------------------------------------

    assert job_3.can_be_built() is False
    build_2_1 = job_2.create_build()
    build_2_1.run()
    assert job_3.can_be_built() is True

    # Job 4 is still missing a build from 3
    assert job_4.can_be_built() is False
    job_3.create_build().run()
    assert job_4.can_be_built() is True

    assert job_2.get_status() == 'success'
    assert job_3.get_status() == 'success'
    assert job_4.get_status() == 'not_built'

    # ------------------------------------------------------------
    # Rebuild #1 to get #3 to be "outdated"
    # ------------------------------------------------------------

    assert job_3.is_outdated() is False
    job_1.create_build().run()
    assert job_3.is_outdated() is True
    assert job_3.get_status() == 'outdated'


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
