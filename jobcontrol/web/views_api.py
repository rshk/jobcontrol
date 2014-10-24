from flask import Blueprint

from jobcontrol.utils.web import json_view


api_views = Blueprint('api', __name__)


@api_views.app_errorhandler(404)
@json_view
def handle_404(err):
    return {'message': 'Not found'}


@api_views.app_errorhandler(500)
@json_view
def handle_500(err):
    return {'message': 'Server error'}


@api_views.route('/jobs/', methods=['GET'])
@json_view
def jobs_get():
    pass


@api_views.route('/jobs/', methods=['POST'])
@json_view
def job_create():
    pass


@api_views.route('/jobs/<int:job_id>', methods=['GET'])
@json_view
def job_get():
    pass


@api_views.route('/jobs/<int:job_id>', methods=['PUT'])
@json_view
def job_update():
    pass


@api_views.route('/jobs/<int:job_id>', methods=['DELETE'])
@json_view
def job_delete():
    pass
