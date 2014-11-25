"""
Interfaces for NEW jobcontrol objects.

**Data model**::

    Build   id SERIAL
    -----   job_id TEXT
            start_time TIMESTAMP
            end_time TIMESTAMP
            started BOOLEAN
            finished BOOLEAN
            success BOOLEAN
            skipped BOOLEAN
            job_config TEXT (YAML)
                Copy of the job configuration whan the build was started
            build_config TEXT (YAML)
                Extra configuration, such as dependency build "pinning"
            retval BINARY (Pickled return value)
            exception BINARY
                Pickled exception object (or None)
            exception_tb BINARY
                Pickled TracebackInfo object

    Build progress
    --------------
            build_id INTEGER (references Build.id)
            group_name VARCHAR(128)
                Name of the "progress group" (separated by '::')
            current INTEGER
                Current progress value
            total INTEGER
                Total progress value
            status_line TEXT
                An optional line of text describing current state
            UNIQUE constraint on (build_id, group_name)

    Log     id SERIAL
    ---     build_id INTEGER (references Build.id)
            created TIMESTAMP
            level INTEGER
            record BINARY
                Pickled LogRecord
            exception_tb BINARY
                Pickled TracebackInfo object


**Job configuration:**

The job configuration is stored as a YAML-serialized dict.

Recognised keys are:

- ``function`` in ``module:function`` format, specify the function to be called
- ``args`` a list of arguments to be passed to the function
- ``kwargs`` a dict of keyword arguments to be passed to the function
- ``title`` a descriptive title, to be shown on the interfaces
- ``notes`` notes, to be shown in interfaces (in restructured text)
- ``dependencies`` list of dependency job names

Additionally, args/kwargs may contain references to return value of dependency
builds, by using the ``!retval <name>`` syntax.


**Exception traceback serialization**

To be used both in build records and associated with log messages containing
an exception.

We want to include the following information:

- Details about the call stack, as in normal tracebacks: filename, line
  number, function name, line of code (plus some context)
- Local variables: we are not guaranteed we can safely pickle / unpickle
  arbitrary values; moreover this might result in huge fields, etc.
  So our better chance is to just store a dictionary mapping names
  to repr()s of the values (trimmed to a -- large -- maximum length,
  just to be on the safe side).
"""

from datetime import datetime
import abc
import pickle
import warnings

import jobcontrol.job_conf


class StorageBase(object):
    __metaclass__ = abc.ABCMeta

    def __init__(self):
        pass

    @classmethod
    def from_url(cls, url):
        raise NotImplementedError('')

    # ------------------------------------------------------------
    # Installation methods.
    # For resource initialization, if needed.
    # ------------------------------------------------------------

    def install(self):
        pass

    def uninstall(self):
        pass

    # ------------------------------------------------------------
    # Build CRUD methods
    # ------------------------------------------------------------

    @abc.abstractmethod
    def get_job_builds(self, job_id, started=None, finished=None,
                       success=None, skipped=None, order='asc', limit=100):
        """
        Iterate over all the builds for a job, sorted by date, according
        to the order specified by ``order``.

        :param job_id:
            The job id
        :param started:
            If set to a boolean, filter on the "started" field
        :param finished:
            If set to a boolean, filter on the "finished" field
        :param success:
            If set to a boolean, filter on the "success" field
        :param skipped:
            If set to a boolean, filter on the "skipped" field
        :param order:
            'asc' (default) or 'desc'
        :param limit:
            only return the first ``limit`` builds

        :yield: Dictionaries representing build information
        """
        pass

    @abc.abstractmethod
    def create_build(self, job_id, job_config, build_config):
        """
        Create a build.

        :param job_id:
            The job for which a build should be started

        :param job_config:
            The job configuration ``(function, args, kwargs, ..)``
            to be copied inside the object (we will use this from now on).

        :param build_config:
            Build configuration, containing things like dependency build
            pinning, etc.

            - ``dependency_builds``: dict mapping job ids to build ids,
              or ``None`` to indicate "create a new build" for this job.

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
                     exception=None, exc_info=None):
        """
        Register a build execution end.
        """
        pass

    def finish_build_with_exception(self, build_id):
        # todo: build a tracebackinfo object
        # todo: return finish_build() with failure + exception trace
        raise NotImplementedError

    def update_build_progress(self, build_id, current, total):
        warnings.warn(DeprecationWarning(
            'The update_build_progress() method is deprecated. '
            'Use report_build_progress() instead.'))
        return self.report_build_progress(build_id, current, total)

    @abc.abstractmethod
    def report_build_progress(self, build_id, current, total, group_name='',
                              status_line=''):
        """
        Report progress for a build.

        :param build_id:
            The build id for which to report progress
        :param current:
            The current number of "steps" done
        :param total:
            The total amount of "steps"
        :param group_name:
            Optionally, a name used to nest multiple progress "levels".
            A tuple (or string separated by '::' can be used to specify
            multiple "nesting" levels)
        :param status_line:
            Optionally, a line of text indicating the current build status.
        """
        pass

    def get_latest_successful_build(self, job_id):
        """
        Helper method to retrieve the latest successful build for a given
        job. Calls ``get_job_builds()`` in the background.

        :return: information about the build, as a dict
        """
        builds = list(self.get_job_builds(
            job_id, started=True, finished=True, success=True, skipped=False,
            order='desc', limit=1))
        if len(builds) < 1:
            return None  # No build!
        assert len(builds) == 1  # Or something is broken..
        return builds[0]

    @abc.abstractmethod
    def log_message(self, build_id, record):
        """
        Store a log record associated with a build.
        """
        # Todo: provide "shortcut" methods to convert the traceback
        #       (from exc_info) to a serializable object, and to clean
        #       up the record object for decent serialization in the
        #       database.
        pass

    @abc.abstractmethod
    def prune_log_messages(self, job_id=None, build_id=None, max_age=None,
                           level=None):
        """
        Delete (old) log messages.

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
    def iter_log_messages(self, build_id=None, max_date=None,
                          min_date=None, min_level=None):
        """
        Iterate over log messages, applying some filters.

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

    # ------------------------------------------------------------
    # Helper methods for serialization
    # ------------------------------------------------------------

    def pack(self, obj):
        return pickle.dumps(obj)

    def unpack(self, obj, safe=False):
        try:
            return pickle.loads(obj)
        except Exception as e:
            if not safe:
                raise
            return 'Error deserializing object: {0!r}'.format(e)

    def yaml_pack(self, obj):
        return jobcontrol.job_conf.dump(obj)

    def yaml_unpack(self, obj):
        return jobcontrol.job_conf.load(obj)

    # ------------------------------------------------------------
    # Generic helper methods
    # ------------------------------------------------------------

    def _normalize_job_config(self, job_conf):
        if not isinstance(job_conf, dict):
            raise TypeError('job_conf must be a dict')

        job_conf.setdefault('function', None)
        job_conf.setdefault('args', ())
        job_conf.setdefault('kwargs', {})

        if isinstance(job_conf['args'], list):
            job_conf['args'] = tuple(job_conf['args'])

        if not isinstance(job_conf['args'], tuple):
            raise TypeError('args must be a tuple')

        if not isinstance(job_conf['kwargs'], dict):
            raise TypeError('kwargs must be a dict')

        job_conf.setdefault('dependencies', [])
        if not isinstance(job_conf['dependencies'], (list, tuple)):
            raise TypeError('dependencies must be a list (or tuple)')

        return job_conf

    def _normalize_build_config(self, build_conf):
        if not isinstance(build_conf, dict):
            raise TypeError('build_conf must be a dict')

        build_conf.setdefault('dependency_builds', {})

        return build_conf

    def _normalize_build_info(self, build_info):
        if not isinstance(build_info, dict):
            raise TypeError('build_info must be a dict')

        build_info.setdefault('job_id', None)

        for key in ('start_time', 'end_time'):
            build_info.setdefault(key, None)

        for key in ('started', 'finished', 'success', 'skipped'):
            build_info.setdefault(key, False)

        build_info.setdefault('job_config', {})
        build_info['job_config'] = \
            self._normalize_job_config(build_info['job_config'])

        build_info.setdefault('build_config', {})
        build_info['build_config'] = \
            self._normalize_build_config(build_info['build_config'])

        for key in ('retval', 'exception', 'exception_tb'):
            build_info.setdefault(key, None)

        for key in ('title', 'notes'):
            build_info.setdefault(key, None)

        return build_info

    def _serialize_log_record(self, record):
        from jobcontrol.utils import TracebackInfo

        row = {
            'record': record,
            'created': datetime.utcfromtimestamp(record.created),
            'exception_tb': None,
        }

        if record.exc_info:
            etype, exc, tb = record.exc_info
            record.exc_info = (etype, exc, None)
            row['exception_tb'] = TracebackInfo.from_tb(tb)

        return row
