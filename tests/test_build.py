"""
Tests for builds
"""

from jobcontrol.core import JobControl
from jobcontrol.job_conf import JobControlConfigMgr


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
