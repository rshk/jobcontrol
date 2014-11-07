from __future__ import division

from collections import defaultdict
import ast
# import colorsys

from flask import (Blueprint, render_template, redirect, url_for,
                   flash, request)

# from jobcontrol.utils import import_object


class FormError(Exception):
    pass


html_views = Blueprint('webui', __name__)


DATE_FORMAT = '%Y-%m-%d %H:%M:%S'


def get_jc():
    from flask import current_app
    return current_app.config['JOBCONTROL']


@html_views.route('/', methods=['GET'])
def index():
    return redirect(url_for('webui.jobs_list'))


@html_views.route('/job/', methods=['GET'])
def jobs_list():
    return render_template('jobs-list.jinja',
                           jobs=list(get_jc().iter_jobs()))


@html_views.route('/job/<int:job_id>', methods=['GET'])
def job_info(job_id):
    jc = get_jc()
    job = jc.get_job(job_id)
    builds = job.get_builds(order='desc')
    return render_template('job-info.jinja', job=job, builds=builds)


@html_views.route('/job/<int:job_id>/depgraph.<string:fmt>', methods=['GET'])
def job_depgraph(job_id, fmt):
    # todo: add reverse dependencies
    # todo: add colors to indicate job status (has builds, outdated, ..)
    # todo: figure out a way to add image map, for links

    jc = get_jc()

    try:
        import pygraphviz
    except:
        return 'PyGraphviz is not installed', 500

    depgraph = jc._create_job_depgraph(job_id, complete=True)
    graph = pygraphviz.AGraph(depgraph, directed=True,
                              name="Job {0} Dependency graph".format(job_id))

    graph.graph_attr['dpi'] = '70'  # Other values make things go wrong
    graph.graph_attr['splines'] = 'curved'

    graph.node_attr['fontsize'] = '14'
    graph.node_attr['fontname'] = 'monospace'

    graph.edge_attr['minlen'] = '1'
    graph.edge_attr['len'] = '1.5'  # Inches

    node = graph.get_node(job_id)
    node.attr['fontsize'] = '16'
    node.attr['penwidth'] = '3'
    # node.attr['color'] = '#ff0000'
    # node.attr['label'] = 'Job {0}'.format(job_id)

    for node in graph.nodes():
        job = jc.get_job(node)
        node.attr['URL'] = url_for('.job_info', job_id=node, _external=True)
        node.attr['target'] = '_top'
        node.attr['tooltip'] = job['title']

        node.attr['fontcolor'] = '#ffffff'
        node.attr['style'] = 'filled'
        node.attr['shape'] = 'circle'
        # node.attr['width'] = '.5'

        if int(node) == job_id:
            node.attr['penwidth'] = '3'
            node.attr['color'] = '#000000'
        else:
            node.attr['penwidth'] = '0'

        if job.has_successful_builds():
            if job.is_outdated():
                node.attr['fillcolor'] = '#f0ad4e'

            else:
                node.attr['fillcolor'] = '#5cb85c'

        elif job.has_builds():
            node.attr['fillcolor'] = '#d9534f'

        else:
            node.attr['fillcolor'] = '#777777'

    # todo: give different color to revdep edges
    # todo: detect loops, color edges in red

    graph.layout()

    if fmt == 'png':
        return graph.draw(format='png'), 200, {'content-type': 'image/png'}

    elif fmt == 'svg':
        return graph.draw(format='svg'), 200, {'content-type': 'image/svg+xml'}

    elif fmt == 'dot':
        return graph.draw(format='dot'), 200, {'content-type': 'text/plain'}

    return 'Unsupported format', 404


@html_views.route('/job/create', methods=['GET'])
def job_create():
    return render_template(
        'job-edit.jinja', job=None,
        form_data={},
        form_errors={})


@html_views.route('/job/create', methods=['POST'])
def job_create_submit():
    jc = get_jc()

    read_data = {
        'title': request.form['title'],
        'function': request.form['function'],
        'args': request.form['args'],
        'kwargs': request.form['kwargs'],
        'dependencies': request.form['dependencies'],
    }

    data, errors = _job_edit_form_process(read_data)

    if len(errors):
        flash("The form contains errors!", 'error')
        return render_template(
            'job-edit.jinja', job=None,
            form_data=read_data,
            form_errors=errors)

    job = jc.create_job(**data)
    flash('Job {0} created'.format(job.id), 'success')
    return redirect(url_for('.job_info', job_id=job.id))


@html_views.route('/job/<int:job_id>/edit', methods=['GET'])
def job_edit(job_id):
    job = get_jc().get_job(job_id)
    return render_template(
        'job-edit.jinja', job=job,
        form_data=_job_edit_form_prepare_values(job),
        form_errors={})


@html_views.route('/job/<int:job_id>/edit', methods=['POST'])
def job_edit_submit(job_id):
    jc = get_jc()
    job = jc.get_job(job_id)

    read_data = {
        'title': request.form['title'],
        'function': request.form['function'],
        'args': request.form['args'],
        'kwargs': request.form['kwargs'],
        'dependencies': request.form['dependencies'],
    }

    data, errors = _job_edit_form_process(read_data)

    if len(errors):
        flash("The form contains errors!", 'error')
        return render_template(
            'job-edit.jinja', job=job,
            form_data=read_data,
            form_errors=errors)

    job.update(**data)
    flash('Job {0} updated'.format(job_id), 'success')
    return redirect(url_for('.job_info', job_id=job_id))


def _job_edit_form_prepare_values(job):
    return {
        'title': job['title'],
        'function': job['function'],
        'args': repr(job['args']),
        'kwargs': repr(job['kwargs']),
        'dependencies': ', '.join(str(x) for x in job['dependencies']),
    }


def _job_edit_form_process(form_data):
    data = {}
    errors = defaultdict(list)

    data['title'] = form_data['title'].strip()

    # todo: check for function existence? (maybe just warning..)
    data['function'] = form_data['function'].strip()

    # ---------- args

    _args = form_data['args'].strip()
    if not _args:
        _args = '()'

    try:
        args = ast.literal_eval(_args)
    except:
        errors['args'].append('Parse failed for arguments (check syntax)')
    else:
        if isinstance(args, tuple):
            data['args'] = args
        else:
            errors['args'].append('Arguments must be a tuple')

    # ---------- kwargs

    _kwargs = form_data['kwargs'].strip()
    if not _kwargs:
        _kwargs = '{}'

    try:
        kwargs = ast.literal_eval(_kwargs)
    except:
        errors['kwargs'].append(
            'Parse failed for Keyword arguments (check syntax)')
    else:
        if isinstance(kwargs, dict):
            data['kwargs'] = kwargs
        else:
            errors['kwargs'].append('Keyword arguments must be a dict')

    # ---------- dependencies

    try:
        _deps = [x.strip() for x in form_data['dependencies'].split(',')]
        data['dependencies'] = [int(x) for x in _deps if x]

    except Exception as e:
        errors['dependencies'].append(str(e))

    return data, errors


@html_views.route('/job/<int:job_id>/run', methods=['GET'])
def job_run(job_id):
    # Todo: return confirmation form
    jc = get_jc()
    job = jc.get_job(job_id)
    return render_template('job-run-form.jinja', job=job)


@html_views.route('/job/<int:job_id>/run/submit', methods=['POST'])
def job_run_submit(job_id):
    # todo: CSRF protection!

    from jobcontrol.async.tasks import app as celery_app, build_job

    jc = get_jc()
    broker = 'redis://'  # todo: take from configuration
    celery_app.conf.JOBCONTROL = jc
    celery_app.conf.BROKER_URL = broker

    build_job.delay(job_id)
    flash('Job {0} build scheduled'.format(job_id), 'success')

    return redirect(url_for('.job_info', job_id=job_id))


@html_views.route('/job/<int:job_id>/delete', methods=['GET'])
def job_delete(job_id):
    job = get_jc().get_job(job_id)
    return render_template('job-delete.jinja', job=job)


@html_views.route('/build/<int:build_id>', methods=['GET'])
def build_info(build_id):
    jc = get_jc()
    build = jc.get_build(build_id)

    job = jc.get_job(build.job_id)

    messages = jc.storage.iter_log_messages(
        job_id=build.job_id,
        build_id=build_id)

    return render_template(
        'build-info.jinja',
        job=job, build=build, messages=messages)


@html_views.route('/autocomplete/function/<path:function_name>',
                  methods=['GET'])
def autocomplete_function_name(function_name):
    """
    Autocomplete the function name, returning a json object containing:

    - candidate completions (for module/function)
    - documentation for the function, if it is valid
    """
    pass


@html_views.route('/job/<int:job_id>/action', methods=['POST'])
def job_action(job_id):
    action = request.form['action']
    jc = get_jc()

    if action == 'build':
        from jobcontrol.async.tasks import app as celery_app, build_job

        broker = 'redis://'  # todo: take from configuration!!
        celery_app.conf.JOBCONTROL = jc
        celery_app.conf.BROKER_URL = broker

        build_job.delay(job_id)
        flash('Job {0} build scheduled'.format(job_id), 'success')

    elif action == 'delete':
        job = jc.get_job(job_id)
        job.delete()
        flash('Job {0} deleted'.format(job_id), 'success')
        return redirect(url_for('.jobs_list'))

    else:
        flash('Unsupported action: {0}'.format(action))

    # todo: return to caller page
    return redirect(url_for('.job_info', job_id=job_id))


@html_views.route('/build/<int:build_id>/action', methods=['POST'])
def build_action(build_id):
    action = request.form['action']
    jc = get_jc()

    if action == 'delete':
        build = jc.get_build(build_id)
        build.delete()

    else:
        flash('Unsupported action: {0}'.format(action))

    # todo: return to caller page
    return redirect(url_for('.build_info', build_id=build_id))
