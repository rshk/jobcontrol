def example_function(*args, **kwargs):
    return (args, kwargs)


def job_with_progress():
    from jobcontrol.globals import current_app
    job_run = current_app.get_current_job_run()
    for i in xrange(11):
        job_run.set_progress(i, 10)
    return "DONE"


def job_with_logging():
    import logging
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
