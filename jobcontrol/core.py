"""
Core objects
"""

from datetime import timedelta
import logging

from jobcontrol.globals import _execution_ctx_stack
from jobcontrol.exceptions import MissingDependencies, SkipBuild
from jobcontrol.utils import import_object


logger = logging.getLogger('jobcontrol')


_secs = lambda **kw: timedelta(**kw).total_seconds()
_year = 365.25  # days in a year
_month = _year / 12  # days in a month


DEFAULT_LOG_RETENTION_POLICY = {
    logging.DEBUG: _secs(days=15),
    logging.INFO: _secs(days=_month),
    logging.WARNING: _secs(days=_month * 3),
    logging.ERROR: _secs(days=_month * 6),
    logging.CRITICAL: _secs(days=_month * 6),
    None: _secs(days=_year),  # Any level
}


class JobControl(object):
    """The main jobcontrol class"""

    def __init__(self, storage):
        self.storage = storage

    def build_job(self, job_id, build_deps=False, build_depending=False):
        logger.info('Starting build for job: {0}'.format(job_id))

        job = self.storage.get_job(job_id)

        if job is None:
            raise RuntimeError("No such job: {0}".format(job_id))

        build_id = self.storage.create_build(job_id)

        ctx = JobExecutionContext(app=self, job_id=job_id, build_id=build_id)
        ctx.push()

        # Check that dependencies are built

        dependencies = self.storage.get_job_deps(job_id)
        deps_not_met = []
        for dep in dependencies:
            lsbd = self._latest_successful_build_date(dep['id'])
            if lsbd is None:
                logger.warning('Dependency job {0} has no successful builds'
                               .format(dep['id']))
                deps_not_met.append(dep['id'])

        if len(deps_not_met):
            if build_deps:
                logger.info('Building dependencies')
                # todo: run builds for all the depending jobs; check
                #       build status -> fail on dep failure
                # todo: add some argument to tell how many times depending
                #       jobs should be retired?
                # todo: figure out some way to run dependency builds in
                #       parallel
                # todo: make sure we detect dependency loops, etc.

                for job_id in deps_not_met:
                    # NOTE: We still need to build depending jobs in case
                    # we were asked to do so, but only after the main job was
                    # built, otherwise we risk entering an infinite loop..
                    build_id = self.build_job(job_id, build_deps=build_deps,
                                              build_depending=False)

                    build = self.storage.get_build(build_id)
                    if (not build['success']) or build['skipped']:
                        raise MissingDependencies(
                            'Build failed for dependency job {0}'
                            .format(job_id))

            else:
                raise MissingDependencies(
                    'Jobs require building: {0}'
                    .format(', '.join(str(x) for x in deps_not_met)))

        # Build job

        self.storage.start_build(build_id)

        try:
            function = self._get_runner_function(job['function'])
            retval = function(*job['args'], **job['kwargs'])

        except SkipBuild:
            # Indicates no need to build this..
            self.storage.finish_build(
                build_id, success=True, skipped=True, retval=None,
                exception=None)

        except Exception as exc:
            self.storage.finish_build(
                build_id, success=False, skipped=False, retval=None,
                exception=exc)

        else:
            self.storage.finish_build(
                build_id, success=True, skipped=False, retval=retval,
                exception=None)

        # Check depending jobs are built...
        if build_depending:
            pass
        pass

        return build_id

    def _latest_successful_build_date(self, job_id):
        builds = list(self.storage.get_job_builds(
            job_id, started=True, finished=True, success=True, skipped=False,
            order='desc', limit=1))
        if len(builds) < 1:
            return None  # No build!
        return builds[0]['end_time']

    def _get_runner_function(self, name):
        return import_object(name)

    def prune_logs(self, policy=None):
        if policy is None:
            policy = DEFAULT_LOG_RETENTION_POLICY

        for level in sorted(policy):
            max_age = policy[level]
            self.storage.prune_log_messages(max_age=max_age, leve=level)


class JobExecutionContext(object):
    """
    Global context for job execution.
    """

    def __init__(self, **kwargs):
        # Kwargs: app, job_id, build_id
        self.__dict__.update(kwargs)

    def push(self):
        _execution_ctx_stack.push(self)

    def pop(self):
        rv = _execution_ctx_stack.pop()
        assert rv is self, \
            'Popped wrong context: {0!r} instead of {1!r}'.format(rv, self)

    def __enter__(self):
        self.push()
        return self

    def __exit__(self, exc_type, exc_value, tb):
        self.pop()


class JobControlLogHandler(logging.Handler):
    """
    Logging handler sending messages to the appropriate
    JobControl instance that will dispatch them to storage.
    """

    def __init__(self):
        super(JobControlLogHandler, self).__init__()

    def flush(self):
        pass  # Nothing to flush!

    def emit(self, record):
        from jobcontrol.globals import current_app, execution_context

        try:
            # If we have no build, do nothing.
            # Note that execution_context.build_id should raise an exception
            # itself, as there will not be any execution_context..
            if execution_context.build_id is None:
                raise RuntimeError()
        except:
            return

        current_app.storage.log_message(
            job_id=execution_context.job_id,
            build_id=execution_context.build_id,
            record=record)

# We need just *one* handler -> create here
_log_handler = JobControlLogHandler()
_log_handler.setLevel(logging.DEBUG)
_root_logger = logging.getLogger('')
_root_logger.setLevel(logging.DEBUG)
_root_logger.addHandler(_log_handler)
