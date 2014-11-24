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

import abc
import pickle

import jobcontrol.job_conf
# from jobcontrol.exceptions import NotFound


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
    # Helper methods for serialization
    # Todo: should we create custom methods to serialize
    #       args, kwargs, exceptions, log records, ... ?
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
    # More helper methods
    # ------------------------------------------------------------

    def _generate_job_id(self):
        import uuid
        return str(uuid.uuid4())

    # ------------------------------------------------------------
    # Job CRUD methods
    # ------------------------------------------------------------

    # @abc.abstractmethod
    # def create_job(self, job_id=None, function=None, args=None, kwargs=None,
    #                dependencies=None, title=None, notes=None, config=None):
    #     """
    #     Create a new job.

    #     :param job_id:
    #         (mandatory) the job "name" (natural key identifier; must be unique;
    #         avoid exceeding a "reasonable" length).
    #     :param function:
    #         Function to be called to run the job
    #     :param args:
    #         A tuple containing positional arguments.
    #         :py:class:`jobcontrol.job_config.Retval` objects may be used
    #         to indicate references to dependency job builds return values.
    #     :param kwargs:
    #         A dictionary containing keyword arguments. Can use Retvals as well.
    #     :param dependencies:
    #         A list of dependency job names.
    #     :param title:
    #         An optional title for the job.
    #     :param notes:
    #         Optional notes for the job.
    #     :param config:
    #         Optionally, a configuration block (dict), reflecting the
    #         structure to be stored in the database.
    #         It must be possible to serialize this as YAML, of course.
    #     :return:
    #         The id of the newly created job
    #     """
    #     pass

    # @abc.abstractmethod
    # def update_job(self, job_id, function=None, args=None, kwargs=None,
    #                dependencies=None, title=None, notes=None, config=None):
    #     """
    #     Update a job definition.

    #     Arguments meanings are the same of ``create_job()``.
    #     Returns nothing.
    #     """
    #     pass

    # def _make_config(self, job_id, function, args, kwargs, dependencies, title,
    #                  notes, config=None):
    #     """Utility function to merge arguments into configuration"""

    #     _config = {
    #         'id': None,
    #         'function': None,
    #         'args': (),
    #         'kwargs': {},
    #         'dependencies': [],
    #         'title': None,
    #         'notes': None,
    #     }

    #     if config is not None:
    #         _config.update(config)

    #     if job_id is not None:
    #         _config['id'] = job_id

    #     if function is not None:
    #         _config['function'] = function

    #     if args is not None:
    #         _config['args'] = args

    #     if kwargs is not None:
    #         _config['kwargs'] = kwargs

    #     if dependencies is not None:
    #         _config['dependencies'] = dependencies

    #     if title is not None:
    #         _config['title'] = title

    #     if notes is not None:
    #         _config['notes'] = notes

    #     return _config

    # @abc.abstractmethod
    # def get_job(self, job_id):
    #     """Get a job definition, as a dict, by id"""
    #     pass

    # @abc.abstractmethod
    # def delete_job(self, job_id):
    #     """Delete a job definition, by id"""
    #     pass

    # @abc.abstractmethod
    # def list_jobs(self):
    #     """List IDs of all jobs"""
    #     pass

    # def iter_jobs(self):
    #     """Iterate all jobs, yielding them as dicts"""
    #     for id in self.list_jobs():
    #         yield self.get_job(id)

    # def mget_jobs(self, job_ids):
    #     """
    #     Get multiple job definitions, by id(s).

    #     Especially useful for getting dependencies.

    #     .. note::

    #         The default implementation just falls back to getting the jobs
    #         one by one, which will work, but will usually be sub-optimal.

    #     :param job_ids: A list of job ids.
    #     """
    #     return list(self.miter_jobs(job_ids))

    # def miter_jobs(self, job_ids):
    #     for job_id in job_ids:
    #         try:
    #             yield self.get_job(job_id)
    #         except NotFound:
    #             pass

    # @abc.abstractmethod
    # def get_job_deps(self, job_id):
    #     """Get ids of direct job dependencies"""
    #     pass

    # @abc.abstractmethod
    # def get_job_revdeps(self, job_id):
    #     """Get ids of jobs directly depending on this one"""
    #     pass

    @abc.abstractmethod
    def get_job_builds(self, job_id, started=None, finished=None,
                       success=None, skipped=None, order='asc', limit=100):
        """
        Get all the builds for a job, sorted by date, according
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
        """
        pass

    # ------------------------------------------------------------
    # Build CRUD methods
    # ------------------------------------------------------------

    @abc.abstractmethod
    def create_build(self, job_id, build_config=None):
        """
        Create a build.

        :param job_id:
            The job for which a build should be started

        :param build_config:
            Build configuration, containing things like dependency build
            pinning, etc.
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
    def log_message(self, job_id, build_id, record):
        """
        Store a log record associated with a build.
        """
        # Todo: provide "shortcut" methods to convert the traceback to
        #       a serializable object, and to clean up the record
        #       object for decent serialization in the database.
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
    def iter_log_messages(self, job_id=None, build_id=None, max_date=None,
                          min_date=None, min_level=None):
        """
        Iterate over log messages, applying some filters.

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
