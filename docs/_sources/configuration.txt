Configuration
#############

The configuration file is written entirely in YAML.


Storage
=======

Define an URL pointing to the storage (for build status).

.. code-block:: yaml

    storage: "postgresql://jobcontrol_test:test@localhost:5432/jc-harvester-141125"

Webapp
======

Configuration for the web application.

Uppercase names will be merged with standard Flask configuration.


.. code-block:: yaml

    webapp:
        PORT: 5050
        DEBUG: False


Celery
======

**TODO**

Configuration for Celery (the asynchronous task running library).


.. code-block:: yaml

    celery:
        BROKER_URL: "redis://localhost:6379"


Jobs
====

Job definition is a list of objects like this:

.. code-block:: yaml

    id: some_job_id
    title: "Some job title here"
    function: mypackage.mymodule:myfunction
    args:
        - spam
        - eggs
        - bacon
    kwargs:
        foobar: 'Something completely different'
        blah: !retval 'some_other_job'
    dependencies: ['some_other_job']

..which tells JobControl to run something roughly equivalent to:

.. code-block:: python

    from mypackage.mymodule import myfunction

    myfunction('spam', 'eggs', 'bacon',
               foobar='Something completely different',
               blah=get_return_value('some_other_job'))

Where the (immaginary) ``get_return_value()`` function returns the return
value from the latest successful build of the specified job (which *must*
be amongst the job dependencies).


Planned job configuration keys
------------------------------

- ``protect`` boolean indicating whether this job must be "protected":
  by "protect" we mean "from accidental mistakes"; for example, it would
  be handy to prevent accidental builds of jobs that import things in
  production websites. If this flag is set, the "quick build" feature
  will be disabled and the build form submit button will need "arming"
  (by clicking another button) before being actually usable.

- ``cleanup`` indicate a function to be called on build deletion to clean up
  any data stored externally. That function requires access to the build
  status, eg. in order to get a pointer to the storage containing the data.
