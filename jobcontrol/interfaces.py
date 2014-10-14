"""
Interfaces for NEW jobcontrol objects.

**Data model**::

    Job     id SERIAL
    ---     function VARCHAR
            args TEXT (serialized)
            kwargs TEXT (serialized)
            ctime TIMESTAMP
            mtime TIMESTAMP
            dependecies INTEGER[] (references Job.id)

    Build   id SERIAL
    -----   job_id INTEGER (references Job.id)
            start_time TIMESTAMP
            end_time TIMESTAMP
            started BOOLEAN
            finished BOOLEAN
            success BOOLEAN
            skipped BOOLEAN
            progress_current INTEGER
            progress_total INTEGER
            retval TEXT (serialized)
            exception TEXT (serialized)

    Log     id SERIAL
    ---     job_id INTEGER (references Job.id)
            build_id INTEGER (references Build.id)
            created TIMESTAMP
            level TIMESTAMP
            record TEXT (serialized)
"""

from datetime import timedelta
import abc
import logging
import pickle

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

    def execute_job(self, job_id, build_deps=False, build_depending=False):
        job = self.storage.job_get(job_id)
        if job is None:
            raise RuntimeError("No such job: {0}".format(job_id))
        pass

    def prune_logs(self, policy=None):
        if policy is None:
            policy = DEFAULT_LOG_RETENTION_POLICY

        for level in sorted(policy):
            max_age = policy[level]
            self.storage.prune_log_messages(max_age=max_age, leve=level)


class StorageBase(object):
    __metaclass__ = abc.ABCMeta

    def __init__(self):
        # Does nothing in default implementation, but in others
        # migth get arguments / do stuff.
        pass

    # ------------------------------------------------------------
    # Installation methods.
    # For resource initialization, if needed.
    # ------------------------------------------------------------

    def install(self):
        pass

    def uninstall(self):
        pass

    # ------------------------------------------------------------
    # Helper methods for serialization
    # Todo: should we create custom methods to serialize
    #       args, kwargs, exceptions, log records, ... ?
    # ------------------------------------------------------------

    def pack(self, obj):
        return pickle.dumps(obj)

    def unpack(self, obj):
        return pickle.loads(obj)

    # ------------------------------------------------------------
    # Job CRUD methods
    # ------------------------------------------------------------

    @abc.abstractmethod
    def job_create(self, function, args, kwargs, dependencies=None):
        """
        Create a new job.

        :return: The job id
        """
        pass

    @abc.abstractmethod
    def job_update(self, job_id, function=None, args=None, kwargs=None,
                   dependencies=None):
        """
        Update a job definition.
        """
        pass

    @abc.abstractmethod
    def job_get(self, job_id):
        """
        Get a job definition, as a dict, by id.
        """
        pass

    @abc.abstractmethod
    def job_delete(self, job_id):
        """
        Delete a job definition, by id.
        """
        pass

    @abc.abstractmethod
    def job_list(self, job_id):
        """List IDs of all jobs"""
        pass

    def job_iter(self, job_id):
        """
        Iterate all jobs, yielding them as dicts.
        """
        for id in self.job_list():
            yield self.job_get(id)

    def job_mget(self, job_ids):
        """
        Get multiple job definitions, by id.

        Especially useful for getting dependencies.
        """
        return [self.job_get(x) for x in job_ids]

    @abc.abstractmethod
    def job_get_deps(self, job_id):
        """Get direct job dependencies"""
        pass

    @abc.abstractmethod
    def job_get_revdeps(self, job_id):
        """Get jobs directly depending on this one"""
        pass

    @abc.abstractmethod
    def job_get_builds(self, job_id, started=None, finished=None,
                       successful=None, skipped=None, order='asc', limit=100):
        """
        Get all the builds for a job, sorted by date, according
        to the order specified by ``order``.

        :param job_id:
            The job id
        :param started:
            If set to a boolean, filter on the "started" field
        :param finished:
            If set to a boolean, filter on the "finished" field
        :param successful:
            If set to a boolean, filter on the "successful" field
        :param skipped:
            If set to a boolean, filter on the "skipped" field
        :param order:
            'asc' (default) or 'desc'
        :param limit:
            only return the first ``limit`` builds
        """
        pass

    # ------------------------------------------------------------
    # Build CRUD methods
    # ------------------------------------------------------------

    @abc.abstractmethod
    def create_build(self, job_id):
        """
        Create a build.

        :return: the build id
        """
        pass

    @abc.abstractmethod
    def get_build(self, build_id):
        """
        Get information about a build.

        :return: the build information, as a dict
        """
        pass

    @abc.abstractmethod
    def delete_build(self, build_id):
        """
        Delete a build, by id.
        """
        pass

    @abc.abstractmethod
    def start_build(self, build_id):
        """
        Register a build execution start.
        """
        pass

    @abc.abstractmethod
    def finish_build(self, build_id, success=None, skipped=None, retval=None,
                     exception=None):
        """
        Register a build execution end.
        """
        pass

    @abc.abstractmethod
    def update_build_progress(self, build_id, current, total):
        """
        Update the current progress for a given build.
        """
        pass

    @abc.abstractmethod
    def log_message(self, job_id, build_id, record):
        """
        Store a log record for a build
        """
        pass

    @abc.abstractmethod
    def prune_log_messages(self, job_id=None, build_id=None, max_age=None,
                           level=None):
        """
        Delete old log messages.

        :param job_id:
            If specified, only delete messages for this job

        :param build_id:
            If specified, only delete messages for this build

        :param max_age:
            If specified, only delete log messages with an age
            greater than this one (in seconds)

        :param level:
            If specified, only delete log messages with a level
            equal or minor to this one
        """
        pass

    @abc.abstractmethod
    def iter_log_messages(self, job_id=None, build_id=None, max_date=None,
                          min_date=None, min_level=None):
        """
        Iterate log messages.

        :param job_id:
            If specified, only return messages for this job

        :param build_id:
            If specified, only return messages for this build

        :param max_date:
            If specified, only return messages newer than this date

        :param min_date:
            If specified, only return messages older than this date

        :param min_level:
            If specified, only return messages with a level at least
            equal to this one
        """
        pass


class JobExecutionContext(object):
    """
    Global context for job execution.
    """

    def __init__(self, **kwargs):
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
