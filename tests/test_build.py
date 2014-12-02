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
