Deployment instructions
#######################

Requisites:

- **Python** 2.7 (2.6 should work but it's untested)
- **PostgreSQL** 9.1+ (tested on 9.4 but older 9.x versions should do)
- **Redis** (any recent version should do; tested on 2.8.17)

Steps:

- Create a PostgreSQL database for jobcontrol
- Install jobcontrol in a virtualenv::

    virtualenv jobcontrol
    pip install jobcontrol
- :doc:`Write a configuration file <configuration>`
- Create database tables::

    jobcontrol-cli --config-file path/to/conf.yaml install
- Launch the webapp::

    jobcontrol-cli --config-file path/to/conf.yaml web --port 5050
- Start redis server::

    redis-server
- Launch the celery worker::

    jobcontrol-cli --config-file path/to/conf.yaml worker
- Visit http://127.0.0.1:5050
- Enjoy!


todo
====
