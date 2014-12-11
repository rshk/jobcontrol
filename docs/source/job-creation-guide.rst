Writing a job function
######################


First rule: keep it simple
==========================

That is, for basic usage, you don't have to do anything "fancy".

Just create a Python function, drop it inside a module somewhere
in the path of the interpreter running jobcontrol, list it in the
configuration file and that's it.

An example project can be found here: https://github.com/rshk/ckan_crawl_demo

.. note:: Although not strictly necessary, it is a good practice to create
   a setup.py in order to make your project properly installable, then
   install it in your virtualenv using ``pip install ...`` or ``python setup.py install``.


Logging messages
================

Just use the standard Python `logging`_ facilities:

.. code-block:: python

    import logging
    logger = logging.getLogger(__name__)
    logger.info('Hello, world')
    logger.warning('Aw, snap!')
    logger.error('Dammit!!')

.. _logging: https://docs.python.org/2/library/logging.html


Reporting progress
==================

Unluckily Python doesn't provide any facility to "report progress", so
we had to implement our own. But no fear, as it gets as simple as:

.. code-block:: python

    from jobcontrol.globals import current_app
    current_app.report_progress(None, 20, 100)  # 20%

Ok, let me explain the arguments a bit more in detail:

- The first one, ``group_name``, is used for building "trees" of progress
  reports. It can be either ``None``, indicating the top level, or a tuple
  of name "parts", used to build the tree.

  For example, let's suppose we need to perform two different "kinds" of steps
  in our function: first we want to download a bunch of web pages, then we
  want to extract links from all of them and import to somewhere.

  The first iteration will report progress like this:

  .. code-block:: python

      current_app.report_progress(('Download webpages',), current, total)

  The second one:

  .. code-block:: python

      current_app.report_progress(('Extracting links',), current, total)

  This will create three progress bars on the UIs, pretty much like this::

    [0/20] Total
      |-- [0/10] Downloading webpages
      '-- [0/10] Extracting links

  Multiple name parts can be used like this:

  .. code-block:: python

      current_ap.report_progress(('http://example.com/foo.zip', 'downloading'), ...)
      current_ap.report_progress(('http://example.com/foo.zip', 'extracting'), ...)
      current_ap.report_progress(('http://example.com/bar.zip', 'downloading'), ...)
      current_ap.report_progress(('http://example.com/bar.zip', 'extracting'), ...)

  Will generate the following progress bars::

      [../400] Total
      |-- [../200] http://www.example.com/foo.zip
      |   |-- [../100] downloading
      |   '-- [../100] extracting
      '-- [../200] http://www.example.com/bar.zip
          |-- [../100] downloading
          '-- [../100] extracting

  (And, of course, intermediate "branches" can be overridden by specifying them manually)

- The second and third ones, ``current`` and ``total`` must be integers
  indicating, respectively, the current amount of items completed and the
  total number of items.

- A fourth optional argument, ``status_line``, may be used to report a (brief)
  description of what's currently going on (eg, ``"Downloading http://www.example.com"``)


Generator functions
===================

.. warning:: Generator functions are *not* supported yet, that means, they will be
             executed, a generator will be obtained and stored (not sure it can be
             pickled, though..) but it will *not* be iterated, meaning the execution
             will have no effect whatsoever.

             If you really need to run a generator function, just wrap it in something
             like ``list(myfunction())``.

.. note:: There are future plans of changing this, probably using generator functions
          to return "multiple" values that can be then used for "parametrized" builds..
