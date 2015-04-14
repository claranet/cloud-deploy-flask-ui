from flask import Flask, flash, make_response, render_template, request, Response

from flask_bootstrap import Bootstrap

from flask.ext.login import LoginManager, UserMixin, current_user, login_required, login_user

from eve import RFC1123_DATE_FORMAT

import aws_data

from base64 import b64decode
from datetime import datetime
import traceback
import sys
import requests
import json

from .forms import CommandAppForm, CreateAppForm, DeleteAppForm, EditAppForm

# FIXME: Static conf to externalize with Flask-Appconfig
headers = {'Content-type': 'application/json', 'Accept': 'text/plain'}
url_apps = 'http://localhost:5000/apps'
url_jobs = 'http://localhost:5000/jobs'

# Helpers
def get_ghost_apps(auth):
    try:
        apps = requests.get(url_apps, headers=headers, auth=auth).json().get('_items', [])
        for app in apps:
            try:
                app['_created'] = datetime.strptime(app['_created'], RFC1123_DATE_FORMAT)
                app['_updated'] = datetime.strptime(app['_updated'], RFC1123_DATE_FORMAT)
            except:
                traceback.print_exc()
    except:
        traceback.print_exc()
        apps = ['Failed to retrieve Apps']

    return apps

def get_ghost_jobs(auth):
    try:
        jobs = requests.get(url_jobs, headers=headers, auth=auth).json().get('_items', [])
        for job in jobs:
            try:
                job['_created'] = datetime.strptime(job['_created'], RFC1123_DATE_FORMAT)
                job['_updated'] = datetime.strptime(job['_updated'], RFC1123_DATE_FORMAT)
            except:
                traceback.print_exc()
    except:
        traceback.print_exc()
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
                pass

        return None

    @app.before_request
    @login_required
    def before_request():
        pass

    @app.route('/web/apps')
    def web_app_list():
        return render_template('app_list.html', apps=get_ghost_apps(current_user.auth))

    @app.route('/web/apps/create', methods=['GET', 'POST'])
    def web_app_create():
        form = CreateAppForm()

        # Perform validation
        if form.validate_on_submit():
            app = {}
            form.map_to_app(app)

            try:
                message = requests.post(url=url_apps, data=json.dumps(app), headers=headers, auth=current_user.auth).content
                print(message)
                flash('Application created.')
            except:
                traceback.print_exc()
                message = 'Failed to create Application (%s)' % (sys.exc_info()[1])

            return render_template('action_completed.html', message=message)

        app_id = request.args.get('clone_from', None)
        if app_id:
            try:
                app = requests.get(url_apps + '/' + app_id, headers=headers, auth=current_user.auth).json()
                
                form.map_from_app(app)
            except:
                traceback.print_exc()

        # Display default template in GET case
        return render_template('app_edit.html', form=form, edit=False)

    @app.route('/web/apps/<app_id>', methods=['GET'])
    def web_app_view(app_id):
        try:
            # Get App data
            app = requests.get(url_apps + '/' + app_id, headers=headers, auth=current_user.auth).json()

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

            try:
                message = requests.patch(url=url_apps + '/' + app_id, data=json.dumps(app), headers=local_headers, auth=current_user.auth).content
                print(message)
                flash('Application updated.')
            except:
                traceback.print_exc()
                message = 'Failed to update App (%s)' % (sys.exc_info()[1])

            return render_template('action_completed.html', message=message)

        # Get App data on first access
        if not form.etag.data:
            try:
                app = requests.get(url_apps + '/' + app_id, headers=headers, auth=current_user.auth).json()
                
                form.map_from_app(app)
            except:
                traceback.print_exc()

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
            modules = requests.get(url_apps + '/' + app_id, headers=headers, auth=current_user.auth).json()['modules']
            form.module_name.choices = [('', '')] + [(module['name'], module['name']) for module in modules]
        except:
            traceback.print_exc()
            form.module_name.choices = [('', 'Failed to retrieve Application Modules')]

        # Perform validation
        if form.validate_on_submit():
            job = {}
            job['user'] = 'web'
            job['command'] = form.command.data
            job['app_id'] = app_id

            module = {}
            if form.module_name.data:
                module['name'] = form.module_name.data
                modules = []
                modules.append(module)
                job['modules'] = modules

            try:
                message = requests.post(url=url_jobs, data=json.dumps(job), headers=headers, auth=current_user.auth).content
                print(message)
                flash('Job created.')
            except:
                traceback.print_exc()
                message = 'Failed to create Job (%s)' % (sys.exc_info()[1])

            return render_template('action_completed.html', message=message)

        # Display default template in GET case
        return render_template('app_command.html', form=form)

    @app.route('/web/apps/<app_id>/delete', methods=['GET', 'POST'])
    def web_app_delete(app_id):
        form = DeleteAppForm()

        # Perform validation
        if form.validate_on_submit and form.confirmation.data == 'yes':
            local_headers = headers.copy()
            local_headers['If-Match'] = form.etag.data

            try:
                message = requests.delete(url=url_apps + '/' + app_id, headers=local_headers, auth=current_user.auth).content
                print(message)
                flash('Application deleted.')
            except:
                traceback.print_exc()
                message = 'Failed to delete App (%s)' % (sys.exc_info()[1])

            return render_template('action_completed.html', message=message)

        # Get Application etag
        try:
            form.etag.data = requests.get(url_apps + '/' + app_id, headers=headers, auth=current_user.auth).json()['_etag']
        except:
            traceback.print_exc()

        # Display default template in GET case
        return render_template('app_delete.html', form=form)

    @app.route('/web/jobs')
    def web_job_list():
        return render_template('job_list.html', jobs=get_ghost_jobs(current_user.auth))

    @app.route('/web/jobs/<job_id>', methods=['GET'])
    def web_job_view(job_id):
        try:
            # Get Job data
            job = requests.get(url_jobs + '/' + job_id, headers=headers, auth=current_user.auth).json()

        except:
            traceback.print_exc()

        return render_template('job_view.html', job=job)

    return app


def run_web_ui():
    app = create_app()
    app.run(host='0.0.0.0', port=5001, debug=True)
