"""
Core objects
"""

from datetime import timedelta
import colorsys
import inspect
import logging
# import pkgutil
import sys
import traceback

from flask import escape

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

    def create_job(self, *a, **kw):
        return JobInfo.new(self, *a, **kw)

    def get_job(self, job_id):
        job = JobInfo(self, job_id)
        job.refresh()  # To get 404 early..
        return job

    def iter_jobs(self):
        for job in self.storage.iter_jobs():
            yield JobInfo(self, job['id'], info=job)

    def get_build(self, build_id):
        build = BuildInfo(self, build_id)
        build.refresh()  # To get 404 early..
        return build

    def build_job(self, job_id, build_deps=False, build_depending=False,
                  _depth=0):

        if isinstance(job_id, JobInfo):
            job_id = JobInfo.id

        self._install_log_handler()

        # ------------------------------------------------------------
        # Get information about the job we want to build
        # ------------------------------------------------------------

        job = self.storage.get_job(job_id)
        if job is None:
            raise RuntimeError("No such job: {0}".format(job_id))

        # ------------------------------------------------------------
        # Build dependency graph for this job
        # ------------------------------------------------------------

        DEPGRAPH = self._create_job_depgraph(job_id)

        logger.debug('Resolving dependencies for job {0}'.format(job_id))
        ORDERED_DEPS = self._resolve_deps(DEPGRAPH, job_id)

        SUCCESSFUL_BUILT_JOBS = []

        # ------------------------------------------------------------
        # Build jobs in order
        # ------------------------------------------------------------

        main_build_id = None

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

            if jid == job_id:
                main_build_id = bid

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

        return main_build_id

    def _create_job_depgraph(self, job_id, complete=False):
        processed = set()
        DEPGRAPH = {}

        def _explore_deps(jid):
            if jid in processed:
                # Already processed
                return

            # Early, to prevent infinite recursion
            processed.add(jid)

            deps = self.storage.get_job_deps(jid)
            DEPGRAPH[jid] = deps = [d['id'] for d in deps]
            for dep in deps:
                _explore_deps(dep)

            if complete:
                revdeps = self.storage.get_job_revdeps(jid)
                revdeps = [d['id'] for d in revdeps]
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
                exception=exc, exc_info=sys.exc_info())

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

    def _install_log_handler(self):
        _root_logger = logging.getLogger('')
        _root_logger.setLevel(logging.DEBUG)
        if _log_handler not in _root_logger.handlers:
            _root_logger.addHandler(_log_handler)

    # ------------------------------------------------------------
    # Job function selection / sandboxing / ... functions
    # ------------------------------------------------------------

    def is_function_allowed(self, name):
        return True  # Allow everything in default implementation

    def get_function(self, name):
        pass

    def autocomplete_function(self, name_prefix):
        # Autocomplete function name
        pass


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

        # Replace traceback with text representation, as traceback
        # objects cannot be pickled
        if record.exc_info is not None:
            tb = traceback.format_exception(*record.exc_info)
            record.exc_info = record.exc_info[0], record.exc_info[1], tb

        current_app.storage.log_message(
            job_id=execution_context.job_id,
            build_id=execution_context.build_id,
            record=record)


class JobInfo(object):
    """High-level interface to jobs"""

    def __init__(self, app, job_id, info=None):
        self.app = app
        self.job_id = job_id
        if info is not None:
            self._info = {}
            self._info.update(info)

    def __repr__(self):
        return '<Job {0}>'.format(self.job_id)

    @classmethod
    def new(cls, app, *w, **kw):
        job_id = app.storage.create_job(*w, **kw)
        return cls(app, job_id)

    @property
    def id(self):
        return self.job_id

    @property
    def info(self):
        if getattr(self, '_info') is None:
            self.refresh()
        return self._info

    def refresh(self):
        self._info = self.app.storage.get_job(self.job_id)

    def __getitem__(self, name):
        return self.info[name]

    def update(self, *a, **kw):
        self.app.storage.update_job(self.job_id, *a, **kw)
        self.refresh()

    def delete(self):
        self.app.storage.delete_job(self.job_id)

    def get_deps(self):
        for dep in self.app.storage.get_job_deps(self.job_id):
            yield JobInfo(self.app, dep['id'], info=dep)

    def get_revdeps(self):
        for revdep in self.app.storage.get_job_revdeps(self.job_id):
            yield JobInfo(self.app, revdep['id'], info=revdep)

    def get_builds(self, *a, **kw):
        for build in self.app.storage.get_job_builds(self.job_id, *a, **kw):
            yield BuildInfo(self.app, build['id'], info=build)

    # def create_build(self):
    #     # Meant for future usage, when builds will support .run()
    #     build_id = self.app.storage.create_build(self.job_id)
    #     return BuildInfo(self.app, build_id)

    def run(self):
        return self.app.build_job(self.job_id)

    def get_latest_successful_build(self):
        build = self.app.storage.get_latest_successful_build(self.job_id)
        if build is None:
            return
        return BuildInfo(self.app, build['id'], info=build)

    def get_docs(self):
        return self._get_job_docs()

    def has_builds(self):
        builds = list(self.get_builds(
            started=True, finished=True, order='desc', limit=1))
        return len(builds) >= 1

    def has_successful_builds(self):
        builds = list(self.get_builds(
            started=True, finished=True, success=True, skipped=False,
            order='desc', limit=1))
        return len(builds) >= 1

    def is_outdated(self):
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
    """High-level interface to builds"""

    def __init__(self, app, build_id, info=None):
        self.app = app
        self.build_id = build_id
        if info is not None:
            self._info = {}
            self._info.update(info)

    def __repr__(self):
        return '<Build {0} (job={1}, status={2})>'.format(
            self.build_id, self.job_id, self.descriptive_status)

    @property
    def id(self):
        return self.build_id

    @property
    def job_id(self):
        return self.info['job_id']

    @property
    def info(self):
        if getattr(self, '_info') is None:
            self.refresh()
        return self._info

    @property
    def descriptive_status(self):
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
        self._info = self.app.storage.get_build(self.build_id)

    def __getitem__(self, name):
        if name not in self.info:
            if name == 'progress_info':
                self._info['progress_info'] = self.get_progress_info()
                return self._info['progress_info']

        return self.info[name]

    def get_progress_info(self):
        current = self.info['progress_current']
        total = self.info['progress_total']

        progress_info = {
            'current': current,
            'total': total,
            'percent': 0,
            'percent_human': 'N/A',
            'label': 'N/A',
        }

        if total != 0:
            ratio = current * 1.0 / total
            percent = ratio * 100
            progress_info['percent'] = percent
            progress_info['percent_human'] = format(percent, '.0f')
            progress_info['label'] = '{0}/{1} ({2:.0f}%)'.format(
                current, total, percent)

            hue = ratio * 120  # todo: use logaritmic scale?
            color = ''.join([
                format(int(x * 255), '02X')
                for x in colorsys.hsv_to_rgb(hue / 360.0, .8, .8)])
            progress_info['color'] = '#' + color

        return progress_info

    def get_job(self):
        return JobInfo(self.app, self.job_id)

    def delete(self):
        self.app.storage.delete_build(self.build_id)

    def run(self):
        raise NotImplementedError("Cannot run a build directly")

    def iter_log_messages(self):
        return self.app.storage.iter_log_messages(build_id=self.build_id)


# We need just *one* handler -> create here
_log_handler = JobControlLogHandler()
_log_handler.setLevel(logging.DEBUG)
