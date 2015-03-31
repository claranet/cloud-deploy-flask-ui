from flask import Flask, render_template, request, make_response, flash

from flask_bootstrap import Bootstrap

from flask_wtf import Form
from flask_wtf.file import FileField
from flask_wtf.file import FileAllowed as FileAllowedValidator

from wtforms import FieldList, FormField, HiddenField, RadioField, SelectField, StringField, SubmitField
from wtforms.validators import DataRequired as DataRequiredValidator
from wtforms.validators import Regexp as RegexpValidator

from eve import RFC1123_DATE_FORMAT

import aws_data
import instance_role
import env

from base64 import b64encode
from datetime import datetime
import tempfile
import traceback
import os
import sys
import requests
import json

# FIXME: Static conf to externalize with Flask-Appconfig
auth = ('api', 'api')
headers = {'Content-type': 'application/json', 'Accept': 'text/plain'}
url_apps = 'http://localhost:5000/apps'
url_jobs = 'http://localhost:5000/jobs'

# Helpers
def get_ghost_apps():
    try:
        apps = requests.get(url_apps, headers=headers, auth=auth).json()['_items']
        for app in apps:
            try:
                app['_created'] = datetime.strptime(app['_created'], RFC1123_DATE_FORMAT)
                app['_updated'] = datetime.strptime(app['_updated'], RFC1123_DATE_FORMAT)
            except:
                traceback.print_exc()
    except:
        apps = ['Failed to retrieve Apps']

    return apps

def get_ghost_app_envs():
    return [(value, value) for value in env.env]

def get_ghost_app_roles():
    return [(value, value) for value in instance_role.role]

def get_ghost_mod_scopes():
    return [
        ('code', 'code'),
        ('system', 'system')
    ]

# FIXME: Get lists from AWS API
def get_aws_vps_ids():
    return [
        ('vpc-12345', 'vpc-12345'),
        ('vpc-7896', 'vpc-7896')
    ]

def get_aws_regions():
    return [
        ('eu-west-1', 'eu-west-1 (Ireland)'),
        ('us-east-1', 'us-east-1 (North Virginia)')
    ]

def get_aws_instance_types():
    return [(value, value) for value in aws_data.instance_type]


# Forms
class ModuleForm(Form):
    # Disable CSRF in module forms as they are AppForm subforms
    def __init__(self, csrf_enabled=False, *args, **kwargs):
        super(ModuleForm, self).__init__(csrf_enabled=csrf_enabled, *args, **kwargs)

    module_name = StringField('Name', validators=[DataRequiredValidator()])
    module_git_repo = StringField('Git Repository', validators=[DataRequiredValidator()])
    module_path = StringField('Path', validators=[DataRequiredValidator()])
    module_scope = SelectField('Scope', validators=[DataRequiredValidator()], choices=get_ghost_mod_scopes())
    module_build_pack = FileField('Build Pack', validators=[FileAllowedValidator(
        upload_set=('txt', 'json'),
        message='The build pack file can only have a .txt or .json extension')
    ])
    module_pre_deploy = FileField('Pre Deploy', validators=[FileAllowedValidator(
        upload_set=('txt', 'json'),
        message='The pre deploy file can only have a .txt or .json extension')
    ])
    module_post_deploy = FileField('Post Deploy', validators=[FileAllowedValidator(
        upload_set=('txt', 'json'),
        message='The post deploy file can only have a .txt or .json extension')
    ])

class AppForm(Form):
    name = StringField('Name', validators=[
        DataRequiredValidator(), 
        RegexpValidator(
            '^[a-zA-Z0-9_.+-]*$',
            message='The application name can only contain ASCII letters, digits or _.+- characters'
        )
    ])
    env = SelectField('Environment', validators=[DataRequiredValidator()], choices=get_ghost_app_envs())
    role = SelectField('Role', validators=[DataRequiredValidator()], choices=get_ghost_app_roles())

    # AWS properties
    region = SelectField('AWS Region', validators=[DataRequiredValidator()], choices=get_aws_regions())
    instance_type = SelectField('AWS Instance Type', validators=[DataRequiredValidator()], choices=get_aws_instance_types())
    vpc_id = SelectField('AWS VPC', choices=get_aws_vps_ids(), validators=[
        DataRequiredValidator(), 
        RegexpValidator(
            '^vpc-[a-z0-9]*$',
            message='The VPC id must begin by <i>vpc</i> followed by lowercase ASCII letters or digits'
        )
    ])

    # Modules
    modules = FieldList(FormField(ModuleForm), min_entries=1)

    # Features
    #feature = StringField('Name', validators=[DataRequiredValidator()])

    submit = SubmitField('Create Application')

class DeployAppForm(Form):
    module_name = SelectField('Module to deploy', validators=[DataRequiredValidator()])

    submit = SubmitField('Deploy Application Module')

class DeleteAppForm(Form):
    etag = HiddenField(validators=[DataRequiredValidator()])
    confirmation = RadioField('Are you sure?', validators=[DataRequiredValidator()], choices=[('yes', 'Yes'), ('no', 'No')])

    submit = SubmitField('Delete Application')

# Web UI App
def create_app():
    app = Flask(__name__)
    Bootstrap(app)

    @app.route('/web/')
    def web_index():
        return render_template('index.html')

    @app.route('/web/apps')
    def web_app_list():
        return render_template('app_list.html', apps=get_ghost_apps())

    @app.route('/web/apps/create', methods=['GET', 'POST'])
    def web_app_create():
        form = AppForm()

        # Perform validation in POST case
        if form.validate_on_submit():
            app = {}
            app['name'] = form.name.data
            app['env'] = form.env.data
            app['role'] = form.role.data
            app['region'] = form.region.data
            app['instance_type'] = form.instance_type.data
            app['vpc_id'] = form.vpc_id.data

            # Extract app data
            #app['autoscale'] = {}
            #app['build_infos'] = {}

            # Extract modules data
            app['modules'] = []
            for form_module in form.modules:
                module = {}
                module['name'] = form_module.module_name.data
                module['git_repo'] = form_module.module_git_repo.data
                module['path'] = form_module.module_path.data
                module['scope'] = form_module.module_scope.data
                if form_module.module_build_pack.data:
                    module['build_pack'] = b64encode(form_module.module_build_pack.data.stream.read())
                if form_module.module_pre_deploy.data:
                    module['pre_deploy'] = b64encode(form_module.module_pre_deploy.data.stream.read())
                if form_module.module_post_deploy.data:
                    module['post_deploy'] = b64encode(form_module.module_post_deploy.data.stream.read())
                app['modules'].append(module)

            try:
                message = requests.post(url=url_apps, data=json.dumps(app), headers=headers, auth=auth).content
                print(message)
                flash('Application created.')
            except:
                traceback.print_exc()
                message = 'Failed to create Application (%s)' % (sys.exc_info()[1])

            return render_template('action_completed.html', message=message)

        # Display default template in GET case
        return render_template('app_create.html', form=form)

    @app.route('/web/apps/<app_id>/deploy', methods=['GET', 'POST'])
    def web_app_deploy(app_id):
        form = DeployAppForm()

        # Get Application Modules
        try:
            modules = requests.get(url_apps + '/' + app_id, headers=headers, auth=auth).json()['modules']
        except:
            traceback.print_exc()
            modules = ['Failed to retrieve Application Modules']

        form.module_name.choices = [(module['name'], module['name']) for module in modules if module['scope'] == 'code']

        # Perform validation in POST case
        if form.validate_on_submit():
            job = {}
            job['user'] = 'web'
            job['command'] = 'deploy'
            job['app_id'] = app_id

            module = {}
            module['name'] = form.module_name.data
            modules = []
            modules.append(module)

            job['modules'] = modules

            try:
                message = requests.post(url=url_jobs, data=json.dumps(job), headers=headers, auth=auth).content
                print(message)
                flash('Job created.')
            except:
                traceback.print_exc()
                message = 'Failed to create Job (%s)' % (sys.exc_info()[1])

            return render_template('action_completed.html', message=message)

        # Display default template in GET case
        return render_template('app_deploy.html', app_id=app_id, form=form)

    @app.route('/web/apps/<app_id>/delete', methods=['GET', 'POST'])
    def web_app_delete(app_id):
        form = DeleteAppForm()

        # Perform validation in POST case
        if form.validate_on_submit and form.confirmation.data == 'yes':
            local_headers = headers.copy()
            local_headers['If-Match'] = form.etag.data

            try:
                message = requests.delete(url=url_apps + '/' + app_id, headers=local_headers, auth=auth).content
                print(message)
                flash('Application deleted.')
            except:
                traceback.print_exc()
                message = 'Failed to delete App (%s)' % (sys.exc_info()[1])

            return render_template('action_completed.html', message=message)

        # Get Application etag
        try:
            form.etag.data = requests.get(url_apps + '/' + app_id, headers=headers, auth=auth).json()['_etag']
        except:
            traceback.print_exc()

        # Display default template in GET case
        return render_template('app_delete.html', app_id=app_id, form=form)

    return app


def run_web_ui():
    app = create_app()
    app.config.update(
        DEBUG = True,
        SECRET_KEY = 'a random string',
        WTF_CSRF_SECRET_KEY = 'a random string'
    )
    app.run(host='0.0.0.0', port=5001)
