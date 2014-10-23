import flask

from datacat.web.views import api


app = flask.Flask('jobcontrol.web')
app.register_blueprint(api, url_prefix='/api/1')
