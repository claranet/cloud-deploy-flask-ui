from flask import flash, Markup
from flask_login import current_user
from werkzeug.exceptions import default_exceptions
from eve import RFC1123_DATE_FORMAT

from datetime import datetime
import traceback
import sys
import requests
import json
from settings import API_BASE_URL

from ghost_tools import b64decode_utf8

API_QUERY_SORT_UPDATED_DESCENDING = '?sort=-_updated'
API_QUERY_SORT_TIMESTAMP_DESCENDING = '?sort=-timestamp'

# FIXME: Static conf to externalize with Flask-Appconfig
headers = {'Content-type': 'application/json', 'Accept': 'application/json'}
url_apps = API_BASE_URL + '/apps'
url_jobs = API_BASE_URL + '/jobs'
url_commands = API_BASE_URL + '/commands'
url_deployments = API_BASE_URL + '/deployments'

# Helpers
def format_success_message(success_message, result):
    """
    >>> result = {"_updated": "Thu, 25 Jun 2015 16:35:27 GMT", "_links": {"self": {"href": "jobs/558c2dcf745f423d9babf52d", "title": "job"}}, "_created": "Thu, 25 Jun 2015 16:35:27 GMT", "_status": "OK", "_id": "558c2dcf745f423d9babf52d", "_etag": "6297ef1e01d45784fa7086191306c4986d4ba8a0"}
    >>> format_success_message("success_message", result)
    Markup(u"success_message: <a href='/web/jobs/558c2dcf745f423d9babf52d' title='job'>jobs/558c2dcf745f423d9babf52d</a>")
    """
    formatted_message = success_message
    links = result.get('_links', [])
    if 'self' in links:
        link = links['self']
        formatted_message += ": <a href='/web/{href}' title='{title}'>{href}</a>".format(href=link.get('href', ''), title=link.get('title', ''))
    return Markup(formatted_message)

def do_request(method, url, data, headers, success_message, failure_message):
    try:
        result = method(url=url, data=data, headers=headers, auth=current_user.auth)
        status_code = result.status_code
        message = result.content
        result_json = result.json() if status_code in [200, 201] else {}
        if status_code in [200, 201, 204]:
            flash(format_success_message(success_message, result_json), 'success')
        else:
            flash(failure_message, 'warning')
    except:
        traceback.print_exc()
        message = 'Failure: %s' % (sys.exc_info()[1])
        flash(failure_message, 'danger')
    print message
    return message, result_json

def handle_response_status_code(status_code):
    if status_code >= 300:
        raise default_exceptions[status_code]


def test_ghost_auth(user):
    return requests.head(API_BASE_URL, headers=headers, auth=user.auth)

def get_ghost_envs(query=None):
    try:
        envs = set([])
        url = url_apps + API_QUERY_SORT_UPDATED_DESCENDING
        url += '&max_result=999&projection={"env":1}'
        if query:
            url += '&where=' + query
        result = requests.get(url, headers=headers, auth=current_user.auth)
        handle_response_status_code(result.status_code)
        for item in result.json().get('_items', []):
            envs.add(item['env'])
    except:
        traceback.print_exc()
        message = 'Failure: %s' % (sys.exc_info()[1])
        flash(message, 'danger')
        envs.add('Failed to retrieve Envs')

    return envs

def get_ghost_apps_per_env(env=None, embed_deployments=False):
    try:
        url = url_apps + API_QUERY_SORT_UPDATED_DESCENDING
        url += '&max_result=999'
        if env:
            url += "&where=env=='" + env + "'"
        if embed_deployments:
            url += '&embedded={"modules.last_deployment":1}'
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

def get_ghost_apps(query=None, page=None, embed_deployments=False):
    try:
        url = url_apps + API_QUERY_SORT_UPDATED_DESCENDING
        if query:
            url += '&where=' + query
        if page:
            url += '&page=' + page
        if embed_deployments:
            url += '&embedded={"modules.last_deployment":1}'
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

def get_ghost_app(app_id, embed_deployments=False):
    try:
        url = url_apps + '/' + app_id
        if embed_deployments:
            url += '?embedded={"modules.last_deployment":1}'
        result = requests.get(url, headers=headers, auth=current_user.auth)
        app = result.json()
        handle_response_status_code(result.status_code)

        # Decode lifecycle hooks scripts
        lifecycle_hooks = app.get('lifecycle_hooks', None)
        if lifecycle_hooks is not None:
            if 'pre_buildimage' in lifecycle_hooks:
                lifecycle_hooks['pre_buildimage'] = b64decode_utf8(lifecycle_hooks['pre_buildimage'])
            if 'post_buildimage' in lifecycle_hooks:
                lifecycle_hooks['post_buildimage'] = b64decode_utf8(lifecycle_hooks['post_buildimage'])
            if 'pre_bootstrap' in lifecycle_hooks:
                lifecycle_hooks['pre_bootstrap'] = b64decode_utf8(lifecycle_hooks['pre_bootstrap'])
            if 'post_bootstrap' in lifecycle_hooks:
                lifecycle_hooks['post_bootstrap'] = b64decode_utf8(lifecycle_hooks['post_bootstrap'])

        # Decode module scripts
        for module in app.get('modules', []):
            if 'build_pack' in module:
                module['build_pack'] = b64decode_utf8(module['build_pack'])
            if 'pre_deploy' in module:
                module['pre_deploy'] = b64decode_utf8(module['pre_deploy'])
            if 'post_deploy' in module:
                module['post_deploy'] = b64decode_utf8(module['post_deploy'])
            if 'after_all_deploy' in module:
                module['after_all_deploy'] = b64decode_utf8(module['after_all_deploy'])

            if 'last_deployment' in module and isinstance(module['last_deployment'], dict):
                try:
                    last_deployment_timestamp = module['last_deployment'].get('timestamp', None)
                    module['last_deployment']['_created'] = datetime.utcfromtimestamp(last_deployment_timestamp).strftime(RFC1123_DATE_FORMAT) if last_deployment_timestamp else None
                except:
                    traceback.print_exc()

    except:
        traceback.print_exc()
        message = 'Failure: %s' % (sys.exc_info()[1])
        flash(message, 'danger')
        app = {}
    return app

def create_ghost_app(app):
    return do_request(requests.post, url=url_apps, data=json.dumps(app), headers=headers, success_message='Application created', failure_message='Application creation failed')

def update_ghost_app(app_id, local_headers, app):
    message, result = do_request(requests.patch, url=url_apps + '/' + app_id, data=json.dumps(app), headers=local_headers, success_message='Application updated', failure_message='Application update failed')
    return message

def delete_ghost_app(app_id, local_headers):
    message, result = do_request(requests.delete, url=url_apps + '/' + app_id, data=None, headers=local_headers, success_message='Application deleted', failure_message='Application deletion failed')
    return message

def get_ghost_jobs(query=None, page=None):
    try:
        url = url_jobs + API_QUERY_SORT_UPDATED_DESCENDING + '&embedded={"app_id": 1}'
        if query:
            url += "&where=" + query
        if page:
            url += "&page="  + page
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
        url = url_jobs + '/' + job_id + '?embedded={"app_id": 1}'
        result = requests.get(url, headers=headers, auth=current_user.auth)
        job = result.json()
        handle_response_status_code(result.status_code)
    except:
        traceback.print_exc()
        message = 'Failure: %s' % (sys.exc_info()[1])
        flash(message, 'danger')
        job = {}
    return job

def get_ghost_job_commands():
    try:
        result = requests.get(url_commands, headers=headers, auth=current_user.auth)
        commands = result.json()
        handle_response_status_code(result.status_code)
    except:
        traceback.print_exc()
        message = 'Failure: %s' % (sys.exc_info()[1])
        flash(message, 'danger')
        commands = [('Error', 'Failed to retrieve commands')]
    return commands

def create_ghost_job(app_id, form, headers):
    job = {}
    job['command'] = form.command.data
    job['app_id'] = app_id

    # Process modules
    modules = []
    if form.modules.data and form.command.data == 'deploy':
        for form_module in form.modules.data:
            module = {}
            if form_module['deploy']:
                module['name'] = form_module['name']
                module['rev'] = form_module['rev']
                modules.append(module)

    if modules:
        job['modules'] = modules

    # Process options
    options = []

    # Process BuildImage options
    if form.command.data == 'buildimage':
        if form.instance_type.data:
            job['instance_type'] = form.instance_type.data
        if isinstance(form.skip_salt_bootstrap.data, bool):
            # In case of buildimage, option[0] can be the skip_salt_bootstrap
            options.append(str(form.skip_salt_bootstrap.data))

    if form.command.data == 'redeploy':
        # In case of redeploy
        # option[0] must be the deploy ID
        options.append(form.deploy_id.data)

        if form.fabric_execution_strategy.data:
            # option[1] can be the fabric_execution_strategy
            options.append(form.fabric_execution_strategy.data)

        if form.safe_deployment.data:
            # option[2] can be the safe deployment type
            options.append(form.safe_deployment_strategy.data)

    if form.command.data == 'deploy':
        if form.fabric_execution_strategy.data:
            # In case of deploy, option[0] can be the fabric_execution_strategy
            options.append(form.fabric_execution_strategy.data)

        if form.safe_deployment.data:
            # option[1] can be the safe deployment type
            options.append(form.safe_deployment_strategy.data)

    if form.command.data == 'recreateinstances':
        if form.rolling_update.data:
            # option[0] can be the safe destroy type
            options.append(form.rolling_update_strategy.data)

    if form.command.data == 'createinstance':
        if form.subnet.data:
            options.append(form.subnet.data)
        if form.private_ip_address.data:
            options.append(form.private_ip_address.data)

    if form.command.data == 'preparebluegreen':
        if isinstance(form.prepare_bg_copy_ami.data, bool):
            # In case of preparebluegreen, option[0] can be the prepare_bg_copy_ami
            options.append(str(form.prepare_bg_copy_ami.data))

    if form.command.data == 'swapbluegreen':
        if form.swapbluegreen_strategy.data:
            options.append(form.swapbluegreen_strategy.data)

    if form.command.data == 'purgebluegreen':
        if isinstance(form.purge_delete_elb.data, bool):
            options.append(str(form.purge_delete_elb.data))

    if len(options) > 0:
        job['options'] = options

    message, result = do_request(requests.post, url=url_jobs, data=json.dumps(job), headers=headers, success_message='Job created', failure_message='Job creation failed')

    return message

def delete_ghost_job(job_id, local_headers):
    message, result = do_request(requests.delete, url=url_jobs + '/' + job_id, data=None, headers=local_headers, success_message='Job deleted', failure_message='Job deletion failed')
    return message

def cancel_ghost_job(job_id, local_headers):
    message, result = do_request(requests.delete, url=url_jobs + '/' + job_id + '/enqueueings', data=None, headers=local_headers, success_message='Job cancelled', failure_message='Job cancellation failed')
    return message

def get_ghost_deployments(query=None, page=None):
    try:
        url = url_deployments + API_QUERY_SORT_TIMESTAMP_DESCENDING + '&embedded={"app_id": 1, "job_id": 1}'
        if query:
            url += "&where=" + query
        if page:
            url += "&page="  + page
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
        url = url_deployments + '/' + deployment_id + '?embedded={"app_id": 1, "job_id": 1}'
        result = requests.get(url, headers=headers, auth=current_user.auth)
        handle_response_status_code(result.status_code)
        deployment = result.json()
    except:
        traceback.print_exc()
        message = 'Failure: %s' % (sys.exc_info()[1])
        flash(message, 'danger')
    return deployment
