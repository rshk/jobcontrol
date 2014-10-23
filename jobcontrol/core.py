"""
Core objects
"""

from datetime import timedelta
import logging

from jobcontrol.globals import _execution_ctx_stack


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
        job = self.storage.job_get(job_id)

        if job is None:
            raise RuntimeError("No such job: {0}".format(job_id))

        build_id = self.storage.create_build(job_id)

        ctx = JobExecutionContext(app=self, job_id=job_id, build_id=build_id)

        # Check that dependencies are built

        # Build job

        # Check depending are built
        pass

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
        current_app.storage.log_message(
            job_id=execution_context.job_id,
            build_id=execution_context.build_id,
            record=record)

# Note: we need just *one* handler -> create here
