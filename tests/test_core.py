# ------------------------------------------------------------
# TESTS for jobcontrol.core
# ------------------------------------------------------------

# todo:
# -----
# - test loading configuration *from file*
# - test skipped build
# - test build run by id
# - test build fail due to missing dependencies
# - test automatic depdendency build (to be implemented)
# - test build deletion [+ cleanup] (to be implemented)
# - test validation of build state inconsistencies
#   eg. trying to start a running / finished job, ...


import pickle

import pytest

from jobcontrol.core import JobControl, JobInfo
from jobcontrol.config import JobControlConfig, BuildConfig, Retval
from jobcontrol.exceptions import NotFound, SerializationError
from jobcontrol.utils import TracebackInfo, ExceptionPlaceholder
from jobcontrol.utils.testing import (
    NonSerializableObject, NonSerializableException)


def test_core_config_jobs(storage):
    config = JobControlConfig.from_string("""
    jobs:
        - id: foo
          function: mymodule.foo
          dependencies: []

        - id: bar
          function: mymodule.bar
          dependencies: ['foo']

        - id: baz
          function: mymodule.baz
          dependencies: ['foo', 'bar']
    """)
    jc = JobControl(storage=storage, config=config)

    job_foo = jc.get_job('foo')
    job_bar = jc.get_job('bar')
    job_baz = jc.get_job('baz')

    # Check jobs
    # ------------------------------------------------------------

    assert isinstance(job_foo, JobInfo)
    assert job_foo.id == 'foo'
    assert job_foo.config['id'] == 'foo'
    assert job_foo.config['function'] == 'mymodule.foo'
    assert job_foo.config['args'] == ()
    assert job_foo.config['kwargs'] == {}
    assert job_foo.config['dependencies'] == []
    assert list(job_foo.get_deps()) == []
    assert list(job_foo.get_revdeps()) == [job_bar, job_baz]
    assert job_foo.get_status() == 'not_built'
    assert list(job_foo.iter_builds()) == []
    assert job_foo.get_latest_successful_build() is None
    assert job_foo.has_builds() is False
    assert job_foo.has_successful_builds() is False
    assert job_foo.has_running_builds() is False
    assert job_foo.is_outdated() is None  # no builds..
    assert job_foo.can_be_built() is True

    assert isinstance(job_bar, JobInfo)
    assert job_bar.id == 'bar'
    assert job_bar.config['id'] == 'bar'
    assert job_bar.config['function'] == 'mymodule.bar'
    assert job_bar.config['args'] == ()
    assert job_bar.config['kwargs'] == {}
    assert job_bar.config['dependencies'] == ['foo']
    assert list(job_bar.get_deps()) == [job_foo]
    assert list(job_bar.get_revdeps()) == [job_baz]
    assert job_bar.get_status() == 'not_built'
    assert list(job_bar.iter_builds()) == []
    assert job_bar.get_latest_successful_build() is None
    assert job_bar.has_builds() is False
    assert job_bar.has_successful_builds() is False
    assert job_bar.has_running_builds() is False
    assert job_bar.is_outdated() is None  # no builds..
    assert job_bar.can_be_built() is False  # "foo" has no builds

    assert isinstance(job_baz, JobInfo)
    assert job_baz.id == 'baz'
    assert job_baz.config['id'] == 'baz'
    assert job_baz.config['function'] == 'mymodule.baz'
    assert job_baz.config['args'] == ()
    assert job_baz.config['kwargs'] == {}
    assert job_baz.config['dependencies'] == ['foo', 'bar']
    assert list(job_baz.get_deps()) == [job_foo, job_bar]
    assert list(job_baz.get_revdeps()) == []
    assert job_baz.get_status() == 'not_built'
    assert list(job_baz.iter_builds()) == []
    assert job_baz.get_latest_successful_build() is None
    assert job_baz.has_builds() is False
    assert job_baz.has_successful_builds() is False
    assert job_baz.has_running_builds() is False
    assert job_baz.is_outdated() is None  # no builds..
    assert job_baz.can_be_built() is False  # "foo" and "bar" have no builds

    # Exception on non-existing job

    with pytest.raises(NotFound):
        jc.get_job('does-not-exist')

    # Iterate jobs

    assert list(jc.iter_jobs()) == [job_foo, job_bar, job_baz]


# ------------------------------------------------------------
# NEW TESTS FOR BUILDS
# ------------------------------------------------------------


def test_simple_build_run(storage):
    config = JobControlConfig.from_string("""
    jobs:
        - id: foo
          function: jobcontrol.utils.testing:testing_job
          kwargs:
              retval: "Foo Retval"
    """)
    jc = JobControl(storage=storage, config=config)

    job = jc.get_job('foo')

    assert job.has_builds() is False
    assert job.has_successful_builds() is False
    assert job.has_running_builds() is False
    assert job.is_outdated() is None
    assert job.can_be_built() is True

    # Create and run a build
    # ------------------------------------------------------------

    build = job.create_build()

    assert job.has_builds() is False  # "finished" builds only
    assert job.has_successful_builds() is False
    assert job.has_running_builds() is False
    assert job.is_outdated() is None
    assert job.can_be_built() is True
    assert list(job.iter_builds()) == [build]

    build.run()

    assert build['started'] is True
    assert build['finished'] is True
    assert build['success'] is True
    assert build['skipped'] is False
    assert build['retval'] == 'Foo Retval'

    assert job.has_builds() is True
    assert job.has_successful_builds() is True
    assert job.has_running_builds() is False
    assert job.is_outdated() is False
    assert job.can_be_built() is True
    assert list(job.iter_builds()) == [build]


def test_build_with_failure(storage):
    config = JobControlConfig.from_string("""
    jobs:
        - id: foo
          function: jobcontrol.utils.testing:testing_job
          kwargs:
              retval: "Foo Retval"
              fail: True
    """)
    jc = JobControl(storage=storage, config=config)

    job = jc.get_job('foo')
    build = job.create_build()
    build.run()

    assert build['started']
    assert build['finished']
    assert not build['success']
    assert not build['skipped']

    assert job.has_builds()
    assert not job.has_successful_builds()
    assert not job.has_running_builds()
    assert list(job.iter_builds()) == [build]
    assert list(job.iter_builds(success=True)) == []
    assert list(job.iter_builds(success=False)) == [build]

    assert isinstance(build['exception'], RuntimeError)
    assert isinstance(build['exception_tb'], TracebackInfo)

    # todo: check the TracebackInfo object


def test_nonserializable_objects():
    """
    Test the "NonSerializableObject" used in
    test_build_failure_due_to_nonserializable_object()
    """

    nso = NonSerializableObject()
    with pytest.raises(Exception):
        pickle.dumps(nso)

    nse = NonSerializableException()
    with pytest.raises(Exception):
        pickle.dumps(nse)


def test_build_failure_due_to_nonserializable_object(storage):
    config = JobControlConfig.from_string("""
    jobs:
        - id: job-nso
          function: jobcontrol.utils.testing:job_returning_nonserializable
    """)
    jc = JobControl(storage=storage, config=config)

    job = jc.get_job('job-nso')
    build = job.create_build()
    build.run()

    assert build['started']
    assert build['finished']
    assert not build['success']

    assert isinstance(build['exception'], SerializationError)
    assert (  # The original exception message is kept..
        "TypeError('a class that defines __slots__ without defining "
        "__getstate__ cannot be pickled',)") in build['exception'].message


def test_build_failure_nonserializable_exception(storage):
    """
    It only gets worse when we cannot even serialize the exception..
    But still, we can wrap it in a serialization error exception
    and be fine with it. Hopefully, we can keep the original traceback..
    """

    config = JobControlConfig.from_string("""
    jobs:
        - id: job-nse
          function: jobcontrol.utils.testing:job_raising_nonserializable
    """)
    jc = JobControl(storage=storage, config=config)

    # Run build for RAISE nonserializable
    # It should just fail with an exception in the post-run serialization
    # todo: We might even check the traceback for that..

    job = jc.get_job('job-nse')
    build = job.create_build()
    build.run()

    assert build['started']
    assert build['finished']
    assert not build['success']

    # WARNING! How to tell whether this job failed due to
    # the raised exception being serialized properly, or due
    # to the exception serialization failed?

    assert not isinstance(build['exception'], NonSerializableException)
    assert isinstance(build['exception'], ExceptionPlaceholder)
