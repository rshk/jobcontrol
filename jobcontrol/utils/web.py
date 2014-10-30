"""
Utilities for the RESTful API
"""

from functools import wraps
import json
import os
import binascii

from flask import request, make_response, session
from werkzeug.exceptions import BadRequest


def json_view(func):
    @wraps(func)
    def wrapper(*a, **kw):
        # todo: catch exceptions and rewrap + make sure they're all JSON
        rv = func(*a, **kw)
        if isinstance(rv, tuple):
            resp = make_response(json.dumps(rv[0]), *rv[1:])
        else:
            resp = make_response(json.dumps(rv))
        resp.headers['Content-type'] = 'application/json'
        return resp
    return wrapper


def _get_json_from_request():
    if request.headers.get('Content-type') != 'application/json':
        raise BadRequest(
            "Unsupported Content-type (expected application/json)")
    try:
        return json.loads(request.data)
    except:
        raise BadRequest('Error decoding json')


def generate_csrf_token():
    if '_csrf_token' not in session:
        session['_csrf_token'] = _generate_csrf_token()
    return session['_csrf_token']


def _generate_csrf_token():
    return binascii.hexlify(os.urandom(32))
