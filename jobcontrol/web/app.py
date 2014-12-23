import flask
from flask import request, session, abort

from jobcontrol.web.views_api import api_views
from jobcontrol.web.views_html import html_views
from jobcontrol.utils.web import generate_csrf_token
from jobcontrol.web.template_filters import filters


app = flask.Flask('jobcontrol.web')
app.register_blueprint(api_views, url_prefix='/api/1')
app.register_blueprint(html_views, url_prefix='')


# IMPORTANT: This *must*  be set to something random
app.secret_key = "This is no secret"


@app.before_request
def csrf_protect():
    # todo: re-enable this only on *web* views, not on the API
    pass
    # if request.method == 'POST':
    #     # token = session.pop('_csrf_token', None)
    #     token = session.get('_csrf_token')
    #     if not token or token != request.form.get('_csrf_token'):
    #         abort(403)


app.jinja_env.globals['csrf_token'] = generate_csrf_token

app.jinja_env.filters.update(filters)
