from __future__ import division

from collections import defaultdict
import ast
import colorsys

from flask import (Blueprint, render_template, redirect, url_for,
                   flash, request, abort)

from jobcontrol.utils import import_object


class FormError(Exception):
    pass


html_views = Blueprint('webui', __name__)


DATE_FORMAT = '%Y-%m-%d %H:%M:%S'


def get_jc():
    from flask import current_app
    return current_app.config['JOBCONTROL']


def _format_build_records(iterable):
    for build in iterable:
        if build['progress_total'] == 0:
            build['progress_pc_n'] = 0
        else:
            build['progress_pc_n'] = (
                build['progress_current'] * 100.0 / build['progress_total'])

        build['progress_pc'] = format(build['progress_pc_n'], '.2f')

        build['progress'] = _fmt_progress(build['progress_current'],
                                          build['progress_total'])

        # Hue: 0 -> 120
        hue = build['progress_pc_n'] * 120 / 100

        color = ''.join([
            format(int(x * 255), '02X')
            for x in colorsys.hsv_to_rgb(hue / 360.0, .8, .8)])
        build['progress_color'] = '#' + color

        # if build['start_time'] is not None:
        #     build['start_time'] = build['start_time'].strftime(DATE_FORMAT)
        # if build['end_time'] is not None:
        #     build['end_time'] = build['end_time'].strftime(DATE_FORMAT)

        yield build


def _fmt_progress(cur, tot):
    if tot == 0:
        return 'N/A'
    return '{0}/{1} ({2:.1f}%)'.format(cur, tot, cur * 100.0 / tot)


def _add_job_info(job):
    jc = get_jc()
    job['call_code'] = _get_call_code(job)
    job['call_code_html'] = _highlight_code_html(job['call_code'])
    job['deps'] = jc.storage.get_job_deps(job['id'])
    job['revdeps'] = jc.storage.get_job_revdeps(job['id'])

    try:
        func = import_object(job['function'])
    except Exception as e:
        docstring = "Error: {0!r}".format(e)
    else:
        docstring = _format_function_doc(func)

    job['function_doc'] = docstring


@html_views.route('/', methods=['GET'])
def index():
    return redirect(url_for('webui.jobs_list'))


@html_views.route('/job/', methods=['GET'])
def jobs_list():
    return render_template('jobs-list.jinja',
                           jobs=list(get_jc().storage.iter_jobs()))


@html_views.route('/job/<int:job_id>', methods=['GET'])
def job_info(job_id):
    jc = get_jc()
    builds = jc.storage.get_job_builds(job_id, order='desc')

    job = jc.storage.get_job(job_id)
    _add_job_info(job)

    return render_template(
        'job-info.jinja',
        job=job,
        builds=_format_build_records(builds))


@html_views.route('/job/<int:job_id>/edit', methods=['GET'])
def job_edit(job_id):
    job = get_jc().storage.get_job(job_id)
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

    data['title'] = form_data['title']

    # todo: check for function existence? (maybe just warning..)
    data['function'] = form_data['function']

    # ---------- args

    try:
        args = ast.literal_eval(form_data['args'])
    except:
        errors['args'].append('Parse failed for arguments (check syntax)')
    else:
        if isinstance(args, tuple):
            data['args'] = args
        else:
            errors['args'].append('Arguments must be a tuple')

    # ---------- kwargs

    try:
        kwargs = ast.literal_eval(form_data['kwargs'])
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
    pass


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
    pass


@html_views.route('/build/<int:build_id>', methods=['GET'])
def build_info(build_id):
    jc = get_jc()
    build = jc.storage.get_build(build_id)
    job = jc.storage.get_job(build['job_id'])
    _add_job_info(job)

    build = list(_format_build_records([build]))[0]
    messages = jc.storage.iter_log_messages(
        job_id=build['job_id'], build_id=build_id)

    return render_template(
        'build-info.jinja',
        job=job, build=build, messages=messages)


def _get_call_code(job):
    module, func = job['function'].split(':')

    call_args = []
    for arg in job['args']:
        call_args.append(repr(arg))
    for key, val in sorted(job['kwargs'].iteritems()):
        call_args.append("{0}={1!r}".format(key, val))

    return "\n".join((
        "from {0} import {1}".format(module, func),
        "{0}(\n    {1})".format(func, ",\n    ".join(call_args))))


def _highlight_code_html(code):
    from pygments import highlight
    from pygments.lexers import PythonLexer
    from pygments.formatters import HtmlFormatter
    return highlight(code, PythonLexer(), HtmlFormatter())


def _format_function_doc(func):
    import inspect
    import docutils.core

    doc = inspect.getdoc(func)
    return docutils.core.publish_parts(doc, writer_name='html')['fragment']
