"""
Base interface for job control main class
"""

from datetime import datetime, timedelta
import pickle
import logging

import abc

from jobcontrol.globals import _execution_ctx_stack
from jobcontrol.utils import cached_property


logger = logging.getLogger('jobcontrol')


class JobControlBase(object):
    __metaclass__ = abc.ABCMeta

    def __init__(self, config):
        self.config = config

    # ------------------------------------------------------------
    # Install / uninstall methods

    def install(self):
        pass

    def uninstall(self):
        pass

    # ------------------------------------------------------------
    # Helper methods

    def pack(self, obj):
        return pickle.dumps(obj)

    def unpack(self, obj):
        return pickle.loads(obj)

    # ------------------------------------------------------------
    # Job definition CRUD

    @abc.abstractmethod
    def define_job(self, function, args, kwargs, dependencies=None):
        pass

    @abc.abstractmethod
    def get_job_definition(self, job_id):
        pass

    @abc.abstractmethod
    def undefine_job(self, job_id):
        pass

    @abc.abstractmethod
    def iter_jobs(self):
        pass

    # ------------------------------------------------------------
    # Job definition CRUD

    @abc.abstractmethod
    def create_job_run(self, job_id):
        """Create a record holding information for the current job run"""
        pass

    @abc.abstractmethod
    def get_job_run_info(self, job_run_id):
        pass

    @abc.abstractmethod
    def update_job_run(self, job_run_id, finished=None, success=None,
                       progress_current=None, progress_total=None,
                       retval=None):
        pass

    @abc.abstractmethod
    def delete_job_run(self, job_run_id):
        pass

    # ------------------------------------------------------------
    # Actual job execution wrapper method

    def run_job(self, job_id):
        """
        Wrapper for job execution.

        - Initializes (global) context for job execution
        - Sets up the logger to capture logs during the task execution
        - Runs the task and updates status accordingly
        """

        job_def = self.get_job_definition(job_id)

        if job_def is None:
            raise RuntimeError("No such job: {0}".format(job_id))

        context = JobExecutionContext()
        context.app = self
        context.config = self.config

        job_run_id = self._create_job_run()
        context.job_id = job_id
        context.job_run_id = job_run_id

        handler = self.create_log_handler(job_id, job_run_id)
        if handler is not None:
            root_logger = logging.getLogger('')
            root_logger.addHandler(handler)

        try:
            function = self._get_function(job_def['function'])
            args = pickle.loads(job_def['args'])
            kwargs = pickle.loads(job_def['kwargs'])

            retval = function(*args, **kwargs)

        except Exception:  # anything will get logged
            logger.exception('Task failed with an exception.')
            job_run_info = {
                'finished': True,
                'success': False,
                'retval': None,
            }

        else:
            job_run_info = {
                'finished': True,
                'success': True,
                'retval': retval,
            }

        finally:
            # Pop the context from the stack
            context.pop()

            self.update_job_run(job_run_id, **job_run_info)

            if handler is not None:
                root_logger.removeHandler(handler)

    # ------------------------------------------------------------
    # Utility

    def create_log_handler(self, job_id, job_run_id):
        """
        Return a log handler to be added to root logger
        during task execution.
        """
        pass

    def _get_function(self, name):
        """Get a function from a module, by name"""

        module_name, function_name = name.split(':')
        module = __import__(module_name, fromlist=[function_name])
        return getattr(module, function_name)


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


class JobDefinition(object):
    def __init__(self, app, row):
        self._app = app
        self._row = row

    ctime = property(
        lambda self: self._row['ctime'])
    function = property(
        lambda self: self._row['function'])
    args = cached_property(
        lambda self: self._app.unpack(self._row['args']))
    kwargs = cached_property(
        lambda self: self._app.unpack(self._row['kwargs']))

    @cached_property
    def dependencies(self):
        for job_id in self._row['dependencies']:
            yield self._app.get_job_definition(job_id)


class JobRunStatus(object):
    pass
