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


import io

from yaml.dumper import SafeDumper
from yaml.loader import SafeLoader

from jobcontrol.globals import execution_context


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
    out = io.StringIO()
    dmpr = SafeDumper(out, default_flow_style=False)

    def _represent_retval(dumper, data):
        return dumper.represent_scalar(
            u'!retval', value=unicode(data.job_id))

    dmpr.add_representer(Retval, _represent_retval)

    dmpr.open()
    try:
        dmpr.represent(data)
    finally:
        dmpr.close()

    return out.getvalue()


def load(stream):
    ldr = SafeLoader(stream)

    def _construct_retval(loader, data):
        return Retval(loader.construct_scalar(data))

    ldr.add_constructor(u'!retval', _construct_retval)

    return ldr.get_single_data()


def prepare_args(args):
    """
    Prepare arguments / kwargs by replacing placeholders with actual
    values from the context.
    """

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
        return [prepare_args(x) for x in args]

    if isinstance(args, tuple):
        return tuple(prepare_args(x) for x in args)

    if isinstance(args, dict):
        return dict((prepare_args(k), prepare_args(v))
                    for k, v in args.iteritems())

    if isinstance(args, (basestring, int, float, long, bool)):
        return args

    raise TypeError("Unsupported type: {0}".format(type(args).__name__))
