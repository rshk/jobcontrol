import flask

from jobcontrol.web.views_api import api_views
from jobcontrol.web.views_html import html_views


app = flask.Flask('jobcontrol.web')
app.register_blueprint(api_views, url_prefix='/api/1')
app.register_blueprint(html_views, url_prefix='')
