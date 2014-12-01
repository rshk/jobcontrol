Command-line interface
######################

All the operations can be run through the "jobcontrol-cli" command.

It is self-documented: running ``jobcontrol-cli --help`` will give
information on available commands; ``jobcontrol-cli <command> --help``
will give usage information on a specific command.


Installing database schema
==========================

::

   jobcontrol-cli --config-file myconfig.yaml install


Uninstalling database schema
============================

.. warning:: This will drop all tables without any further warning!

::

   jobcontrol-cli --config-file myconfig.yaml uninstall


Running the web app
===================

.. note:: For production mode, the application should be run via
          a proper WSGI container, such as gunicorn or uWSGI.

::

    jobcontrol-cli --config-file myconfig.yaml web --port 5050 --debug
