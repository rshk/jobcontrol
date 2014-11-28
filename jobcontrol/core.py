"""
Objects responsible for JobControl core functionality.

.. note::

    Important objects from this module should be imported in
    main __init___, in order to "abstract away" the namespace
    and have them in a more nicely accessible place.
"""

from datetime import timedelta
import inspect
import logging
import sys
import warnings

from flask import escape

from jobcontrol.globals import _execution_ctx_stack
from jobcontrol.exceptions import MissingDependencies, SkipBuild, NotFound
from jobcontrol.utils import import_object, cached_property
from jobcontrol.utils.depgraph import resolve_deps
from jobcontrol.job_conf import JobControlConfigMgr

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
    """The main JobControl class"""

    def __init__(self, storage, config):
        self.storage = storage

        if not isinstance(config, JobControlConfigMgr):
            config = JobControlConfigMgr(config)
        self.config = config

    @classmethod
    def from_config_file(cls, config_file):
        """
        Initialize JobControl by loading configuration from a file.
        Will also initialize storage taking values from the configuration.
        """

        config = JobControlConfigMgr.from_file(config_file)
        obj = cls(storage=config.get_storage(), config=config)
        return obj

    @classmethod
    def from_config(cls, config):
        """
        Initialize JobControl from some configuration.

        :param config:
            Either a :py:class:`jobcontrol.job_conf.JobControlConfigMgr`
            instance, or a dict to be passed as argument to constructor.

        :return:
            a :py:class:`JobControl` instance
        """

        if not isinstance(config, JobControlConfigMgr):
            config = JobControlConfigMgr(config)
        obj = cls(storage=config.get_storage(), config=config)
        return obj

    def get_job(self, job_id):
        """
        Get a job, by id.

        :param job_id: The job id
        :return:
            a :py:class:`JobInfo` class instance associated with the
            requested job.
        """

        job_cfg = self.config.get_job(job_id)
        if job_cfg is None:
            raise NotFound('No such job: {0!r}'.format(job_id))
        return JobInfo(self, job_id, config=job_cfg)

    def iter_jobs(self):
        """
        Generator yielding all the jobs, one by one.

        :yields:
            for each job, a :py:class:`JobInfo` class instance associated
            with the job.
        """

        for job in self.config.iter_jobs():
            yield JobInfo(self, job['id'], config=job)

    def get_build(self, build_id):
        """
        Get a build, by id.

        :return: a :py:class:`BuildInfo` instance.
        """

        build = BuildInfo(self, build_id)
        build.refresh()  # To get 404 early..
        return build

    def create_build(self, job_id):
        """
        Create a build from a job configuration.

        Currently, we require that all the dependencies have already
        been built; in the future, it will be possible to build them
        automatically.

        Also, current implementation doesn't allow for customizations
        to either the job configuration nor the build one (pinning,
        dep/revdep building, ...).

        :param job_id:
            Id of the job for which to start a build
        :return: a :py:class:`BuildInfo` instance.
        """

        job = self.get_job(job_id)
        build_config = {
            'build_deps': False,
            'build_revdeps': False,
            'dependency_builds': {},
        }

        # Make sure all dependencies have a successful build.
        # Otherwise, raise an exception to abort everything.

        for dep in job.get_deps():
            assert isinstance(dep, JobInfo)

            dep_build = dep.get_latest_successful_build()
            if not dep_build:
                raise MissingDependencies(
                    'Dependency job {0!r} has no successful builds!')

            build_config['dependency_builds'][dep.id] = dep_build.id

        # Actually create a record for this build
        build_id = self.storage.create_build(
            job_id=job_id, job_config=job.config, build_config=build_config)

        return self.get_build(build_id)

    def build_job(self, job_id):
        """
        Create and run a new build for the specified job
        """
        build = self.create_build(job_id)
        return self.run_build(build)

    def run_build(self, build_id):
        """
        Actually run a build.

        - take the build configuration
        - make sure all the dependencies are built
        - take return values from the dependencies -> pass as arguments
        - run the build
        - build the reverse dependencies as well, if required to do so

        :param build_id: either a :py:class:`BuildInfo` instance, or a build id
        """

        if isinstance(build_id, BuildInfo):
            build = build_id
            build_id = build_id.id

        else:
            build = BuildInfo(app=self, build_id=build_id)

        build.refresh()  # Make sure we have up-to-date information

        # Make sure the log handler is installed
        self._install_log_handler()

        # Actually run the build
        self._run_build(build)

    def _run_build(self, build):
        from jobcontrol.job_conf import prepare_args

        logger.info('Starting execution of job {0} / build {1}'
                    .format(build.job_id, build.id))

        log_prefix = '[job: {0}, build: {1}] '.format(build.job_id, build.id)

        # Mark the build as started
        self.storage.start_build(build.id)

        # Create and push the global context
        ctx = JobExecutionContext(
            app=self, job_id=build.job_id, build_id=build.id)
        ctx.push()

        # note: from now on, we must make sure the context is popped
        #       no matter what -> no risky code must be executed outside
        #       the "try" block below.

        try:
            function = self._get_runner_function(build.job_config['function'])
            logger.debug(log_prefix + 'Function is {0!r}'.format(function))

            args = prepare_args(build.job_config['args'], build)
            kwargs = prepare_args(build.job_config['kwargs'], build)

            # Run!
            retval = function(*args, **kwargs)

            # todo: what if the function is a generator? Should we iterate it
            #       or just leave it alone?

        except SkipBuild:
            logger.info(log_prefix + 'Build SKIPPED')

            # Indicates no need to build this..
            self.storage.finish_build(
                build.id, success=True, skipped=True, retval=None,
                exception=None)

        except Exception as exc:
            logger.exception(log_prefix + 'Build FAILED')

            self.storage.finish_build(
                build.id, success=False, skipped=False, retval=None,
                exception=exc, exc_info=sys.exc_info())

        else:
            logger.info(log_prefix + 'Build SUCCESSFUL')

            self.storage.finish_build(
                build.id, success=True, skipped=False, retval=retval,
                exception=None)

        finally:
            # POP context from the stack
            ctx.pop()

    def _create_job_depgraph(self, job_id, complete=False):
        processed = set()
        DEPGRAPH = {}

        def _explore_deps(jid):
            if jid in processed:
                # Already processed
                return

            # Early, to prevent infinite recursion
            processed.add(jid)

            DEPGRAPH[jid] = deps = list(self.config.get_job_deps(jid))

            for dep in deps:
                _explore_deps(dep)

            if complete:
                revdeps = list(self.config.get_job_revdeps(jid))

                for rdid in revdeps:
                    if rdid not in DEPGRAPH:
                        DEPGRAPH[rdid] = []
                    if jid not in DEPGRAPH[rdid]:
                        DEPGRAPH[rdid].append(jid)
                    _explore_deps(rdid)

        logger.debug('Building dependency graph for job {0}'.format(job_id))
        _explore_deps(job_id)

        return DEPGRAPH

    def _resolve_deps(self, depgraph, job_id):
        # Allow changing dependency resolution function
        return resolve_deps(depgraph, job_id)

    def _latest_successful_build_date(self, job_id):
        builds = list(self.storage.get_job_builds(
            job_id, started=True, finished=True, success=True, skipped=False,
            order='desc', limit=1))
        if len(builds) < 1:
            return None  # No build!
        return builds[0]['end_time']

    def _get_runner_function(self, name):
        if not isinstance(name, basestring):
            raise TypeError('Function name must be a string')
        if not name:
            raise ValueError('Cannot get function for empty name!')
        return import_object(name)

    def prune_logs(self, policy=None):
        if policy is None:
            policy = DEFAULT_LOG_RETENTION_POLICY

        for level in sorted(policy):
            max_age = policy[level]
            self.storage.prune_log_messages(max_age=max_age, leve=level)

    def _install_log_handler(self):
        _root_logger = logging.getLogger('')
        _root_logger.setLevel(logging.DEBUG)
        if _log_handler not in _root_logger.handlers:
            _root_logger.addHandler(_log_handler)

    # ------------------------------------------------------------
    # Reporting methods, which require an execution context
    # to be active.
    # ------------------------------------------------------------

    def report_progress(self, group_name, current, total, status_line=''):
        """
        Report progress for the currently running build.

        :param group_name:
            The report "group name": either a tuple representing
            the "path", or None for the top-level.

        :param current:
            Current progress

        :param total:
            Total progress

        :param status_line:
            An optional line of text, describing the currently running
            operation.
        """
        from jobcontrol.globals import execution_context as ctx

        self.storage.report_build_progress(
            build_id=ctx.build_id,
            group_name=group_name,
            current=current,
            total=total,
            status_line=status_line)


class JobExecutionContext(object):
    """
    Class to hold "global" context during job execution.

    This class can also act as a context manager for temporary
    context:

    .. code-block:: python

        with JobExecutionContext(app, job_id, build_id):
            pass # do stuff in an execution context

    :param app: The JobControl instance running jobs
    :param job_id: Id of the currently running job
    :param build_id: Id of the currently running build
    """

    def __init__(self, app, job_id, build_id):
        # Kwargs: app, job_id, build_id
        self.app = app
        self.job_id = job_id
        self.build_id = build_id

    def push(self):
        """Push this context in the global stack"""
        _execution_ctx_stack.push(self)

    def pop(self):
        """Pop this context from the global stack"""
        rv = _execution_ctx_stack.pop()
        assert rv is self, \
            'Popped wrong context: {0!r} instead of {1!r}'.format(rv, self)

    def __enter__(self):
        self.push()
        return self

    def __exit__(self, exc_type, exc_value, tb):
        self.pop()

    @property
    def current_app(self):
        """Returns the currently running app"""
        return self.app

    @cached_property
    def current_job(self):
        """
        Returns a :py:class:`JobInfo` instance associated with the
        currently running job.
        """
        return self.app.get_job(self.job_id)

    @cached_property
    def current_build(self):
        """
        Returns a :py:class:`BuildInfo` instance associated with the
        currently running build.
        """
        return self.app.get_build(self.build_id)


class JobControlLogHandler(logging.Handler):
    """
    Logging handler sending messages to the appropriate
    JobControl instance that will dispatch them to storage.
    """

    def __init__(self):
        super(JobControlLogHandler, self).__init__()

    def flush(self):
        """No-op, as we don't need to flush anything"""
        pass  # Nothing to flush!

    def emit(self, record):
        """
        "Emit" the log record (if there is an execution context, store
        the log record appropriately; otherwise, just ignore it).
        """
        from jobcontrol.globals import current_app, execution_context

        try:
            # If we have no build, do nothing.
            # Note that execution_context.build_id should raise an exception
            # itself, as there will not be any execution_context..
            if execution_context.build_id is None:
                raise RuntimeError()
        except:
            return

        # Replace traceback with text representation, as traceback
        # objects cannot be pickled
        # if record.exc_info is not None:
        #     tb = traceback.format_exception(*record.exc_info)
        #     record.exc_info = record.exc_info[0], record.exc_info[1], tb

        # NOTE: This will be done by the storage!

        current_app.storage.log_message(
            build_id=execution_context.build_id,
            record=record)


class JobInfo(object):
    """High-level interface to jobs"""

    def __init__(self, app, job_id, config):
        self.app = app
        self._job_id = job_id
        self._config = {
            'args': (),
            'kwargs': {},
            'function': None,
            'dependencies': [],
        }
        self._config.update(config)

    def __repr__(self):
        return '<Job {0!r}>'.format(self.id)

    @property
    def id(self):
        return self._job_id

    @property
    def config(self):
        return self._config

    def __getitem__(self, name):
        return self._config[name]

    def get_deps(self):
        """
        Iterate over jobs this job depends upon.

        :yields: :py:class:`JobInfo` instances
        """
        for dep_id in self.app.config.get_job_deps(self.id):
            dep = self.app.config.get_job(dep_id)
            yield JobInfo(self.app, dep['id'], config=dep)

    def get_revdeps(self):
        """
        Iterate over jobs depending on this one

        :yields: :py:class:`JobInfo` instances
        """
        for revdep_id in self.app.config.get_job_revdeps(self.id):
            revdep = self.app.config.get_job(revdep_id)
            yield JobInfo(self.app, revdep['id'], config=revdep)

    def iter_builds(self, *a, **kw):
        """
        Iterate over builds for this job.

        Accepts the same arguments as
        :py:meth:`jobcontrol.interfaces.StorageBase.get_job_builds`

        :yields: :py:class:`BuildInfo` instances
        """
        for build in self.app.storage.get_job_builds(self.id, *a, **kw):
            yield BuildInfo(self.app, build['id'], info=build)

    def get_builds(self, *a, **kw):
        """DEPRECATED alias for iter_builds()"""
        warnings.warn(DeprecationWarning(
            'The get_builds() method is deprecated. '
            'Use iter_builds() instead.'))
        return self.iter_builds(*a, **kw)

    # def create_build(self):
    #     # Meant for future usage, when builds will support .run()
    #     build_id = self.app.storage.create_build(self.job_id)
    #     return BuildInfo(self.app, build_id)

    def run(self):
        """
        Trigger run for this job (will automatically create
        a build, etc.)
        """
        return self.app.build_job(self.id)

    def get_latest_successful_build(self):
        """
        Get latest successful build for this job, if any.
        Otherwise, returns ``None``.
        """
        build = self.app.storage.get_latest_successful_build(self.id)
        if build is None:
            return None
        return BuildInfo(self.app, build['id'], info=build)

    def get_docs(self):
        """
        Get documentation for this job.
        """
        return self._get_job_docs()

    def get_conf_as_yaml(self):
        """
        Return the job configuration as serialized YAML, mostly
        for displaying on user interfaces.
        """
        from jobcontrol.job_conf import dump
        return dump(self.config)

    def has_builds(self):
        """
        Check whether this job has any build.
        """
        builds = list(self.get_builds(
            started=True, finished=True, order='desc', limit=1))
        return len(builds) >= 1

    def has_successful_builds(self):
        """
        Check whether this job has any successful build.
        """
        builds = list(self.get_builds(
            started=True, finished=True, success=True, skipped=False,
            order='desc', limit=1))
        return len(builds) >= 1

    def is_outdated(self):
        """
        Check whether any dependency has builds more recent than the newest
        build for this job.
        """
        latest_build = self.get_latest_successful_build()

        if not latest_build:
            return None  # Unknown (no build)

        for dep in self.get_deps():
            _build = dep.get_latest_successful_build()
            if _build is None:
                return None  # Unknown (no dep build) [error!]

            if _build['end_time'] > latest_build['end_time']:
                # dependency build is newer
                return True

        return False

    # todo: move all the docs / ... utilities outside this class
    #       -> maybe move to some "job config" class?
    #       -> we need them for the job_config in the build as well!

    def _get_job_docs(self):
        call_code = self._get_call_code()

        docs = {
            'call_code': call_code,
            'call_code_html': self._highlight_code_html(call_code),
        }

        try:
            func = import_object(self['function'])

        except Exception as e:
            docs['function_doc'] = escape(u"Error: {0!r}".format(e))

        else:
            docs['function_doc'] = self._format_function_doc(func)
            docs['function_argspec'] = self._get_function_argspec(func)
            docs['function_argspec_human'] = \
                self._make_human_argspec(docs['function_argspec'])

        try:
            docs['function_module'], docs['function_name'] = \
                self['function'].split(':')
        except:
            docs['function_module'] = '???'
            docs['function_name'] = self['function']

        return docs

    def _get_call_code(self):
        try:
            module, func = self['function'].split(':')
        except:
            return '# Invalid function: {0}'.format(self['function'])

        call_args = []
        for arg in self['args']:
            call_args.append(repr(arg))
        for key, val in sorted(self['kwargs'].iteritems()):
            call_args.append("{0}={1!r}".format(key, val))

        if len(call_args):
            _args = "\n    {1}".format(func, ",\n    ".join(call_args))
        else:
            _args = ""

        return "\n".join((
            "from {0} import {1}".format(module, func),
            "{0}({1})".format(func, _args)))

    def _highlight_code_html(self, code):
        from pygments import highlight
        from pygments.lexers import PythonLexer
        from pygments.formatters import HtmlFormatter
        return highlight(code, PythonLexer(), HtmlFormatter())

    def _format_function_doc(self, func):
        import inspect
        import docutils.core

        doc = inspect.getdoc(func)
        if doc is None:
            return 'No docstring available.'
        return docutils.core.publish_parts(doc, writer_name='html')['fragment']

    def _get_function_argspec(self, func):
        aspec = inspect.getargspec(func)

        if aspec.defaults is not None:
            optargs = zip(aspec.args[len(aspec.defaults):], aspec.defaults)
            reqargs = aspec.args[:-len(aspec.defaults)]
        else:
            optargs = []
            reqargs = aspec.args[:]

        # ============================================================ #
        #   Note:                                                      #
        # ============================================================ #
        #                                                              #
        # Terminology used by the AST is:                              #
        # - args -> positional arguments                               #
        # - keywords -> arguments with default values                  #
        # - startargs -> name of *args                                 #
        # - kwargs -> name of **kwargs                                 #
        #                                                              #
        # Terminology used by inspect is quite different;              #
        # - varargs -> *args                                           #
        # - keywords -> **kwargs                                       #
        # - args -> all the named arguments                            #
        # - defaults -> default values, for keyword arguments          #
        #                                                              #
        # Maybe we should use the AST terminology here, as it better   #
        # reflect the structure? (the bad part is the different        #
        # meaning of the "keywords" term here..)                       #
        #                                                              #
        # ============================================================ #

        return {
            'varargs': aspec.varargs,
            'keywords': aspec.keywords,
            'reqargs': reqargs,
            'optargs': optargs,
        }

    def _make_human_argspec(self, argspec):
        parts = []

        for arg in argspec['reqargs']:
            parts.append(arg)

        for arg, default in argspec['optargs']:
            parts.append('{0}={1!r}'.format(arg, default))

        if argspec['varargs']:
            parts.append('*' + argspec['varargs'])

        if argspec['keywords']:
            parts.append('**' + argspec['keywords'])

        return ', '.join(parts)


class BuildInfo(object):
    """
    High-level interface to builds.

    :param app:
        The JobControl instance this build was retrieved from
    :param build_id:
        The build id
    :param info:
        Optionally, this can be used to pre-populate the build
        information (useful, eg. if we are retrieving a bunch
        of builds from the database at once).
    """

    def __init__(self, app, build_id, info=None):
        self.app = app
        self.build_id = build_id
        self._info = None
        if info is not None:
            self._info = {}
            self._info.update(info)

    def __repr__(self):
        return '<Build {0} (job={1}, status={2})>'.format(
            self.build_id, self.job_id, self.descriptive_status)

    @property
    def id(self):
        """The build id"""
        return self.build_id

    @property
    def job_id(self):
        """The job id"""
        return self.info['job_id']

    @property
    def info(self):
        """
        Property used to lazily access the build attributes.

        Returns a dict with the following keys:

        - ``'id'``
        - ``'job_id'``
        - ``'start_time'``
        - ``'end_time'``
        - ``'started'``
        - ``'finished'``
        - ``'success'``
        - ``'skipped'``
        - ``'job_config'``
        - ``'build_config'``
        - ``'retval'``
        - ``'exception'``
        - ``'exception_tb'``
        """
        if getattr(self, '_info') is None:
            self.refresh()
        return self._info

    @property
    def job_config(self):
        """
        Property to access the job configuration.
        """
        return self.info['job_config']

    @property
    def build_config(self):
        """
        Property to access the build configuration.
        """
        return self.info['build_config']

    @property
    def descriptive_status(self):
        """
        Return a label describing the current status of the build.

        :returns:
          - ``'CREATED'`` if the build was not started yet
          - ``'RUNNING'`` if the build was started but did not finish
          - ``'SUCCESSFUL'`` if the build run with success
          - ``'SKIPPED'`` if the build was skipped
          - ``'FAILED'`` if the build execution failed
        """
        if not self['started']:
            return 'CREATED'
        if not self['finished']:
            return 'RUNNING'
        if self['success']:
            if self['skipped']:
                return 'SKIPPED'
            return 'SUCCESSFUL'
        return 'FAILED'

    def refresh(self):
        """Refresh the build status information from database"""
        self._info = self.app.storage.get_build(self.build_id)

    def __getitem__(self, name):
        # if name not in self.info:
        #     if name == 'progress_info':
        #         self._info['progress_info'] = self.get_progress_info()
        #         return self._info['progress_info']

        return self.info[name]

    def get_progress_info(self):
        """Get information about the build progress"""
        # ---------------------------------------------------------------- HERE
        return None
        raise NotImplementedError  # todo: use new progress objects

        # current = self.info['progress_current']
        # total = self.info['progress_total']

        # progress_info = {
        #     'current': current,
        #     'total': total,
        #     'percent': 0,
        #     'percent_human': 'N/A',
        #     'label': 'N/A',
        # }

        # if total != 0:
        #     ratio = current * 1.0 / total
        #     percent = ratio * 100
        #     progress_info['percent'] = percent
        #     progress_info['percent_human'] = format(percent, '.0f')
        #     progress_info['label'] = '{0}/{1} ({2:.0f}%)'.format(
        #         current, total, percent)

        #     hue = ratio * 120  # todo: use logaritmic scale?
        #     color = ''.join([
        #         format(int(x * 255), '02X')
        #         for x in colorsys.hsv_to_rgb(hue / 360.0, .8, .8)])
        #     progress_info['color'] = '#' + color

        # return progress_info

    def get_job(self):
        """Get a :py:class:`JobInfo` associated with this build's job"""
        return JobInfo(self.app, self.job_id)

    def delete(self):
        """Delete all information related to this build from database"""
        self.app.storage.delete_build(self.build_id)

    def run(self):
        """Calls run_build() on the main app for this build"""
        return self.app.run_build(self)

    def iter_log_messages(self, **kw):
        """
        Iterate over log messages for this build.

        Keywords are passed directly to the underlying ``iter_log_messages()``
        method of the storage.
        """
        return self.app.storage.iter_log_messages(build_id=self.build_id, **kw)


# We need just *one* handler -> create here
_log_handler = JobControlLogHandler()
_log_handler.setLevel(logging.DEBUG)
