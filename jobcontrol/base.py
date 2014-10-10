"""
Base interface for job control main class
"""

from datetime import datetime
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

    def job_create(self, function, args=None, kwargs={}, dependencies=None):
        job_id = self._job_create(
            function=function, args=args or (), kwargs=kwargs or {},
            dependencies=dependencies)
        return JobDefinition(self, job_id=job_id)

    @abc.abstractmethod
    def _job_create(self, function, args, kwargs, dependencies=None):
        pass

    def job_read(self, job_id):
        return JobDefinition(self, job_id=job_id)

    @abc.abstractmethod
    def _job_read(self, job_id):
        pass

    @abc.abstractmethod
    def _job_update(self, job_id, function=None, args=None, kwargs=None,
                    dependencies=None):
        pass

    @abc.abstractmethod
    def _job_delete(self, job_id):
        pass

    def job_iter(self):
        for job_id in self._job_iter():
            yield JobDefinition(self, job_id=job_id)

    @abc.abstractmethod
    def _job_iter(self):
        pass

    # ------------------------------------------------------------
    # Job run CRUD

    @abc.abstractmethod
    def _job_run_create(self, job_id):
        pass

    @abc.abstractmethod
    def _job_run_read(self, job_run_id):
        pass

    @abc.abstractmethod
    def _job_run_update(self, job_run_id, finished=None, success=None,
                        progress_current=None, progress_total=None,
                        retval=None):
        pass

    @abc.abstractmethod
    def _job_run_delete(self, job_run_id):
        pass

    @abc.abstractmethod
    def _job_run_iter(self, job_id):
        pass

    # ------------------------------------------------------------
    # Actual job execution wrapper method

    def execute_job(self, job_id):
        """
        Wrapper for job execution.

        - Initializes (global) context for job execution
        - Sets up the logger to capture logs during the task execution
        - Runs the task and updates status accordingly
        """

        job_def = self._job_read(job_id)

        if job_def is None:
            raise RuntimeError("No such job: {0}".format(job_id))

        context = JobExecutionContext()
        context.app = self
        context.config = self.config

        job_run_id = self._job_run_create(job_id)
        context.job_id = job_id
        context.job_run_id = job_run_id
        context.push()

        handler = self.create_log_handler(job_id, job_run_id)
        if handler is not None:
            root_logger = logging.getLogger('')
            root_logger.addHandler(handler)

        job_run_info = {
            'finished': True,
            'retval': None,
        }

        try:
            function = self._get_function(job_def['function'])
            args = job_def['args']
            kwargs = job_def['kwargs']

            retval = function(*args, **kwargs)

        except Exception:  # anything will get logged
            logger.exception('Task failed with an exception.')
            job_run_info.update({
                'success': False,
            })

        else:
            job_run_info.update({
                'success': True,
                'retval': retval,
            })

        finally:
            # Pop the context from the stack
            context.pop()

            if handler is not None:
                root_logger.removeHandler(handler)

        self._job_run_update(job_run_id, **job_run_info)
        return JobRunStatus(self, job_run_id=job_run_id)

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

    def _iter_logs(self, job_run_id):
        # Simulate a generator..
        for x in ():
            yield None

    # ------------------------------------------------------------
    # To be accessed from task run context

    def get_current_job(self):
        from jobcontrol.globals import execution_context
        return self.job_read(execution_context.job_id)

    def get_current_job_run(self):
        from jobcontrol.globals import execution_context
        return JobRunStatus(self, job_run_id=execution_context.job_run_id)


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
    def __init__(self, app, job_id):
        self._app = app
        self._job_id = job_id
        self._updates = {}

    job_id = property(lambda x: x._job_id)

    @cached_property
    def dependencies(self):
        if self._record['dependencies'] is None:
            return []
        return [JobDefinition(self._app, job_id)
                for job_id in self._record['dependencies']]

    @cached_property
    def _record(self):
        return self._app._job_read(self.job_id)

    def __getitem__(self, name):
        if name in self._updates:
            return self._updates[name]
        return self._record[name]

    def __setitem__(self, name, value):
        self._updates[name] = value

        if name == 'finished' and value:
            self._updates['end_date'] = datetime.now()

    def __delitem(self, name):
        self._updates.pop(name, None)

    def save(self):
        self._app._job_update(self.job_id, **self._updates)
        self.refresh()

    def refresh(self):
        # Will get refreshed next time property is accessed
        self._updates.clear()
        self.__dict__.pop('_record', None)
        self.__dict__.pop('dependencies', None)

    def delete(self):
        return self._app._job_delete(self._job_id)

    def iter_runs(self):
        return (
            JobRunStatus(self._app, job_run_id=x)
            for x in self._app._job_run_iter(self._job_id))

    def run(self):
        return self._app.execute_job(self._job_id)

    def run_async(self):
        raise NotImplementedError('run_async() is not implemented yet')


class JobRunStatus(object):
    def __init__(self, app, job_run_id):
        self._app = app
        self._job_run_id = job_run_id
        self._updates = {}

    job_run_id = property(lambda x: x._job_run_id)

    def get_info(self):
        return self._app._job_run_read(self.job_run_id)

    def delete(self):
        return self._app._job_delete(self._job_id)

    @cached_property
    def job_id(self):
        return self.get_info()['job_id']

    def is_started(self):
        return self.get_info()['started']

    def is_finished(self):
        return self.get_info()['finished']

    def is_successful(self):
        return self.get_info()['success']

    def get_result(self):
        return self.get_info()['retval']

    def get_progress(self):
        info = self.get_info()
        return info['progress_current'], info['progress_total']

    def set_progress(self, current=None, total=None):
        from jobcontrol.globals import execution_context
        if execution_context.job_run_id != self._job_run_id:
            raise RuntimeError("Cannot set progress for non-current task!")
        self._app._job_run_update(
            self._job_run_id,
            progress_current=current,
            progress_total=total)

    def get_log_messages(self):
        return self._app._iter_logs(self._job_run_id)
