"""
Functions to manage the job configuration

The job configuration is a YAML object (dict) containing (at least) the
following keys:

- module - name of the module from wich to import the function
- function - name of the function to be called
- args - arguments to the function (list)
- kwargs - keyword arguments to the function (dictionary)
- dependencies - dependencies for this job

Additional "constructors" are available:

- ``!retval <n>`` will be replaced with return value of latest successful
  build for dependency job ``<n>`` (and job ``<n>`` *must* be specified
  as a dependency)

- [proposed] ``!cfg <name>`` will be replaced with global configuration
  option ``<name>``

- [proposed] "system" objects, such as context, job configuration, ...
  might be passed/accessed as well?

  - execution context
  - current job object
  - current build object

- [proposed] ``!secret <name>`` value from "secret" configuration, usually
  used for storing passwords etc, on file.


**Note:** job configuration widgets *need* to manipulate the configuration,
if we want to expose it in a nicer way -- is there any way to do so while
preserving formatting / comments in other parts of the document?

-----

**Job configuration:**

.. code-block:: yaml

    jobs:

      - name: my-job-name
        title: A descriptive title
        function: package.module:name
        args: []
        kwargs:
          storage: {url: 'mongodb://...'}
          input_storage: !retval 'other-job-name'
        dependencies: ['other-job-name']

      - name: other-job-name
        title: Another descriptive title
        function: package.module:othername
"""


from collections import Mapping

import yaml
from yaml import SafeDumper, SafeLoader

from jobcontrol.globals import execution_context
from jobcontrol.utils import get_storage_from_url
from jobcontrol.exceptions import NotFound


class Retval(object):
    """Placeholder for ``!retval <n>``"""

    def __init__(self, job_id):
        if not isinstance(job_id, basestring):
            raise TypeError("Job id must be a string")
        self.job_id = job_id

    def __repr__(self):
        return 'Retval({0!r})'.format(self.job_id)

    def __eq__(self, other):
        if type(self) != type(other):
            return False

        return self.job_id == other.job_id

    def __ne__(self, other):
        return not self.__eq__(other)


def dump(data):
    class CustomDumper(SafeDumper):
        pass

    def _represent_retval(dumper, data):
        return dumper.represent_scalar(
            u'!retval', value=unicode(data.job_id))

    CustomDumper.add_representer(Retval, _represent_retval)

    return yaml.dump_all([data], Dumper=CustomDumper,
                         default_flow_style=False)


def load(stream):
    class CustomLoader(SafeLoader):
        pass

    def _construct_retval(loader, data):
        return Retval(loader.construct_scalar(data))

    CustomLoader.add_constructor(u'!retval', _construct_retval)

    return yaml.load(stream, Loader=CustomLoader)


def prepare_args(args, build):
    """
    Prepare arguments / kwargs by replacing placeholders with actual
    values from the context.
    """

    # todo: important! we want to use return values from the *pinned* builds!

    if isinstance(args, Retval):
        current_job = execution_context.current_job
        if args.job_id not in current_job['dependencies']:
            raise ValueError("job {0} is not a dependency of job {1}"
                             .format(args.job_id, current_job.id))

        dep_job = execution_context.current_app.get_job(args.job_id)
        build = dep_job.get_latest_successful_build()
        if build is None:
            raise ValueError("Job {0} has no successful builds"
                             .format(args.job_id))
        return build['retval']

    if isinstance(args, list):
        return [prepare_args(x, build) for x in args]

    if isinstance(args, tuple):
        return tuple(prepare_args(x, build) for x in args)

    if isinstance(args, dict):
        return dict((prepare_args(k, build), prepare_args(v, build))
                    for k, v in args.iteritems())

    if isinstance(args, (basestring, int, float, long, bool)):
        return args

    raise TypeError("Unsupported type: {0}".format(type(args).__name__))


class JobControlConfigMgr(Mapping):
    def __init__(self, initial=None):
        self._data = {}
        if initial is not None:
            self._data.update(initial)

    @classmethod
    def from_file(cls, filename):
        if isinstance(filename, basestring):
            with open(filename, 'r') as fp:
                return cls.from_string(fp.read())

        if hasattr(filename, 'read'):
            return cls.from_string(filename.read())

        raise TypeError('filename must be a string or a file-like object')

    @classmethod
    def from_string(cls, s):
        import jinja2

        tpl = jinja2.Template(s)
        rendered = tpl.render()
        conf_obj = load(rendered)
        return cls.from_object(conf_obj)

    @classmethod
    def from_object(cls, data):
        obj = cls()
        obj.validate(data)
        obj._data = {}
        obj._data.update(data)
        return obj

    @property
    def config(self):
        return self._data

    def __getitem__(self, name):
        return self.config[name]

    def __iter__(self):
        return iter(self.config)

    def __len__(self):
        return len(self.config)

    # ------------------------------------------------------------
    # Configuration validation
    # ------------------------------------------------------------

    def validate(self, data):
        data.setdefault('jobs', [])
        data.setdefault('webapp', {})
        data.setdefault('secret', {})

        if not isinstance(data['jobs'], list):
            raise TypeError('Jobs must be a list')

        for job in data['jobs']:
            if 'id' not in job:
                raise ValueError('Jobs must have an Id')

    # ------------------------------------------------------------
    # High-level interface
    # ------------------------------------------------------------

    def iter_jobs(self):
        for job in self._data['jobs']:
            yield job

    def get_job(self, job_id):
        for job in self._data['jobs']:
            if job['id'] == job_id:
                return job
        raise NotFound('Job not found: {0!r}'.format(job_id))

    def get_job_deps(self, job_id):
        job = self.get_job(job_id)
        if 'dependencies' not in job:
            return
        for dep in job['dependencies']:
            yield dep

    def get_job_revdeps(self, job_id):
        for job in self._data['jobs']:
            if ('dependencies' in job) and (
                    job_id in job['dependencies']):
                yield job['id']

    def get_webapp_config(self):
        """
        Returns a dict containing configuration for the Flask app
        """

        if 'webapp' not in self._data:
            return {}

        return self._data['webapp']

    def get_secret(self, name):
        return self._data['secret'].get(name)

    def get_storage(self):
        if 'storage' not in self._data:
            raise ValueError('Configuration must specify a storage')

        if not isinstance(self._data['storage'], basestring):
            raise TypeError('Storage must be a string (URL)')

        return get_storage_from_url(self._data['storage'])
