"""
Storage class, used to actually store the build state in PostgreSQL.

.. note:: If you want to write state to some other database, just
          create a compatible class and pass that to the main
          JobControl instance.
"""


class Storage(object):
    """Storage class for JobControl builds state"""
    pass
