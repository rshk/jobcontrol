import logging
import random
import time


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


def testing_job(steps=10, sleep=1, retval='DONE', fail=False):
    """
    Job to be used for testing purposes.

    Provides facilities for simulating various execution scenarios,
    such as logging, failures, progress, ..

    :param steps: How many "steps" this job is composed of
    :param sleep: How many seconds to sleep between each "step"
    :param retval: What to return
    :param fail:
        - if ``False``, the build will succeed
        - if ``True``, the build will fail
        - if an integer, the step at wich the build will fail
        - if a float (0 <= x <= 1), the chance of the job failing
    """

    from jobcontrol.globals import current_app, execution_context

    logger = logging.getLogger(__name__)

    def update_progress(*a):
        current_app.storage.update_build_progress(
            execution_context.build_id, *a)

    update_progress(0, 10)
    for i in xrange(1, steps + 1):
        _log_random(logger)

        update_progress(i, steps)

        time.sleep(sleep)

        if isinstance(fail, float):
            # Float: chance of failing
            if random.random() <= (fail / steps):
                raise RuntimeError('Simulating failure {0:.0f}%'
                                   .format(fail * 100))

        elif isinstance(fail, (int, long)) and fail == i:
            # Int: where to fail
            raise RuntimeError('Simulating failure at step {0}'
                               .format(fail))

    _log_random(logger)

    if fail is True:
        raise RuntimeError('Simulating failure at end')

    return "DONE"


def job_with_logging():
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)
    logger.debug('This is a debug message')
    logger.info('This is a info message')
    logger.warning('This is a warning message')
    logger.error('This is a error message')
    logger.critical('This is a critical message')

    try:
        raise ValueError('Foobar')
    except:
        logger.exception('This is an exception message')


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


def job_dep_A():
    return 'A'


def job_dep_B():
    from jobcontrol.globals import current_job
    dependencies = current_job.dependencies

    if len(dependencies) != 1:
        raise RuntimeError("Expected 1 dependency, got {0}"
                           .format(len(dependencies)))

    latest_run = list(dependencies[0].iter_runs())[-1]
    res = latest_run.get_result()

    return res + 'B'


def job_dep_C():
    from jobcontrol.globals import current_job
    dependencies = current_job.dependencies

    if len(dependencies) != 1:
        raise RuntimeError("Expected 1 dependency, got {0}"
                           .format(len(dependencies)))

    latest_run = list(dependencies[0].iter_runs())[-1]
    res = latest_run.get_result()

    return res + 'C'


def job_debug_echo(*args, **kwargs):
    from jobcontrol.globals import current_app, job_id
    # todo: return information on job + deps..
    return (args, kwargs)


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
