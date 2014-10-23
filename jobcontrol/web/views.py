from flask import Blueprint

from jobcontrol.utils.web import json_view


api = Blueprint('api', __name__)


@api.app_errorhandler(404)
@json_view
def handle_404(err):
    return {'message': 'Not found'}


@api.app_errorhandler(500)
@json_view
def handle_500(err):
    return {'message': 'Server error'}


@api.route('/jobs/', methods=['GET'])
@json_view
def jobs_get():
    pass


@api.route('/jobs/', methods=['POST'])
@json_view
def job_create():
    pass


@api.route('/jobs/<int:job_id>', methods=['GET'])
@json_view
def job_get():
    pass


@api.route('/jobs/<int:job_id>', methods=['PUT'])
@json_view
def job_update():
    pass


@api.route('/jobs/<int:job_id>', methods=['DELETE'])
@json_view
def job_delete():
    pass
