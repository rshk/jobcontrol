Configuration
#############

The main configuration file is written in YAML and pre-processed
through Jinja, to allow things like defining variables, macros, etc.


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

Configuration for Celery (the asynchronous task running library).

See all the possible configuration options here:
http://docs.celeryproject.org/en/latest/configuration.html


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
==============================

- ``protect`` boolean indicating whether this job must be "protected":
  by "protect" we mean "from accidental mistakes"; for example, it would
  be handy to prevent accidental builds of jobs that import things in
  production websites. If this flag is set, the "quick build" feature
  will be disabled and the build form submit button will need "arming"
  (by clicking another button) before being actually usable.

- ``cleanup`` indicate a function to be called on build deletion to clean up
  any data stored externally. That function requires access to the build
  status, eg. in order to get a pointer to the storage containing the data.


Example macros
==============

For example, let's say we want to "crawl" and "process" a bunch of websites.

We could use a macro like this to keep repetitions at minimum:

.. code-block:: jinja

    {% macro process_website(name, url) %}
      - id: crawl_{{ name }}
        title: "Crawl {{ url }}"
        function: mycrawler:crawl
        kwargs:
          storage: postgresql://.../crawled_data_{{ name }}

      - id: process_{{ name }}
        title: "Process {{ url }}"
        function: mycrawler:process
        kwargs:
          input_storage: !retval crawl_{{ name }}
          storage: postgresql://.../processed_data_{{ name }}
    {% endmacro %}

    jobs:
    {{ process_website('example_com', 'http://www.example.com') }}
    {{ process_website('example_org', 'http://www.example.org') }}
    {{ process_website('example_net', 'http://www.example.net') }}

Will get expanded to:

.. code-block:: yaml

    jobs:
      - id: crawl_example_com
        title: "Crawl http://www.example.com"
        function: mycrawler:crawl
        kwargs:
          storage: postgresql://.../crawled_data_example_com

      - id: process_example_com
        title: "Process http://www.example.com"
        function: mycrawler:process
        kwargs:
          input_storage: !retval crawl_example_com
          storage: postgresql://.../processed_data_example_com

      - id: crawl_example_org
        title: "Crawl http://www.example.org"
        function: mycrawler:crawl
        kwargs:
          storage: postgresql://.../crawled_data_example_org

      - id: process_example_org
        title: "Process http://www.example.org"
        function: mycrawler:process
        kwargs:
          input_storage: !retval crawl_example_org
          storage: postgresql://.../processed_data_example_org

      - id: crawl_example_net
        title: "Crawl http://www.example.net"
        function: mycrawler:crawl
        kwargs:
          storage: postgresql://.../crawled_data_example_net

      - id: process_example_net
        title: "Process http://www.example.net"
        function: mycrawler:process
        kwargs:
          input_storage: !retval crawl_example_net
          storage: postgresql://.../processed_data_example_net

.. warning::

   Mind the indentation! The best way is to use the desired final indentation
   in the macro definition, then call the macro at "zero" indentation level.
