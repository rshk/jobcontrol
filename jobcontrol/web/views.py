from flask import Blueprint, request, url_for, current_app


api = Blueprint('api', __name__)


@api.route('/jobs/', methods=['GET'])
def jobs_get():
    pass


@api.route('/jobs/', methods=['POST'])
def job_create():
    pass


@api.route('/jobs/<int:job_id>', methods=['GET'])
def job_get():
    pass


@api.route('/jobs/<int:job_id>', methods=['PUT'])
def job_update():
    pass


@api.route('/jobs/<int:job_id>', methods=['DELETE'])
def job_delete():
    pass
