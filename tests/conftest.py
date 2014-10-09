import os
import random
import time
from urlparse import urlparse
import shutil

import pytest
import py.path


TESTS_ROOT_DIR = py.path.local(__file__).dirpath()
TESTS_DATA_DIR = TESTS_ROOT_DIR.join('data')


POSTGRES_ENV_NAME = 'POSTGRES_URL'

# postgresql://jobcontrol_test:test@localhost:5432/jobcontrol_test


def get_postgres_conf():
    if POSTGRES_ENV_NAME not in os.environ:
        raise RuntimeError(
            "Missing configuration: the {0} environment variable is required"
            " in order to be able to create a PostgreSQL database for running"
            " tests. Please set it to something like: ``postgresql://"
            "user:password@host:port/database``."
            .format(POSTGRES_ENV_NAME))
    url = urlparse(os.environ[POSTGRES_ENV_NAME])
    return {
        'database': url.path.split('/')[1],
        'user': url.username,
        'password': url.password,
        'host': url.hostname,
        'port': url.port or 5432,
    }


@pytest.fixture(scope='module', params=['memory', 'postgresql'])
def jobcontrolmgr(request):
    if request.param == 'memory':
        from jobcontrol.ext.memory import MemoryJobControl
        jc = MemoryJobControl({})
        jc.install()
        request.addfinalizer(jc.uninstall)
        return jc

    if request.param == 'postgresql':
        try:
            conf = get_postgres_conf()
        except RuntimeError:
            pytest.skip('POSTGRESQL_URL not configured')

        from jobcontrol.ext.postgresql import PostgreSQLJobControl
        jc = PostgreSQLJobControl({'DATABASE': conf})

        try:
            # Make sure we don't have tables left around
            jc.uninstall()
        except:
            pass

        jc.install()
        request.addfinalizer(jc.uninstall)
        return jc

    raise RuntimeError('Invalid parameter: {0}'.format(request.param))
