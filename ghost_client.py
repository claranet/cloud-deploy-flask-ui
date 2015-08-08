from flask import flash
from flask.ext.login import current_user
from werkzeug.exceptions import default_exceptions
from eve import RFC1123_DATE_FORMAT

from base64 import b64decode
from datetime import datetime
import traceback
import sys
import requests
import json

API_QUERY_SORT_UPDATED_DESCENDING = '?sort=-_updated'
API_QUERY_SORT_TIMESTAMP_DESCENDING = '?sort=-timestamp'

# FIXME: Static conf to externalize with Flask-Appconfig
headers = {'Content-type': 'application/json', 'Accept': 'text/plain'}
url_apps = 'http://localhost:5000/apps'
url_jobs = 'http://localhost:5000/jobs'
url_deployments = 'http://localhost:5000/deployments'

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
        if status_code in [200, 201]:
            flash(format_success_message(success_message, result.json()), 'success')
        elif status_code in [204]:
            flash(format_success_message(success_message, {}), 'success')
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


def test_ghost_auth(user):
    return requests.get(url_apps, headers=headers, auth=user.auth)


def get_ghost_apps(query=None):
    try:
        url = url_apps + API_QUERY_SORT_UPDATED_DESCENDING
        if query:
            url += "&where=" + query
        result = requests.get(url, headers=headers, auth=current_user.auth)
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

def get_ghost_app(app_id):
    try:
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
    return app

def create_ghost_app(app):
    return do_request(requests.post, url=url_apps, data=json.dumps(app), headers=headers, success_message='Application created', failure_message='Application creation failed')

def update_ghost_app(app_id, local_headers, app):
    return do_request(requests.patch, url=url_apps + '/' + app_id, data=json.dumps(app), headers=local_headers, success_message='Application updated', failure_message='Application update failed')

def delete_ghost_app(app_id, local_headers):
    return do_request(requests.delete, url=url_apps + '/' + app_id, data=None, headers=local_headers, success_message='Application deleted', failure_message='Application deletion failed')


def get_ghost_jobs(query=None):
    try:
        url = url_jobs + API_QUERY_SORT_UPDATED_DESCENDING + '&embedded={"app_id": 1}'
        if query:
            url += "&where=" + query
        result = requests.get(url, headers=headers, auth=current_user.auth)
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

def get_ghost_job(job_id):
    try:
        result = requests.get(url_jobs + '/' + job_id, headers=headers, auth=current_user.auth)
        job = result.json()
        handle_response_status_code(result.status_code)
    except:
        traceback.print_exc()
        message = 'Failure: %s' % (sys.exc_info()[1])
        flash(message, 'danger')
    return job

def create_ghost_job(app_id, form, headers):
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

    return message

def delete_ghost_job(job_id, local_headers):
    return do_request(requests.delete, url=url_jobs + '/' + job_id, data=None, headers=local_headers, success_message='Job deleted', failure_message='Job deletion failed')


def get_ghost_deployments(query=None):
    try:
        url = url_deployments + API_QUERY_SORT_TIMESTAMP_DESCENDING + '&embedded={"app_id": 1, "job_id": 1}'
        if query:
            url += "&where=" + query
        result = requests.get(url, headers=headers, auth=current_user.auth)
        handle_response_status_code(result.status_code)
        deployments = result.json().get('_items', [])
        for deployment in deployments:
            try:
                deployment['_created'] = datetime.strptime(deployment['_created'], RFC1123_DATE_FORMAT)
            except:
                traceback.print_exc()
    except:
        traceback.print_exc()
        message = 'Failure: %s' % (sys.exc_info()[1])
        flash(message, 'danger')
        deployments = ['Failed to retrieve Deployments']

    return deployments

def get_ghost_deployment(deployment_id):
    try:
        result = requests.get(url_deployments + '/' + deployment_id, headers=headers, auth=current_user.auth)
        handle_response_status_code(result.status_code)
        deployment = result.json()
    except:
        traceback.print_exc()
        message = 'Failure: %s' % (sys.exc_info()[1])
        flash(message, 'danger')
    return deployment