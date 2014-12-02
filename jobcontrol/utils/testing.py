import logging
import random
import time

from jobcontrol.exceptions import SkipBuild


def job_simple_echo(*args, **kwargs):
    return (args, kwargs)


_cached_words = None


def _get_words():
    global _cached_words

    if _cached_words is not None:
        return _cached_words

    try:
        with open('/usr/share/dict/words') as fp:
            _cached_words = [x.strip() for x in fp]
    except:
        _cached_words = []

    return _cached_words


def _capfirst(s):
    return s[0].upper() + s[1:]


def _random_paragraph(size=10):
    return _capfirst(' '.join(random.sample(_get_words(), size)))


def _log_random(logger):
    classes = (logging.DEBUG, logging.INFO, logging.WARNING, logging.ERROR,
               logging.CRITICAL)

    for num in xrange(random.randint(0, 30)):
        logger.log(random.choice(classes),
                   _random_paragraph(random.randint(10, 20)))


def testing_job(progress_steps=None, retval=None, fail=False, skip=False,
                log_messages=None, step_duration=0):
    """
    Job used for testing purposes.

    :param progress_steps:
        A list of tuples: ``(<group_name>, <steps>)``, where "group_name"
        is a tuple of name "levels", "steps" an integer representing how
        many steps should that level have.

        Progress reports will be sent in randomized order.

    :param retval:
        The return value for the job.

    :param fail:
        Whether this job should fail.

    :param skip:
        Whether this job should be skipped.

    :param log_messages:
        A list of tuples: ``(level, message)``

    :param step_duration:
        The time to sleep between steps, in milliseconds.
    """

    from jobcontrol.globals import execution_context

    logger = logging.getLogger('jobcontrol.utils.testing_job')

    log_messages = list(log_messages or [])
    if progress_steps is None:
        progress_steps = [(None, 10)]

    totals = {}
    counters = {}

    progress_report_items = []
    for name, steps in progress_steps:

        if isinstance(name, list):
            # Safe YAML doesn't have tuples, but names must be tuples
            name = tuple(name)

        if not (name is None or isinstance(name, tuple)):
            raise TypeError("Name must be a tuple or None")

        for i in xrange(steps):
            progress_report_items.append(name)
        totals[name] = steps
        counters[name] = 0

    random.shuffle(progress_report_items)

    sleep_time = step_duration * 1.0 / 1000

    def report_progress(name, cur, tot, status=None):
        app = execution_context.current_app
        app.report_progress(
            group_name=name, current=cur, total=tot,
            status_line=status)

    def _should_fail():
        return random.randint(0, len(progress_report_items)) == 0

    for item in progress_report_items:
        counters[item] += 1
        report_progress(item, counters[item], totals[item],
                        'Doing action {0} [{1}/{2}]'
                        .format(item, counters[item], totals[item]))

        if len(log_messages):
            lev, msg = log_messages.pop(0)
            logger.log(lev, msg)

        if fail and _should_fail():
            raise RuntimeError(
                'This is a simulated exception in the middle of the loop')

        if skip and _should_fail():
            raise SkipBuild(
                'This is a simulated skip in the middle of the loop')

        if sleep_time:
            time.sleep(sleep_time)

    if skip:
        # Make sure the job gets skipped
        raise SkipBuild('This build should be skipped!')

    if fail:
        # Make sure the job fails
        raise RuntimeError('This is a simulated exception')

    return retval


def job_with_logging():
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)
    logger.debug('This is a debug message')
    logger.info('This is a info message')
    logger.warning('This is a warning message')
    logger.error('This is an error message')
    logger.critical('This is a critical message')

    try:
        raise ValueError('Foobar')
    except:
        logger.exception('This is an exception message')


def job_with_tracer_log():
    from jobcontrol.globals import execution_context
    logger = logging.getLogger(__name__)
    logger.info('Message from job={0}, build={1}'
                .format(execution_context.job_id,
                        execution_context.build_id))
    pass


def job_failing_once():
    """
    This job will fail exactly once; retry will be successful
    """
    from jobcontrol.globals import current_job
    exec_count = len(list(current_job.iter_runs()))

    if exec_count <= 1:
        # This is the first run
        raise RuntimeError("Simulating failure")

    return exec_count


def job_echo_config(*args, **kwargs):
    """
    Simple job, "echoing" back the current configuration.
    """

    from jobcontrol.globals import current_job, current_build
    return {
        'args': args,
        'kwargs': kwargs,
        'build_id': current_build.id,
        'job_id': current_job.id,
        'dependencies': current_build['job_config']['dependencies'],
        'job_config': current_build['job_config'],
        'build_config': current_build['build_config'],
    }


class RecordingLogHandler(logging.Handler):
    """Log handler that records messages"""

    def __init__(self):
        super(RecordingLogHandler, self).__init__()
        self._messages = []

    def flush(self):
        pass  # Nothing to flush!

    def emit(self, record):
        self._messages.append(record)

    def print_messages(self):
        from nicelog.formatters import ColorLineFormatter
        formatter = ColorLineFormatter(
            show_date=False, show_function=False, show_filename=False,
            message_inline=True)
        for msg in self._messages:
            print(formatter.format(msg))

    def clear_messages(self):
        self._messages = []


class NonSerializableObject(object):
    __slots__ = ['foo', 'bar']

    def __init__(self):
        self.foo = 'foo'
        self.bar = 'bar'


class NonSerializableException(Exception):
    def __init__(self):
        super(NonSerializableException, self).__init__()
        self.nso = NonSerializableObject()


def job_returning_nonserializable():
    return NonSerializableObject()


def job_raising_nonserializable():
    raise NonSerializableException()
