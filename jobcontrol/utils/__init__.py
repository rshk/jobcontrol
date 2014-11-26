from collections import defaultdict
from datetime import datetime
from urlparse import urlparse
import json
import linecache
import math
import sys

_missing = object()


class cached_property(object):
    """A decorator that converts a function into a lazy property.  The
    function wrapped is called the first time to retrieve the result
    and then that calculated result is used the next time you access
    the value::

        class Foo(object):

            @cached_property
            def foo(self):
                # calculate something important here
                return 42

    The class has to have a `__dict__` in order for this property to
    work.
    """

    # implementation detail: this property is implemented as non-data
    # descriptor.  non-data descriptors are only invoked if there is
    # no entry with the same name in the instance's __dict__.
    # this allows us to completely get rid of the access function call
    # overhead.  If one choses to invoke __get__ by hand the property
    # will still work as expected because the lookup logic is replicated
    # in __get__ for manual invocation.

    def __init__(self, func, name=None, doc=None):
        self.__name__ = name or func.__name__
        self.__module__ = func.__module__
        self.__doc__ = doc or func.__doc__
        self.func = func

    def __get__(self, obj, type=None):
        if obj is None:
            return self
        value = obj.__dict__.get(self.__name__, _missing)
        if value is _missing:
            value = self.func(obj)
            obj.__dict__[self.__name__] = value
        return value


def import_object(name):
    if name.count(':') != 1:
        raise ValueError("Invalid object name: {0!r}. "
                         "Expected format: '<module>:<name>'."
                         .format(name))

    module_name, class_name = name.split(':')
    module = __import__(module_name, fromlist=[class_name])
    return getattr(module, class_name)


STORAGE_ALIASES = {
    'postgresql': 'jobcontrol.ext.postgresql:PostgreSQLStorage',
    'memory': 'jobcontrol.ext.memory:MemoryStorage',
}


def get_storage_from_url(url):
    """
    Get a storage from URL.

    Storages URLs are in the format:

    - ``<scheme>://``
    - ``<class>+<scheme>://`` Load <class>, pass the URL removing ``<class>+``
    """

    # NOTE: We should improve this, as the standard format for
    #       describing imported objects is **not** compatible with the URL
    #       scheme format.

    # TODO: Use stevedore to register / load storage plugins in place
    #       of the dict above.

    parsed = urlparse(url)
    if '+' in parsed.scheme:
        clsname, scheme = parsed.scheme.split('+', 1)
        url = parsed._replace(scheme=scheme).geturl()
    else:
        clsname = scheme = parsed.scheme

    if clsname in STORAGE_ALIASES:
        clsname = STORAGE_ALIASES[clsname]

    storage_class = import_object(clsname)
    return storage_class.from_url(url)


def get_storage_from_config(config):
    raise NotImplementedError('')


def short_repr(obj, maxlen=50):
    rep = repr(obj)
    if len(rep) <= maxlen:
        return rep

    # Cut in the middle..
    cutlen = maxlen - 3
    p1 = math.ceil(cutlen / 2.0)
    p2 = math.floor(cutlen / 2.0)
    return '...'.join((rep[:p1], rep[-p2:]))


def _json_dumps_default(obj):
    if isinstance(obj, datetime):
        return obj.isoformat()

    raise TypeError('{0!r} is not JSON serializable'.format(obj))


def json_dumps(obj):
    return json.dumps(obj, default=_json_dumps_default)


def trim_string(s, maxlen=1024, ellps='...'):
    """Trim a string to a maximum length, adding an "ellipsis"
    indicator if the string was trimmed"""

    if len(s) > maxlen:
        return s[:maxlen - len(ellps)] + ellps
    return s


class FrameInfo(object):
    def __init__(self, filename, lineno, name, line, locs):
        self.filename = filename
        self.lineno = lineno
        self.name = name
        self.line = line
        self.locs = self._format_locals(locs)
        self.context = self._get_context()

    def _get_context(self, size=5):
        """Return some "context" lines from a file"""
        _start = max(0, self.lineno - size - 1)
        _end = self.lineno + size
        _lines = linecache.getlines(self.filename)[_start:_end]
        _lines = [x.rstrip() for x in _lines]
        _lines = zip(xrange(_start + 1, _end + 1), _lines)
        return _lines

    def _format_locals(self, locs):
        return dict(((k, trim_string(repr(v), maxlen=1024))
                     for k, v in locs.iteritems()))


class TracebackInfo(object):
    """
    Information about an error traceback; this is meant to be serialized
    instead of the full traceback (which is *not* serializable...)
    """

    def __init__(self):
        self.frames = []

    @classmethod
    def from_current_exc(cls):
        return cls.from_tb(sys.exc_info()[2])

    @classmethod
    def from_tb(cls, tb):
        obj = cls()
        obj.frames = cls._extract_tb(tb)
        return obj

    def format(self):
        """Format traceback for printing"""

        lst = []
        for filename, lineno, name, line, locs in self.frames:
            item = '  File "{0}", line {1}, in {2}\n'.format(
                filename, lineno, name)
            if line:
                item = item + '    {0}\n'.format(line.strip())
            lst.append(item)
            for key, val in sorted(locs.iteritems()):
                lst.append('        {0} = {1}\n'.format(key, val))
        return lst

    @classmethod
    def _extract_tb(cls, tb, limit=None):
        if limit is None:
            if hasattr(sys, 'tracebacklimit'):
                limit = sys.tracebacklimit
        list = []
        n = 0
        while tb is not None and (limit is None or n < limit):
            f = tb.tb_frame
            lineno = tb.tb_lineno
            co = f.f_code
            filename = co.co_filename
            name = co.co_name
            linecache.checkcache(filename)
            line = linecache.getline(filename, lineno, f.f_globals)
            locs = cls._dump_locals(f.f_locals)
            if line:
                line = line.strip()
            else:
                line = None
            list.append(FrameInfo(filename, lineno, name, line, locs))
            tb = tb.tb_next
            n = n+1
        return list

    @classmethod
    def _dump_locals(cls, locs):
        return dict(((k, trim_string(repr(v), maxlen=1024))
                     for k, v in locs.iteritems()))

    def __str__(self):
        return ''.join(self.format())

    def __unicode__(self):
        return u''.join(unicode(x) for x in self.format())


class ProgressReport(object):
    """Class for representing progress reports"""

    def __init__(self, name, current=None, total=None, status_line=None,
                 children=None):
        self.name = name
        self._current = current
        self._total = total
        self.status_line = status_line
        self.children = []
        if children is not None:
            if not all(isinstance(x, ProgressReport)
                       for x in children):
                raise TypeError(
                    "Progress children must be ProgressReport instances")
            self.children.extend(children)

    @property
    def current(self):
        if self._current is not None:
            return self._current

        return sum(x.current for x in self.children)

    @property
    def total(self):
        if self._total is not None:
            return self._total

        return sum(x.total for x in self.children)

    @classmethod
    def from_table(cls, table, base_name=None):
        """
        :param table:
            a list of tuples: (name, current, total, status_line).

            - If there is a tuple with ``name == None`` -> use
              as the object's current/total report

            - Find all the "namespaces" and use to build progress
              sub-objects
        """

        root = None
        prefixes = []  # Need to preserve order!

        # For each prefix, build a table with prefix stripped from names
        sub_tables = defaultdict(list)

        for name, current, total, status_line in table:
            if not (name is None or isinstance(name, tuple)):
                raise TypeError('name must be a tuple (or None)')

            if not name:
                root = (base_name, current, total, status_line)

            else:
                prefix = name[0]
                if prefix not in prefixes:
                    prefixes.append(prefix)
                sub_tables[prefix].append(
                    (name[1:], current, total, status_line))

        if root is None:
            # the root is indefined -- should be guessed!
            obj = cls(base_name)

        else:
            name, current, total, status_line = root  # Explicit!
            obj = cls(name, current, total, status_line)

        # Add children..
        for pref in prefixes:
            obj.children.append(ProgressReport.from_table(
                sub_tables[pref], base_name=pref))

        return obj
