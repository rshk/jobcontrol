from jobcontrol.job_conf import dump, load, prepare_args, Retval


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
