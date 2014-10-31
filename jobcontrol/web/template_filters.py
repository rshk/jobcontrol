import datetime
import humanize
import time


filters = {}


def humanize_timestamp(value):
    if value is None:
        return u'never'

    if isinstance(value, datetime.datetime):
        delta = datetime.datetime.now() - value
        return humanize.naturaltime(delta)

    if isinstance(value, (int, long, float)):
        return humanize.naturaltime(time.time() - value)

    raise ValueError("Unsupported date format: {0!r}"
                     .format(value))


def humanize_timedelta(value):
    if value is None:
        return u'N/A'

    if isinstance(value, datetime.timedelta):
        td = datetime.timedelta(seconds=int(value.total_seconds()))
        return str(td)

    if isinstance(value, (int, long, float)):
        td = datetime.timedelta(seconds=int(value))
        return str(td)

    raise ValueError("Unsupported time delta format: {0!r}"
                     .format(value))


def yesno(value, yes='Yes', no='No'):
    return yes if value else no


filters['humanize_timestamp'] = humanize_timestamp
filters['humanize_timedelta'] = humanize_timedelta
filters['yesno'] = yesno
