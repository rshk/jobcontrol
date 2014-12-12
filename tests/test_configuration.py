import pytest

from jobcontrol.core import BuildConfig
from jobcontrol.config import JobControlConfig, Retval, _yaml_load


def test_retval_object():
    """Make sure the retval object works as intended"""

    assert Retval('job-1') == Retval('job-1')
    assert Retval('job-1') != Retval('job-2')
    assert Retval('job-1') != "something completely different"
    with pytest.raises(TypeError):
        Retval(123)  # id must be a string

    assert repr(Retval('my-job')) == "Retval('my-job')"


def test_load_conf_from_yaml():
    """Load some simple yaml"""

    assert _yaml_load("""
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


def test_load_conf_from_yaml_with_retval():
    """Load some YAML containing "retval" objects"""

    assert _yaml_load("""
    foo: !retval 123
    bar: !retval some-job
    baz: !retval "job name here"
    a_list:
        - one
        - !retval two
    a_dict:
        one: 1
        two: !retval 2
    """) == {
        'foo': Retval('123'),
        'bar': Retval('some-job'),
        'baz': Retval('job name here'),
        'a_list': ['one', Retval('two')],
        'a_dict': {'one': 1, 'two': Retval('2')},
    }


def test_config_default_values():
    config = JobControlConfig.from_string('')
    assert config.storage is None
    assert config.jobs == []
    assert config.webapp == {}
    assert config.celery == {}
    assert config.secret == {}

    assert config.get_storage() is None


def test_config_all_keys():
    config = JobControlConfig.from_string("""
    storage: postgresql://localhost/database
    webapp:
        PORT: 5000
        HOST: 0.0.0.0
        SECRET_KEY: "super secret key"
    celery:
        BROKER_URL: redis://
    secret:
        MY_PASSWORD: '53cur3!'
    jobs:
        - id: foo
        - id: bar
    """)

    assert config.storage == 'postgresql://localhost/database'
    assert config.webapp == {
        'PORT': 5000,
        'HOST': '0.0.0.0',
        'SECRET_KEY': 'super secret key',
    }
    assert config.celery == {'BROKER_URL': 'redis://'}
    assert config.secret == {'MY_PASSWORD': '53cur3!'}
    assert len(config.jobs) == 2
    assert isinstance(config.jobs[0], BuildConfig)
    assert config.jobs[0]['id'] == 'foo'
    assert isinstance(config.jobs[1], BuildConfig)
    assert config.jobs[1]['id'] == 'bar'


def test_job_config_default_values():
    config = JobControlConfig.from_string("""
    jobs:
        - id: foo
          custom_key: 'Custom value'
    """)
    job = config.get_job('foo')
    assert isinstance(job, BuildConfig)
    assert job['id'] == 'foo'
    assert job['function'] is None
    assert job['args'] == ()
    assert job['kwargs'] == {}
    assert job['dependencies'] == []
    assert job['pinned_builds'] == {}
    assert job['title'] is None
    assert job['notes'] is None
    assert job['protected'] is False
    assert job['cleanup_function'] is None
    assert job['repr_function'] is None

    with pytest.raises(KeyError):
        job['does_not_exist']

    assert job['custom_key'] == 'Custom value'


def test_build_config_update():
    build_config = BuildConfig()
    build_config['id'] = 'my_job_id'

    build_config['function'] = 'mymodule:myfunction'
    assert build_config['function'] == 'mymodule:myfunction'
    with pytest.raises(TypeError):
        build_config['function'] = 123
    with pytest.raises(TypeError):
        build_config['function'] = u'Unicode.is:not_ok'

    build_config['args'] = (1, 2, 3)
    assert build_config['args'] == (1, 2, 3)
    build_config['args'] = [1, 2, 3]
    assert build_config['args'] == (1, 2, 3)
    with pytest.raises(TypeError):
        build_config['args'] = None
    with pytest.raises(TypeError):
        build_config['args'] = {1: 123}

    build_config['kwargs'] = {'foo': 'bar'}
    assert build_config['kwargs'] == {'foo': 'bar'}
    with pytest.raises(TypeError):
        build_config['kwargs'] = None
    with pytest.raises(TypeError):
        build_config['kwargs'] = []
    with pytest.raises(TypeError):
        build_config['kwargs'] = 'Something..'

    build_config['dependencies'] = ['a', 'b']
    assert build_config['dependencies'] == ['a', 'b']
    build_config['dependencies'] = ('a', 'b')
    assert build_config['dependencies'] == ['a', 'b']
    with pytest.raises(TypeError):
        build_config['dependencies'] = None
    with pytest.raises(TypeError):
        build_config['dependencies'] = 'abcde'
    with pytest.raises(TypeError):
        build_config['dependencies'] = {'some': 'dict'}

    build_config['pinned_builds'] = {'a': 1, 'b': 2}
    assert build_config['pinned_builds'] == {'a': 1, 'b': 2}
    with pytest.raises(TypeError):
        build_config['pinned_builds'] = None
    with pytest.raises(TypeError):
        build_config['pinned_builds'] = ['something', 'else']
    with pytest.raises(TypeError):
        build_config['pinned_builds'] = 'a string?'

    build_config['title'] = u'This is a unicode string'
    assert isinstance(build_config['title'], unicode)
    build_config['title'] = 'This is a bytes string'
    assert isinstance(build_config['title'], unicode)

    build_config['notes'] = u'This is a unicode string'
    assert isinstance(build_config['notes'], unicode)
    build_config['notes'] = 'This is a bytes string'
    assert isinstance(build_config['notes'], unicode)

    build_config['protected'] = True
    assert build_config['protected'] is True
    with pytest.raises(TypeError):
        build_config['protected'] = None
    with pytest.raises(TypeError):
        build_config['protected'] = 'False'

    build_config['cleanup_function'] = 'mymodule:my_cleanup_function'
    assert build_config['cleanup_function'] == 'mymodule:my_cleanup_function'
    with pytest.raises(TypeError):
        build_config['cleanup_function'] = 123

    build_config['repr_function'] = 'mymodule:my_repr_function'
    assert build_config['repr_function'] == 'mymodule:my_repr_function'
    with pytest.raises(TypeError):
        build_config['repr_function'] = 123

    with pytest.raises(KeyError):
        build_config['some_extra_config']
    build_config['some_extra_config'] = 'something'
    assert build_config['some_extra_config'] == 'something'


def test_job_config_with_dependencies():
    config = JobControlConfig.from_string("""
    jobs:
        - id: foo
          function: mymodule.foo
          dependencies: []

        - id: bar
          function: mymodule.bar
          dependencies: ['foo']

        - id: baz
          function: mymodule.baz
          dependencies: ['foo', 'bar']
    """)

    # Make sure they are still the same method.
    # Note that comparing with ``is`` will fail as they are *not*
    # actually the same method anymore..
    assert config.get_job == config.get_job_config
    assert JobControlConfig.get_job == JobControlConfig.get_job_config

    assert config.get_job('foo')['dependencies'] == []
    assert config.get_job('bar')['dependencies'] == ['foo']
    assert config.get_job('baz')['dependencies'] == ['foo', 'bar']

    assert config.get_job_deps('foo') == []
    assert config.get_job_deps('bar') == ['foo']
    assert config.get_job_deps('baz') == ['foo', 'bar']

    assert config.get_job_revdeps('foo') == ['bar', 'baz']
    assert config.get_job_revdeps('bar') == ['baz']
    assert config.get_job_revdeps('baz') == []

    assert config.get_job_deps('does-not-exist') == []
    assert config.get_job_revdeps('does-not-exist') == []


def test_build_config_var_deletion():
    build_config = BuildConfig()

    assert build_config['function'] is None
    build_config['function'] = 'some:function'
    assert build_config['function'] == 'some:function'
    del build_config['function']
    assert build_config['function'] is None

    with pytest.raises(KeyError):
        build_config['custom_var']
    build_config['custom_var'] = 'Some value here'
    assert build_config['custom_var'] == 'Some value here'
    del build_config['custom_var']
    with pytest.raises(KeyError):
        build_config['custom_var']


def test_jobcontrol_config_exceptions():
    with pytest.raises(TypeError):
        JobControlConfig('This is not a dict')

    with pytest.raises(TypeError) as excinfo:
        JobControlConfig({'storage': ['not', 'a', 'string']})
    assert excinfo.value.message == 'storage must be a string'

    with pytest.raises(TypeError) as excinfo:
        JobControlConfig.from_string("""
        jobs:
            - missing: id
        """)
    assert excinfo.value.message == 'Job id cannot be None'

    with pytest.raises(ValueError) as excinfo:
        JobControlConfig.from_string("""
        jobs:
            - id: foo
            - id: bar
            - id: foo
        """)
    assert excinfo.value.message == 'Duplicate job id: foo'

    with pytest.raises(TypeError) as excinfo:
        JobControlConfig.from_string("""
        jobs:
            - id: something
              title: ['not', 'a', 'string']
        """)
    assert excinfo.value.message == 'title must be a string, got list instead'

    with pytest.raises(TypeError) as excinfo:
        JobControlConfig.from_string("""
        jobs:
            - id: something
              notes: ['not', 'a', 'string']
        """)
    assert excinfo.value.message == 'notes must be a string, got list instead'


def test_build_config_exceptions():
    with pytest.raises(TypeError):
        BuildConfig('This is not a dict')


def test_build_config_pickle_unpickle():
    import pickle

    config = JobControlConfig.from_string("""
    webapp:
        PORT: 5000
    jobs:
        - id: foo
        - id: bar
          dependencies: ['foo']
          args:
              - !retval 'foo'
    """)

    pickled_config = pickle.dumps(config)
    unpickled_config = pickle.loads(pickled_config)

    assert isinstance(unpickled_config, JobControlConfig)
    assert unpickled_config == config
    assert not (unpickled_config != config)  # test __ne__
    assert len(unpickled_config.jobs) == 2
    for job in unpickled_config.jobs:
        assert isinstance(job, BuildConfig)
