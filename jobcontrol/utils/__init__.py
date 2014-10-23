from datetime import datetime
import json
import math
from urlparse import urlparse

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
    #       scheme format..

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
