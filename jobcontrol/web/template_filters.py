import datetime
import time

import humanize
from flask import escape


filters = {}


DEFAULT_DATE_FORMAT = '%a, %d %b %Y %H:%M:%S'


def humanize_timestamp(value):
    if value is None:
        return u'never'

    if isinstance(value, datetime.datetime):
        delta = datetime.datetime.now() - value
        return humanize.naturaltime(delta)

    if isinstance(value, (int, long, float)):
        return humanize.naturaltime(time.time() - value)

    raise TypeError("Unsupported date format: {0!r}".format(value))


def humanize_timedelta(value):
    if value is None:
        return u'N/A'

    if isinstance(value, datetime.timedelta):
        td = datetime.timedelta(seconds=int(value.total_seconds()))
        return str(td)

    if isinstance(value, (int, long, float)):
        td = datetime.timedelta(seconds=int(value))
        return str(td)

    raise TypeError("Unsupported time delta format: {0!r}".format(value))


def yesno(value, yes='Yes', no='No'):
    return yes if value else no


def strftime(value, fmt=DEFAULT_DATE_FORMAT):
    if value is None:
        return 'N/A'

    if isinstance(value, (int, long, float)):
        value = datetime.datetime.utcfromtimestamp(value)

    if isinstance(value, datetime.datetime):
        return value.strftime('%a, %d %b %Y %H:%M:%S')

    raise TypeError("Unsupported date object: {0!r}".format(value))


def highlight(value, lexer='python'):
    from pygments import highlight
    from pygments.lexers import get_lexer_by_name
    from pygments.formatters import HtmlFormatter

    try:
        lexer = get_lexer_by_name(lexer)
        return highlight(value, lexer, HtmlFormatter())

    except:
        lexer = get_lexer_by_name('text')
        return highlight(value, lexer, HtmlFormatter())


filters['humanize_timestamp'] = humanize_timestamp
filters['humanize_timedelta'] = humanize_timedelta
filters['yesno'] = yesno
filters['strftime'] = strftime
filters['highlight'] = highlight
