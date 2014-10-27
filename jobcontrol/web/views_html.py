from __future__ import division

from flask import Blueprint, render_template, redirect, url_for, flash
import colorsys


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

        if build['start_time'] is not None:
            build['start_time'] = build['start_time'].strftime(DATE_FORMAT)
        if build['end_time'] is not None:
            build['end_time'] = build['end_time'].strftime(DATE_FORMAT)

        yield build


def _fmt_progress(cur, tot):
    if tot == 0:
        return 'N/A'
    return '{0}/{1} ({2:.1f}%)'.format(cur, tot, cur * 100.0 / tot)


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
    return render_template(
        'job-info.jinja',
        job=jc.storage.get_job(job_id),
        builds=_format_build_records(jc.storage.get_job_builds(job_id)))


@html_views.route('/job/<int:job_id>/edit', methods=['GET'])
def job_edit(job_id):
    return render_template(
        'job-edit.jinja',
        job=get_jc().storage.get_job(job_id))


@html_views.route('/job/<int:job_id>/edit/submit', methods=['POST'])
def job_edit_submit(job_id):
    # Do stuff
    # Redirect to job_edit page
    pass


@html_views.route('/job/<int:job_id>/run', methods=['GET'])
def job_run(job_id):
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
