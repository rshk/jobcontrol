"""
Core objects
"""

from datetime import timedelta
import logging

from jobcontrol.globals import _execution_ctx_stack
from jobcontrol.exceptions import MissingDependencies, SkipBuild
from jobcontrol.utils import import_object
from jobcontrol.utils.depgraph import resolve_deps

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

    def build_job(self, job_id, build_deps=False, build_depending=False,
                  _depth=0):

        # ------------------------------------------------------------
        # Get information about the job we want to build
        # ------------------------------------------------------------

        job = self.storage.get_job(job_id)
        if job is None:
            raise RuntimeError("No such job: {0}".format(job_id))

        # ------------------------------------------------------------
        # Build dependency graph for this job
        # ------------------------------------------------------------

        DEPGRAPH = {}

        def _explore_deps(jid):
            if jid in DEPGRAPH:
                # Already processed
                return

            deps = self.storage.get_job_deps(jid)
            DEPGRAPH[jid] = deps = [d['id'] for d in deps]
            for dep in deps:
                _explore_deps(dep)

        logger.debug('Building dependency graph for job {0}'.format(job_id))
        _explore_deps(job_id)

        logger.debug('Resolving dependencies for job {0}'.format(job_id))
        ORDERED_DEPS = self._resolve_deps(DEPGRAPH, job_id)

        SUCCESSFUL_BUILT_JOBS = []

        # ------------------------------------------------------------
        # Build jobs in order
        # ------------------------------------------------------------

        logger.debug('We need to build {0} targets'.format(len(ORDERED_DEPS)))
        for jid in ORDERED_DEPS:
            if (jid != job_id) and (
                    self.storage.get_latest_successful_build(jid) is not None):
                # No need to rebuild this..
                logger.info('Dependency {0} already built'
                            .format(jid))
                continue

            bid = self._build_job(jid)
            build = self.storage.get_build(bid)

            if build['success']:
                SUCCESSFUL_BUILT_JOBS.append((jid, bid))

            elif jid != job_id:
                raise MissingDependencies(
                    'Dependency build failed: job {0}, build {1}'
                    .format(jid, bid))

        # ------------------------------------------------------------
        # Rebuild reverse dependencies, if asked to do so
        # ------------------------------------------------------------
        # Todo: we need some way to detect infinite loops here as well!

        if build_depending:
            REVDEPS = set()

            for jid, bid in SUCCESSFUL_BUILT_JOBS:
                for item in self.storage.get_job_revdeps(jid):
                    REVDEPS.add(item['id'])

            REVDEPS = REVDEPS.difference(x[0] for x in SUCCESSFUL_BUILT_JOBS)

            logger.info('Building {0} reverse dependencies'
                        .format(len(REVDEPS)))

            for jid in REVDEPS:
                self.build_job(jid, build_deps=build_deps,
                               build_depending=build_depending)

        return dict(SUCCESSFUL_BUILT_JOBS)[job_id]

    def _resolve_deps(self, depgraph, job_id):
        # Allow changing dependency resolution function
        return resolve_deps(depgraph, job_id)

    def _build_job(self, job_id):
        """Actually run a build for this job"""

        job = self.storage.get_job(job_id)
        if job is None:
            raise RuntimeError('No such job: {0}'.format(job_id))

        logger.info('Starting build for job: {0}'.format(job_id))
        build_id = self.storage.create_build(job_id)

        log_prefix = '[job: {0}, build: {1}] '.format(job_id, build_id)

        ctx = JobExecutionContext(app=self, job_id=job_id, build_id=build_id)
        ctx.push()
        self.storage.start_build(build_id)

        try:
            function = self._get_runner_function(job['function'])
            logger.debug(log_prefix + 'Function is {0!r}'.format(function))

            retval = function(*job['args'], **job['kwargs'])

        except SkipBuild:
            logger.info(log_prefix + 'Build SKIPPED')

            # Indicates no need to build this..
            self.storage.finish_build(
                build_id, success=True, skipped=True, retval=None,
                exception=None)

        except Exception as exc:
            logger.exception(log_prefix + 'Build FAILED')

            self.storage.finish_build(
                build_id, success=False, skipped=False, retval=None,
                exception=exc)

        else:
            logger.info(log_prefix + 'Build SUCCESSFUL')

            self.storage.finish_build(
                build_id, success=True, skipped=False, retval=retval,
                exception=None)

        finally:
            ctx.pop()

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
