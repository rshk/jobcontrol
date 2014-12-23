from flask import Blueprint, request, url_for

from jobcontrol.utils.web import json_view


api_views = Blueprint('api', __name__)


def get_jc():
    from flask import current_app
    return current_app.config['JOBCONTROL']


# @api_views.app_errorhandler(404)
# @json_view
# def handle_404(err):
#     return {'message': 'Not found'}


# @api_views.app_errorhandler(500)
# @json_view
# def handle_500(err):
#     return {'message': 'Server error'}


def _job_to_json(job):
    return {
        'id': job.id,
        'title': job.config['title'],
        'dependencies': job.config['dependencies'],
        'link': url_for('.job_info', job_id=job.id),
    }


@api_views.route('/job/', methods=['GET'])
@json_view
def jobs_list():
    filter_tags = []
    if 'tag' in request.args:
        filter_tags = request.args.getlist('tag')

    jobs = get_jc().iter_jobs()
    if filter_tags:
        jobs = (x for x in jobs
                if all(t in x.config.get('tags', [])
                       for t in filter_tags))

    return [_job_to_json(x) for x in jobs]


@api_views.route('/job/<string:job_id>', methods=['GET'])
@json_view
def job_info(job_id):
    jc = get_jc()
    job = jc.get_job(job_id)
    return _job_to_json(job)


@api_views.route('/job/<string:job_id>/run', methods=['POST'])
@json_view
def job_run_submit(job_id):
    from jobcontrol.async.tasks import run_build

    jc = get_jc()
    jc.get_celery_app()  # Make sure it's configured

    build = jc.create_build(job_id)
    run_build.delay(build.id)

    return {
        'build_id': build.id
    }


# todo: add catch-all view for 404 pages?
