"""
Tests for builds
"""

import pickle

import pytest

from jobcontrol.core import JobControl
from jobcontrol.exceptions import SerializationError
from jobcontrol.job_conf import JobControlConfigMgr
from jobcontrol.utils import TracebackInfo, ExceptionPlaceholder
from jobcontrol.utils.testing import (
    NonSerializableObject, NonSerializableException)


def test_build_simple(storage):
    job_id = 'job-test_build_simple'

    job_config = {
        'id': job_id,
        'function': 'jobcontrol.utils.testing:job_echo_config',
        'kwargs': {'foo': 'bar'},
    }

    jc = JobControl(storage=storage,
                    config=JobControlConfigMgr({'jobs': [job_config]}))

    # ------------------------------------------------------------
    # Create build and verify generated configuration
    # ------------------------------------------------------------

    build = jc.create_build(job_id=job_id)

    assert build['job_id'] == job_id
    assert build['job_config'] == {
        'function': 'jobcontrol.utils.testing:job_echo_config',
        'kwargs': {'foo': 'bar'},
        'args': (),
        'dependencies': [],
        'id': job_id,
    }
    assert build['build_config'] == {
        'dependency_builds': {},
        'build_deps': False,
        'build_revdeps': False,
    }

    _raw_build = jc.storage.get_build(build.id)
    assert build.info == _raw_build

    job = jc.get_job(job_id)
    assert len(list(job.iter_builds())) == 1
    assert len(list(job.iter_builds(started=True))) == 0

    # ------------------------------------------------------------
    # Run the build and make sure things worked fine
    # ------------------------------------------------------------

    jc.run_build(build.id)

    job = jc.get_job(job_id)
    assert len(list(job.iter_builds())) == 1
    assert len(list(job.iter_builds(started=True, finished=True))) == 1

    build.refresh()
    assert build['finished']
    assert build['success']
    assert isinstance(build['retval'], dict)


def test_build_failure(storage):
    config = {
        'jobs': [
            {'id': 'my-first-job',
             'function': 'jobcontrol.utils.testing:testing_job',
             'kwargs': {'fail': True}}
        ]
    }

    jc = JobControl(storage=storage, config=config)

    build = jc.create_build('my-first-job')
    build.run()

    build.refresh()
    assert build['finished'] is True
    assert build['success'] is False

    assert isinstance(build['exception'], RuntimeError)
    assert isinstance(build['exception_tb'], TracebackInfo)

    # todo: can we check something more, in the TracebackInfo?


def test_nonserializable_objects():
    """Accessory test for testing objects"""

    nso = NonSerializableObject()
    with pytest.raises(Exception):
        pickle.dumps(nso)

    nse = NonSerializableException()
    with pytest.raises(Exception):
        pickle.dumps(nse)


def test_build_failure_nonserializable_object(storage):

    config = {
        'jobs': [
            {'id': 'job-returning-nso',
             'function': 'jobcontrol.utils.testing:job_returning_nonserializable'},  # noqa
        ]
    }

    jc = JobControl(storage=storage, config=config)

    # Run build for RETURN nonserializable
    # It should just fail with an exception in the post-run serialization
    # todo: We might even check the traceback for that..

    # NOTE: The in-memory storage doesn't need to serialize objects

    build = jc.create_build('job-returning-nso')
    build.run()

    build.refresh()
    assert build['finished'] is True
    assert build['success'] is False

    assert isinstance(build['exception'], SerializationError)


def test_build_failure_nonserializable_exception(storage):

    config = {
        'jobs': [
            {'id': 'job-raising-nso',
             'function': 'jobcontrol.utils.testing:job_raising_nonserializable'},  # noqa
        ]
    }

    jc = JobControl(storage=storage, config=config)

    # Run build for RAISE nonserializable
    # It should just fail with an exception in the post-run serialization
    # todo: We might even check the traceback for that..

    build = jc.create_build('job-raising-nso')
    build.run()

    build.refresh()
    assert build['finished'] is True
    assert build['success'] is False

    # WARNING! How to tell whether this job failed due to
    # the raised exception being serialized properly, or due
    # to the exception serialization failed?

    assert not isinstance(build['exception'], NonSerializableException)
    assert isinstance(build['exception'], ExceptionPlaceholder)


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

    assert job_1.get_status() == 'running'

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
