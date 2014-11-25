from textwrap import dedent

import pytest

from jobcontrol.job_conf import (
    dump, load, Retval, JobControlConfigMgr)
from jobcontrol.interfaces import StorageBase
from jobcontrol.ext.postgresql import PostgreSQLStorage
from jobcontrol.exceptions import NotFound


# todo: test arguments replacement -> requires an execution context!


def test_simple_conf_loading():
    assert load("""
    module: mypkg.mymod
    function: myfunc
    args:
        - spam
        - eggs
        - bacon
    kwargs:
        one: 1
        two: 2
        three: 3
    dependencies: [job-1, job-2]
    """) == {
        'module': 'mypkg.mymod',
        'function': 'myfunc',
        'args': ['spam', 'eggs', 'bacon'],
        'kwargs': {'one': 1, 'two': 2, 'three': 3},
        'dependencies': ['job-1', 'job-2'],
    }


def test_load_conf_with_retval():
    # Make sure the object comparison works
    assert Retval('job-1') == Retval('job-1')
    assert Retval('job-1') != Retval('job-2')
    assert Retval('job-1') != "something completely different"

    # Make sure serialization works fine..
    loaded = load(u'!retval job-1')
    assert loaded == Retval('job-1')

    loaded = load(u'!retval "job-1"')
    assert loaded == Retval('job-1')

    dumped = dump(Retval('job-1'))
    assert dumped == u"!retval 'job-1'\n"

    config = load("""
    args:
        - foobar
        - !retval job-1
    kwargs:
        foo: !retval job-2
        bar: !retval job-3
    dependencies: [1, 2, 3]
    """)
    assert config == {
        'args': ['foobar', Retval('job-1')],
        'kwargs': {'foo': Retval('job-2'), 'bar': Retval('job-3')},
        'dependencies': [1, 2, 3],
    }


def test_load_complex_conf():
    conf = u"""
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

    loaded = load(conf)
    assert isinstance(loaded, dict)
    assert list(loaded.iterkeys()) == ['jobs']
    assert len(loaded['jobs']) == 2
    assert loaded['jobs'][0]['name'] == 'my-job-name'
    assert loaded['jobs'][0]['kwargs']['storage'] == {'url': 'mongodb://...'}
    assert loaded['jobs'][0]['kwargs']['input_storage'] == Retval('other-job-name')  # noqa
    assert loaded['jobs'][1]['name'] == 'other-job-name'


def test_conf_with_references():
    conf = u"""
    # todo: there should be a better way to define this..
    extra:
        - &site_url 'http://example.com'
        - &api_key '1234abcd'

    jobs:
        - name: one
          site: *site_url
          api_key: *api_key
        - name: two
          site: *site_url
          api_key: *api_key
    """

    loaded = load(conf)
    assert loaded['jobs'][0] == {
        'name': 'one',
        'site': 'http://example.com',
        'api_key': '1234abcd',
    }


def test_configuration_with_binary_strings():
    """
    Regression test: serialization was failing on binary strings
    """

    import yaml

    obj = '\xaa\xbb\x00\xff\xff\x00ABC'
    assert yaml.load(yaml.dump(obj)) == obj
    assert yaml.safe_load(yaml.safe_dump(obj)) == obj

    obj = {'blob': '\xaa\xbb\x00\xff\xff\x00ABC'}
    assert yaml.load(yaml.dump(obj)) == obj
    assert yaml.safe_load(yaml.safe_dump(obj)) == obj

    obj = {
        'function': 'jobcontrol.utils.testing:job_simple_echo',
        'title': None,
        'notes': None,
        # 'args': ('\xaa\xbb\x00\xff\xff\x00ABC',),
        'args': '\xaa\xbb\x00\xff\xff\x00ABC',
        'dependencies': [],
        'kwargs': {},
        'id': 'f974e89f-4ae3-40cc-8316-b78e42bd5cc8',
    }
    dump(obj)


def test_config_manager():
    config = dedent("""\
    storage: postgresql://user:pass@localhost:5432/mydb
    jobs:
        - id: job-1
          function: jobcontrol.utils.testing:job_simple_echo
          args:
              - one
              - 123
    webapp:
        PORT: 5050
        DEBUG: True

    secret:
        foo: "A Foo!"
        bar: 1234
    """)

    cfgmgr = JobControlConfigMgr.from_string(config)
    assert cfgmgr.config['storage'] == 'postgresql://user:pass@localhost:5432/mydb'  # noqa
    assert isinstance(cfgmgr.config['jobs'], list)
    assert len(cfgmgr.config['jobs']) == 1
    assert cfgmgr.config['jobs'][0]['id'] == 'job-1'
    assert cfgmgr.config['jobs'][0]['args'] == ['one', 123]
    assert cfgmgr.config['webapp'] == {'PORT': 5050, 'DEBUG': True}

    jobs = list(cfgmgr.iter_jobs())
    assert len(jobs) == 1
    assert jobs[0]['id'] == 'job-1'

    assert cfgmgr.get_job('job-1') == jobs[0]

    with pytest.raises(NotFound):
        cfgmgr.get_job('does-not-exist')

    assert cfgmgr.get_webapp_config() == {'PORT': 5050, 'DEBUG': True}

    assert cfgmgr.get_secret('foo') == 'A Foo!'
    assert cfgmgr.get_secret('bar') == 1234

    storage = cfgmgr.get_storage()
    assert isinstance(storage, StorageBase)
    assert isinstance(storage, PostgreSQLStorage)

    # todo: test error cases too..


def test_config_manager_job_deps():
    config = dedent("""\
    storage: postgresql://user:pass@localhost:5432/mydb
    jobs:
        - id: job-1
          function: jobcontrol.utils.testing:job_simple_echo

        - id: job-2
          function: jobcontrol.utils.testing:job_simple_echo
          dependencies: [job-1]

        - id: job-3
          function: jobcontrol.utils.testing:job_simple_echo
          dependencies: [job-2, job-1]
    """)

    cfgmgr = JobControlConfigMgr.from_string(config)

    assert list(cfgmgr.get_job_deps('job-1')) == []
    assert list(cfgmgr.get_job_deps('job-2')) == ['job-1']
    assert list(cfgmgr.get_job_deps('job-3')) == ['job-2', 'job-1']

    assert list(cfgmgr.get_job_revdeps('job-1')) == ['job-2', 'job-3']
    assert list(cfgmgr.get_job_revdeps('job-2')) == ['job-3']
    assert list(cfgmgr.get_job_revdeps('job-3')) == []
