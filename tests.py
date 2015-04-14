import flask

def create_test_app_context():
    app = flask.Flask(__name__)
    app.config.update(REQUEST_METHOD='GET', SERVER_NAME='localhost', SERVER_PORT='5000', SECRET_KEY='a random string', WTF_CSRF_SECRET_KEY='a random string')
    app.config['wsgi.url_scheme'] = 'http'
    app.app_context().push()
    app.request_context(app.config).push()
