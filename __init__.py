from flask import Flask, flash, make_response, render_template, request, Response
from flask.ext.socketio import SocketIO
from flask_bootstrap import Bootstrap
from flask.ext.login import LoginManager, UserMixin, current_user, login_required, login_user
from werkzeug.exceptions import default_exceptions
from eve import RFC1123_DATE_FORMAT
from websocket import create_ws

import aws_data

from base64 import b64decode
from datetime import datetime
import traceback
import sys
import requests
import json

from forms import CommandAppForm, CreateAppForm, DeleteAppForm, EditAppForm
from forms import DeleteJobForm

API_QUERY_SORT_UPDATED_DESCENDING = '?sort=-_updated'

# FIXME: Static conf to externalize with Flask-Appconfig
headers = {'Content-type': 'application/json', 'Accept': 'text/plain'}
url_apps = 'http://localhost:5000/apps'
url_jobs = 'http://localhost:5000/jobs'

# Helpers
def format_success_message(success_message, result):
    """
    >>> result = {"_updated": "Thu, 25 Jun 2015 16:35:27 GMT", "_links": {"self": {"href": "jobs/558c2dcf745f423d9babf52d", "title": "job"}}, "_created": "Thu, 25 Jun 2015 16:35:27 GMT", "_status": "OK", "_id": "558c2dcf745f423d9babf52d", "_etag": "6297ef1e01d45784fa7086191306c4986d4ba8a0"}
    >>> format_success_message("success_message", result)
    "success_message: <a href='/web/jobs/558c2dcf745f423d9babf52d' title='job'>jobs/558c2dcf745f423d9babf52d</a>"
    """
    formatted_message = success_message
    links = result.get('_links', [])
    if 'self' in links:
        link = links['self']
        formatted_message += ": <a href='/web/{href}' title='{title}'>{href}</a>".format(href=link.get('href', ''), title=link.get('title', ''))
    return formatted_message

def do_request(method, url, data, headers, success_message, failure_message):
    try:
        result = method(url=url, data=data, headers=headers, auth=current_user.auth)
        status_code = result.status_code
        message = result.content
        if status_code in [200, 201, 204]:
            flash(format_success_message(success_message, result.json()), 'success')
        else:
            flash(failure_message, 'warning')
    except:
        traceback.print_exc()
        message = 'Failure: %s' % (sys.exc_info()[1])
        flash(failure_message, 'danger')
    print message
    return message

def handle_response_status_code(status_code):
    if status_code >= 300:
        raise default_exceptions[status_code]

def get_ghost_apps(auth, query=None):
    try:
        url = url_apps + API_QUERY_SORT_UPDATED_DESCENDING
        if query:
            url += "&where=" + query
        result = requests.get(url, headers=headers, auth=auth)
        handle_response_status_code(result.status_code)
        apps = result.json().get('_items', [])
        for app in apps:
            try:
                app['_created'] = datetime.strptime(app['_created'], RFC1123_DATE_FORMAT)
                app['_updated'] = datetime.strptime(app['_updated'], RFC1123_DATE_FORMAT)
            except:
                traceback.print_exc()
    except:
        traceback.print_exc()
        message = 'Failure: %s' % (sys.exc_info()[1])
        flash(message, 'danger')
        apps = ['Failed to retrieve Apps']

    return apps

def get_ghost_jobs(auth, query=None):
    try:
        url = url_jobs + API_QUERY_SORT_UPDATED_DESCENDING
        if query:
            url += "&where=" + query
        result = requests.get(url, headers=headers, auth=auth)
        handle_response_status_code(result.status_code)
        jobs = result.json().get('_items', [])
        for job in jobs:
            try:
                job['_created'] = datetime.strptime(job['_created'], RFC1123_DATE_FORMAT)
                job['_updated'] = datetime.strptime(job['_updated'], RFC1123_DATE_FORMAT)
            except:
                traceback.print_exc()
    except:
        traceback.print_exc()
        message = 'Failure: %s' % (sys.exc_info()[1])
        flash(message, 'danger')
        jobs = ['Failed to retrieve Jobs']

    return jobs

# Web UI App
def create_app():
    app = Flask(__name__)

    app.config.update(
        SECRET_KEY='a random string',
        WTF_CSRF_SECRET_KEY='a random string'
    )

    Bootstrap(app)

    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager._login_disabled = False

    @login_manager.unauthorized_handler
    def unauthorized():
        return Response('Please provide proper credentials', 401, {'WWW-Authenticate': 'Basic realm="Login Required"'})

    @login_manager.request_loader
    def load_user_from_request(request):
        basic_auth = request.headers.get('Authorization')

        if basic_auth:
            try:
                basic_auth = b64decode(basic_auth.replace('Basic ', '', 1)).split(':')
                user = UserMixin()
                user.id = basic_auth[0]
                user.auth = tuple(basic_auth)
                
                # Try to list apps to verify credentials
                response = requests.get(url_apps, headers=headers, auth=user.auth)
                
                if response.status_code == 200:
                    return user
            except:
                traceback.print_exc()
                message = 'Failure: %s' % (sys.exc_info()[1])
                flash(message, 'danger')

        return None

    @app.before_request
    @login_required
    def before_request():
        pass

    @app.route('/web/apps')
    def web_app_list():
        query = request.args.get('where', None)
        apps = get_ghost_apps(current_user.auth, query)
        return render_template('app_list.html', apps=apps)

    @app.route('/web/apps/create', methods=['GET', 'POST'])
    def web_app_create():
        form = CreateAppForm()

        # Perform validation
        if form.validate_on_submit():
            app = {}
            form.map_to_app(app)

            message = do_request(requests.post, url=url_apps, data=json.dumps(app), headers=headers, success_message='Application created', failure_message='Application creation failed')

            return render_template('action_completed.html', message=message)

        app_id = request.args.get('clone_from', None)
        if app_id:
            try:
                result = requests.get(url_apps + '/' + app_id, headers=headers, auth=current_user.auth)
                app = result.json()
                handle_response_status_code(result.status_code)
                form.map_from_app(app)
            except:
                traceback.print_exc()
                message = 'Failure: %s' % (sys.exc_info()[1])
                flash(message, 'danger')

        # Display default template in GET case
        return render_template('app_edit.html', form=form, edit=False)

    @app.route('/web/apps/<app_id>', methods=['GET'])
    def web_app_view(app_id):
        try:
            # Get App data
            result = requests.get(url_apps + '/' + app_id, headers=headers, auth=current_user.auth)
            app = result.json()
            handle_response_status_code(result.status_code)
            
            # Decode module scripts
            for module in app.get('modules', []):
                if 'build_pack' in module:
                    module['build_pack'] = b64decode(module['build_pack'])
                if 'pre_deploy' in module:
                    module['pre_deploy'] = b64decode(module['pre_deploy'])
                if 'post_deploy' in module:
                    module['post_deploy'] = b64decode(module['post_deploy'])
        except:
            traceback.print_exc()
            message = 'Failure: %s' % (sys.exc_info()[1])
            flash(message, 'danger')

        return render_template('app_view.html', app=app)

    @app.route('/web/apps/<app_id>/edit', methods=['GET', 'POST'])
    def web_app_edit(app_id):
        form = EditAppForm()

        # Perform validation
        if form.validate_on_submit():
            local_headers = headers.copy()
            local_headers['If-Match'] = form.etag.data

            # Remove read-only fields that cannot be changed
            del form.name
            del form.env
            del form.role

            # Update Application
            app = {}
            form.map_to_app(app)

            message = do_request(requests.patch, url=url_apps + '/' + app_id, data=json.dumps(app), headers=local_headers, success_message='Application updated', failure_message='Application update failed')

            return render_template('action_completed.html', message=message)

        # Get App data on first access
        if not form.etag.data:
            try:
                result = requests.get(url_apps + '/' + app_id, headers=headers, auth=current_user.auth)
                handle_response_status_code(result.status_code)
                app = result.json()
                form.map_from_app(app)
            except:
                traceback.print_exc()
                message = 'Failure: %s' % (sys.exc_info()[1])
                flash(message, 'danger')

        # Remove alternative options from select fields that cannot be changed
        form.env.choices = [(form.env.data, form.env.data)]
        form.role.choices = [(form.role.data, form.role.data)]

        # Display default template in GET case
        return render_template('app_edit.html', form=form, edit=True)

    @app.route('/web/apps/<app_id>/command', methods=['GET', 'POST'])
    def web_app_command(app_id):
        form = CommandAppForm()

        # Get Application Modules
        try:
            result = requests.get(url_apps + '/' + app_id, headers=headers, auth=current_user.auth)
            handle_response_status_code(result.status_code)
            app = result.json()
            form.module_name.choices = [('', '')] + [(module['name'], module['name']) for module in app['modules']]
        except:
            traceback.print_exc()
            message = 'Failure: %s' % (sys.exc_info()[1])
            flash(message, 'danger')
            form.module_name.choices = [('', 'Failed to retrieve Application Modules')]

        # Perform validation
        if form.validate_on_submit():
            job = {}
            job['command'] = form.command.data
            job['app_id'] = app_id

            # Process modules
            modules = []

            if form.module_name.data:
                module = {}
                if form.command.data == 'deploy':
                    module['name'] = form.module_name.data
                    module['rev'] = form.module_rev.data or 'HEAD'
                modules.append(module)

            if modules:
                job['modules'] = modules

            # Process options
            options = []

            if form.command.data == 'rollback':
                # In case of rollback, option[0] must be the deploy ID
                options.append(form.module_deploy_id.data)

            if len(options) > 0:
                job['options'] = options

            message = do_request(requests.post, url=url_jobs, data=json.dumps(job), headers=headers, success_message='Job created', failure_message='Job creation failed')

            return render_template('action_completed.html', message=message)

        # Display default template in GET case
        return render_template('app_command.html', form=form, app=app)

    @app.route('/web/apps/<app_id>/delete', methods=['GET', 'POST'])
    def web_app_delete(app_id):
        form = DeleteAppForm()

        # Perform validation
        if form.validate_on_submit and form.confirmation.data == 'yes':
            local_headers = headers.copy()
            local_headers['If-Match'] = form.etag.data

            message = do_request(requests.delete, url=url_apps + '/' + app_id, data=None, headers=local_headers, success_message='Application deleted', failure_message='Application deletion failed')

            return render_template('action_completed.html', message=message)

        # Get Application etag
        try:
            result = requests.get(url_apps + '/' + app_id, headers=headers, auth=current_user.auth)
            app = result.json()
            handle_response_status_code(result.status_code)
            form.etag.data = app['_etag']
        except:
            traceback.print_exc()
            message = 'Failure: %s' % (sys.exc_info()[1])
            flash(message, 'danger')

        # Display default template in GET case
        return render_template('app_delete.html', form=form, app=app)

    @app.route('/web/jobs')
    def web_job_list():
        query = request.args.get('where', None)
        jobs = get_ghost_jobs(current_user.auth, query)
        apps_name_cache = {}
        apps_env_cache = {}
        for job in jobs:
            app_id = job['app_id']
            app_name = apps_name_cache.get(app_id, None)
            app_env = apps_env_cache.get(app_id, None)
            if app_name is None:
                try:
                    # Get App data
                    result = requests.get(url_apps + '/' + app_id, headers=headers, auth=current_user.auth)
                    handle_response_status_code(result.status_code)
                    app = result.json()
                    apps_name_cache[app_id] = app_name = app['name']
                    apps_env_cache[app_id] = app_env = app['env']
                except:
                    apps_name_cache[app_id] = app_name = 'N/A'
                    apps_env_cache[app_id] = app_env = 'N/A'
            job['app_name'] = app_name
            job['app_env'] = app_env

        return render_template('job_list.html', jobs=jobs)

    @app.route('/web/jobs/<job_id>', methods=['GET'])
    def web_job_view(job_id):
        try:
            # Get Job data
            result = requests.get(url_jobs + '/' + job_id, headers=headers, auth=current_user.auth)
            job = result.json()
            handle_response_status_code(result.status_code)
        except:
            traceback.print_exc()
            message = 'Failure: %s' % (sys.exc_info()[1])
            flash(message, 'danger')

        return render_template('job_view.html', job=job)

    @app.route('/web/jobs/<job_id>/delete', methods=['GET', 'POST'])
    def web_job_delete(job_id):
        form = DeleteJobForm()

        # Perform validation
        if form.validate_on_submit and form.confirmation.data == 'yes':
            local_headers = headers.copy()
            local_headers['If-Match'] = form.etag.data

            message = do_request(requests.delete, url=url_jobs + '/' + job_id, data=None, headers=local_headers, success_message='Job deleted', failure_message='Job deletion failed')

            return render_template('action_completed.html', message=message)

        # Get job etag
        try:
            result = requests.get(url_jobs + '/' + job_id, headers=headers, auth=current_user.auth)
            job = result.json()
            handle_response_status_code(result.status_code)
            if job.get('status', '') in ['done', 'failed']:
                form.etag.data = job['_etag']
        except:
            traceback.print_exc()
            message = 'Failure: %s' % (sys.exc_info()[1])
            flash(message, 'danger')

        # Display default template in GET case
        return render_template('job_delete.html', form=form, job=job)

    return app
