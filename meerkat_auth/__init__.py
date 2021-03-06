"""
meerkat_auth.py

Registering root Flask app services for the Meerkat Authentication module.
"""
from flask import Flask, abort, g, redirect, render_template
from flask_babel import Babel
from raven.contrib.flask import Sentry
import os

# Create the Flask app
app = Flask(__name__)
babel = Babel(app)
config_object = os.getenv('CONFIG_OBJECT', 'meerkat_auth.config.Production')
app.config.from_object(config_object)
app.config.from_envvar('MEERKAT_AUTH_SETTINGS', silent=True)

# Set up sentry error monitoring
if app.config["SENTRY_DNS"]:
    sentry = Sentry(app, dsn=app.config["SENTRY_DNS"])
else:
    sentry = None

from meerkat_auth.views.users import users_blueprint
from meerkat_auth.views.roles import roles_blueprint
from meerkat_auth.views.auth import auth_blueprint


# Internationalisation for the backend
@babel.localeselector
def get_locale():
    return g.get("language", app.config["DEFAULT_LANGUAGE"])


# display something at /
@app.route("/")
def root():
    """Display something at /."""
    return redirect(app.config["DEFAULT_LANGUAGE"] + "/")


@app.route('/<language>/')
def index(language):
    """Display something at /<language>/."""
    g.language = language
    app.logger.warning(g.language)
    return render_template(
        'login.html',
        root=app.config['ROOT_URL']
    )


@users_blueprint.url_value_preprocessor
@roles_blueprint.url_value_preprocessor
def pull_lang_code(endpoint, values):
    if not values.get("language", ""):
        values["language"] = g.language
    if values["language"] not in app.config["SUPPORTED_LANGUAGES"]:
        abort(404, "Language not supported")
    else:
        g.language = values.pop('language')


@users_blueprint.url_defaults
@roles_blueprint.url_defaults
def add_language_code(endpoint, values):
    values.setdefault('language', app.config["DEFAULT_LANGUAGE"])

# Register the Blueprint modules for the backend
app.register_blueprint(users_blueprint, url_prefix='/<language>/users')
app.register_blueprint(roles_blueprint, url_prefix='/<language>/roles')
app.register_blueprint(auth_blueprint, url_prefix='/api')


# Handle errors
@app.errorhandler(401)
@app.errorhandler(403)
@app.errorhandler(404)
@app.errorhandler(410)
@app.errorhandler(418)
@app.errorhandler(500)
@app.errorhandler(501)
@app.errorhandler(502)
def error500(error):
    """
    Serves page for generic error.

    Args:
        error (int): The error code given by the error handler.
    """
    return render_template('error.html', error=error)
