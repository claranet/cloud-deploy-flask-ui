from __future__ import print_function

import json
import logging
import requests

from datetime import datetime
from flask import flash, Markup
from flask_login import current_user
from werkzeug.exceptions import default_exceptions

from ghost_tools import b64decode_utf8, b64encode_utf8
from libs.provisioners.provisioner import DEFAULT_PROVISIONER_TYPE
from models.apps import APPS_DEFAULT
from settings import API_BASE_URL, PAGINATION_LIMIT
from ui_helpers import get_pretty_yaml_from_json
from urllib import urlencode

RFC1123_DATE_FORMAT = '%a, %d %b %Y %H:%M:%S GMT'
API_QUERY_SORT_UPDATED_DESCENDING = '?sort=-_updated'
API_QUERY_SORT_TIMESTAMP_DESCENDING = '?sort=-timestamp'

# FIXME: Static conf to externalize with Flask-Appconfig
headers = {'Content-type': 'application/json', 'Accept': 'application/json'}
url_apps = API_BASE_URL + '/apps'
url_webhooks = API_BASE_URL + '/webhooks'
url_jobs = API_BASE_URL + '/jobs'
url_commands = API_BASE_URL + '/commands'
url_commands_fields = url_commands + '/fields'
url_deployments = API_BASE_URL + '/deployments'
url_lxd = API_BASE_URL + '/lxd'


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
        formatted_message += ": <a href='/web/{href}' title='{title}'>{href}</a>".format(href=link.get('href', ''),
                                                                                         title=link.get('title', ''))
    return Markup(formatted_message)


def do_request(method, url, data, headers, success_message, failure_message):
    result_json = ''
    status_code = 0
    try:
        result = method(url=url, data=data, headers=headers, auth=current_user.auth)
        status_code = result.status_code
        message = result.content
        result_json = result.json() if status_code in [200, 201] else {}
        if status_code in [200, 201, 204]:
            flash(format_success_message(success_message, result_json), 'success')
        else:
            flash(failure_message, 'warning')
        if message and message.strip():
            flash(message, 'info')
    except:
        message = 'Failure: Error while requesting Ghost API'
        logging.exception(message)
        flash(failure_message, 'danger')
        flash(message, 'danger')
    return message, result_json, status_code


def handle_response_status_code(status_code):
    if status_code >= 300:
        raise default_exceptions[status_code]


def test_ghost_auth(user):
    return requests.head(API_BASE_URL, headers=headers, auth=user.auth)


def get_ghost_lxd_status():
    try:
        url = url_lxd + '/status'
        result = requests.get(url, headers=headers, auth=current_user.auth)
        json = result.json()
        status = json.get('status')
        if json.get('error'):
            message = 'Failure: LXD Error {}'.format(json.get('error'))
            flash(message, 'danger')
        handle_response_status_code(result.status_code)
    except:
        message = 'Failure: Error while retrieving LXD status'
        logging.exception(message);
        flash(message, 'danger')
        status = False

    return status


def get_ghost_lxd_images():
    try:
        url = url_lxd + '/images'
        result = requests.get(url, headers=headers, auth=current_user.auth)
        images = result.json()
        if type(images) is not list and images.get('error'):
            message = 'Failure: LXD Error {}'.format(images.get('error'))
            flash(message, 'danger')
            images = images.get('images')
        handle_response_status_code(result.status_code)
    except:
        message = 'Failure: Error while retrieving LXD images'
        logging.exception(message)
        flash(message, 'danger')
        images = []

    return images


def get_ghost_envs(query=None, with_wildcard=True):
    try:
        envs_list = list()
        envs_set = set()
        url = url_apps + API_QUERY_SORT_UPDATED_DESCENDING
        url += '&' + urlencode({'max_results': PAGINATION_LIMIT, 'projection': '{"env":1}'})
        if query:
            url += '&where=' + query
        result = requests.get(url, headers=headers, auth=current_user.auth)
        handle_response_status_code(result.status_code)
        for item in result.json().get('_items', []):
            envs_set.add(item['env'])
        if with_wildcard:
            envs_list.insert(0, '*')
        envs_list.extend(list(envs_set))
    except:
        message = 'Failure: Error while retrieving application envs'
        logging.exception(message)
        flash(message, 'danger')
        envs_list = ['Failed to retrieve Envs']

    return envs_list


def get_ghost_roles(query=None, with_wildcard=True):
    try:
        roles_list = list()
        roles_set = set()
        url = url_apps + API_QUERY_SORT_UPDATED_DESCENDING
        url += '&' + urlencode({'max_results': PAGINATION_LIMIT, 'projection':'{"role":1}'})
        if query:
            url += '&where=' + query
        result = requests.get(url, headers=headers, auth=current_user.auth)
        handle_response_status_code(result.status_code)
        for item in result.json().get('_items', []):
            roles_set.add(item['role'])
        if with_wildcard:
            roles_list.insert(0, '*')
        roles_list.extend(list(roles_set))
    except Exception as e:
        logging.exception(e)
        message = 'Failure: {}'.format(str(e))
        flash(message, 'danger')
        roles_list[0] = 'Failed to retrieve Roles'

    return roles_list


def get_ghost_apps(role=None, page=None, embed_deployments=False, env=None, name=None):
    try:
        url = url_apps + API_QUERY_SORT_UPDATED_DESCENDING
        # Eve Query building
        query = []
        if role is not None:
            query.append('"role":"{role}"'.format(role=role))
        if env is not None:
            query.append('"env":"{env}"'.format(env=env))
        if name is not None:
            query.append('"name":{{"$regex":".*{name}.*"}}'.format(name=name))
        if len(query) > 0:
            url += '&where={' + ",".join(query) + '}'
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
                logging.exception('Error while converting application date')
    except:
        message = 'Failure: Error while retrieving applications'
        logging.exception(message)
        flash(message, 'danger')
        apps = []

    return apps


def get_ghost_app(app_id, embed_deployments=False, embed_features_params_as_yml=False):
    try:
        url = url_apps + '/' + app_id
        if embed_deployments:
            url += '?embedded={"modules.last_deployment":1}'
        result = requests.get(url, headers=headers, auth=current_user.auth)
        app = result.json()
        handle_response_status_code(result.status_code)
        app = normalize_app_object(app, embed_features_params_as_yml)
    except:
        message = 'Failure: Error while retrieving application'
        logging.exception(message)
        flash(message, 'danger')
        app = {}
    return app


def create_ghost_app(app):
    message, result, status_code = do_request(requests.post, url=url_apps, data=json.dumps(app), headers=headers,
                                              success_message='Application created',
                                              failure_message='Application creation failed')
    return message, result, status_code


def update_ghost_app(app_id, local_headers, app):
    message, result, status_code = do_request(requests.patch, url=url_apps + '/' + app_id, data=json.dumps(app),
                                              headers=local_headers,
                                              success_message='Application "{}" updated'.format(app_id),
                                              failure_message='Application "{}" update failed'.format(app_id))
    return message, status_code


def delete_ghost_app(app_id, local_headers):
    message, result, status_code = do_request(requests.delete, url=url_apps + '/' + app_id, data=None,
                                              headers=local_headers,
                                              success_message='Application "{}" was deleted'.format(app_id),
                                              failure_message='Application "{}" deletion failed'.format(app_id))
    return message, status_code


def get_ghost_jobs(query=None, page=None, application_name=None, application_role=None, application_env=None,
                   job_status=None, job_command=None, job_user=None):
    try:
        url = url_jobs + API_QUERY_SORT_UPDATED_DESCENDING + '&embedded={"app_id": 1}'
        if query:
            url += "&where=" + query
        else:
            query = {}
            if application_name or application_env or application_role:
                applications = ['{{"app_id":"{app_id}"}}'.format(app_id=application['_id'])
                                for application in get_ghost_apps(name=application_name,
                                                                  role=application_role,
                                                                  env=application_env)]
                if len(applications) > 0:
                    query['$or'] = '[{}]'.format(','.join(applications))
                else:
                    query['$or'] = '[{"app_id":"null"}]'

            if job_user:
                query['user'] = '{{"$regex":".*{user}.*"}}'.format(user=job_user)

            if job_command:
                query['command'] = '"{}"'.format(job_command)

            if job_status:
                query['status'] = '"{}"'.format(job_status)

            querystr = '{{{query}}}'.format(query=','.join('"{key}":{value}'.format(key=key, value=value)
                                                           for key, value in query.items()))
            url += "&where=" + querystr
        if page:
            url += "&page=" + page
        result = requests.get(url, headers=headers, auth=current_user.auth)
        handle_response_status_code(result.status_code)
        jobs = result.json().get('_items', [])
        for job in jobs:
            try:
                set_job_duration(job)
                job['_created'] = datetime.strptime(job['_created'], RFC1123_DATE_FORMAT)
                job['_updated'] = datetime.strptime(job['_updated'], RFC1123_DATE_FORMAT)
            except:
                logging.exception('Error while converting job date')
    except:
        message = 'Failure: Error while retrieving jobs'
        logging.exception(message)
        flash(message, 'danger')
        jobs = []

    return jobs


def get_ghost_job(job_id):
    try:
        url = url_jobs + '/' + job_id + '?embedded={"app_id": 1}'
        result = requests.get(url, headers=headers, auth=current_user.auth)
        job = result.json()
        set_job_duration(job)
        handle_response_status_code(result.status_code)
    except:
        message = 'Failure: Error while retrieving job'
        logging.exception(message)
        flash(message, 'danger')
        job = {}
    return job


def get_ghost_websocket_token(job_id):
    try:
        url = url_jobs + '/' + job_id + '/websocket_token'
        result = requests.get(url, headers=headers, auth=current_user.auth)
        token = result.json().get('token')
        handle_response_status_code(result.status_code)
    except:
        message = 'Failure: Error while retrieving websocket token'
        logging.exception(message)
        flash(message, 'danger')
        token = ''
    return token


def set_job_duration(job):
    if job.get('started_at') and job.get('status') not in ['init', 'started']:
        job_updated = datetime.strptime(job['_updated'], RFC1123_DATE_FORMAT)
        job_started = datetime.strptime(job['started_at'], RFC1123_DATE_FORMAT)
        job['duration'] = str(job_updated - job_started)


def get_ghost_job_commands(with_fields=False, app_id=''):
    try:
        result = requests.get('{}/{}'.format(url_commands_fields if with_fields else url_commands, app_id), headers=headers, auth=current_user.auth)
        commands = result.json()

        # Dict sort
        commands = sorted(commands)
        handle_response_status_code(result.status_code)
    except:
        message = 'Failure: Error while retrieving job commands'
        logging.exception(message)
        flash(message, 'danger')
        commands = [('Error', 'Failed to retrieve commands info')]
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
        if isinstance(form.skip_provisioner_bootstrap.data, bool):
            # In case of buildimage, option[0] can be the skip_provisioner_bootstrap
            options.append(str(form.skip_provisioner_bootstrap.data))

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

    if form.command.data == 'executescript':
        if form.to_execute_script.data:
            options.append(b64encode_utf8(form.to_execute_script.data.replace('\r\n', '\n')))
        else:
            options.append('')
        if form.script_module_context.data:
            options.append(form.script_module_context.data)
        else:
            options.append('')

        options.append(form.execution_strategy.data)
        if form.execution_strategy.data == 'single':
            options.append(form.single_host_instance.data)
        else:
            if form.safe_deployment_strategy.data:
                # can be the safe deployment type
                options.append(form.safe_deployment_strategy.data)

    if form.command.data == 'preparebluegreen':
        options.append(str(form.prepare_bg_copy_ami.data
                           if isinstance(form.prepare_bg_copy_ami.data, bool) else False))
        options.append(str(form.prepare_create_temp_elb.data
                           if isinstance(form.prepare_create_temp_elb.data, bool) else False))

    if form.command.data == 'swapbluegreen':
        if form.swapbluegreen_strategy.data:
            options.append(form.swapbluegreen_strategy.data)

    if len(options) > 0:
        job['options'] = options

    message, result, status_code = do_request(requests.post, url=url_jobs, data=json.dumps(job), headers=headers,
                                              success_message='Job created',
                                              failure_message='Job creation failed')
    return message


def delete_ghost_job(job_id, local_headers):
    message, result, status_code = do_request(requests.delete, url=url_jobs + '/' + job_id, data=None,
                                              headers=local_headers,
                                              success_message='Job "{}" deleted'.format(job_id),
                                              failure_message='Job "{}" deletion failed'.format(job_id))
    return message, status_code


def cancel_ghost_job(job_id, local_headers):
    message, result, status_code = do_request(requests.delete, url=url_jobs + '/' + job_id + '/enqueueings', data=None,
                                              headers=local_headers,
                                              success_message='Job "{}" cancelled'.format(job_id),
                                              failure_message='Job "{}" cancellation failed'.format(job_id))
    return message


def get_ghost_deployments(query=None, page=None, application_name=None, application_role=None, application_env=None, deployment_revision=None, deployment_module=None):
    try:
        url = url_deployments + API_QUERY_SORT_TIMESTAMP_DESCENDING + '&embedded={"app_id": 1, "job_id": 1}'
        if query:
            url += "&where=" + query
        else:
            query = {}
            if application_name or application_env or application_role:
                applications = ['{{"app_id":"{app_id}"}}'.format(app_id=application['_id'])
                                for application in get_ghost_apps(name=application_name,
                                                                  role=application_role,
                                                                  env=application_env)]
                if len(applications) > 0:
                    query['$or'] = '[{}]'.format(','.join(applications))
                else:
                    query['$or'] = '[{"app_id":"null"}]'

            if deployment_revision:
                query['revision'] = '"{}"'.format(deployment_revision)

            if deployment_module:
                query['module'] = '{{"$regex":".*{module}.*"}}'.format(module=deployment_module)

            querystr = '{{{query}}}'.format(query=','.join('"{key}":{value}'.format(key=key, value=value)
                                                           for key, value in query.items()))
            url += "&where=" + querystr
        if page:
            url += "&page=" + page
        result = requests.get(url, headers=headers, auth=current_user.auth)
        handle_response_status_code(result.status_code)
        deployments = result.json().get('_items', [])
        for deployment in deployments:
            try:
                deployment['_created'] = datetime.strptime(deployment['_created'], RFC1123_DATE_FORMAT)
            except:
                logging.exception('Error while converting deployment date')
    except:
        message = 'Failure: Error while retrieving deployments'
        logging.exception(message)
        flash(message, 'danger')
        deployments = []

    return deployments


def get_ghost_deployment(deployment_id):
    try:
        url = url_deployments + '/' + deployment_id + '?embedded={"app_id": 1, "job_id": 1}'
        result = requests.get(url, headers=headers, auth=current_user.auth)
        handle_response_status_code(result.status_code)
        deployment = result.json()
        deployment['_created'] = datetime.strptime(deployment['_created'], RFC1123_DATE_FORMAT)
        # app_id contains embedded full app object
        deployment['app_id'] = normalize_app_object(deployment.get('app_id', {}), False)
    except:
        message = 'Failure: Error while retrieving deployment'
        deployment = None
        logging.exception(message)
        flash(message, 'danger')
    return deployment


def normalize_app_object(app, embed_features_params_as_yml):
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

    # Decode blue/green hooks scripts
    hooks = app.get('blue_green', {}).get('hooks', None)
    if hooks:
        if 'pre_swap' in hooks:
            hooks['pre_swap'] = b64decode_utf8(hooks['pre_swap'])
        if 'post_swap' in hooks:
            hooks['post_swap'] = b64decode_utf8(hooks['post_swap'])

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

        # [GHOST-507] Normalize modules.*.source / git_repo
        git_repo = module.get('git_repo')
        module_source = module.get('source', {}) or {}
        module_source['url'] = module_source.get('url', git_repo) or git_repo
        module_source['protocol'] = (module_source.get('protocol', APPS_DEFAULT['modules.source.protocol'])
                                     or APPS_DEFAULT['modules.source.protocol'])
        module_source['mode'] = (module_source.get('mode', APPS_DEFAULT['modules.source.mode'])
                                 or APPS_DEFAULT['modules.source.mode'])
        git_repo = git_repo or module_source['url']

        module['git_repo'] = git_repo
        module['source'] = module_source

        if 'last_deployment' in module and isinstance(module['last_deployment'], dict):
            try:
                last_deployment_timestamp = module['last_deployment'].get('timestamp', None)
                module['last_deployment']['_created'] = datetime.utcfromtimestamp(
                    last_deployment_timestamp).strftime(RFC1123_DATE_FORMAT) if last_deployment_timestamp else None
            except:
                logging.exception('Error while converting application date')
    # Features checks
    for feature in app.get('features', []):
        if 'provisioner' not in feature:
            feature['provisioner'] = DEFAULT_PROVISIONER_TYPE
        if embed_features_params_as_yml:
            feature['parameters_pretty'] = get_pretty_yaml_from_json(feature.get('parameters') or {})
    # Container enhancements
    if 'source_container_image' in app.get('build_infos'):
        fingerprint = app['build_infos']['source_container_image']
        app['build_infos']['src_container_img'] = dict(get_ghost_lxd_images()).get(fingerprint)

    return app


def get_ghost_webhooks(query=None, page=None):
    try:
        url = url_webhooks + API_QUERY_SORT_UPDATED_DESCENDING + '&embedded={"app_id": 1}'
        if query:
            url += "&where=" + query
        if page:
            url += "&page=" + page
        result = requests.get(url, headers=headers, auth=current_user.auth)
        handle_response_status_code(result.status_code)
        webhooks = result.json().get('_items', [])
    except:
        traceback.print_exc()
        message = 'Failure: %s' % (sys.exc_info()[1])
        flash(message, 'danger')
        webhooks = ['Failed to retrieve Webhooks']

    return webhooks


def create_ghost_webhook(webhook):
    message, result, status_code = do_request(requests.post, url=url_webhooks, data=json.dumps(webhook), headers=headers,
                                              success_message='Webhook created',
                                              failure_message='Webhook creation failed')
    return message, result, status_code


def update_ghost_webhook(webhook_id, local_headers, webhook):
    message, result, status_code = do_request(requests.patch, url=url_webhooks + '/' + webhook_id, data=json.dumps(webhook),
                                              headers=local_headers,
                                              success_message='Webhook "{}" updated'.format(webhook_id),
                                              failure_message='Webhook "{}" update failed'.format(webhook_id))
    return message, status_code


def delete_ghost_webhook(webhook_id, local_headers):
    message, result, status_code = do_request(requests.delete, url=url_webhooks + '/' + webhook_id, data=None,
                                              headers=local_headers,
                                              success_message='Webhook "{}" deleted'.format(webhook_id),
                                              failure_message='Webhook "{}" deletion failed'.format(webhook_id))
    return message, status_code


def get_ghost_webhook(webhook_id):
    try:
        url = url_webhooks + '/' + webhook_id + '?embedded={"app_id": 1}'
        result = requests.get(url, headers=headers, auth=current_user.auth)
        webhook = result.json()
        handle_response_status_code(result.status_code)
    except:
        traceback.print_exc()
        message = 'Failure: %s' % (sys.exc_info()[1])
        flash(message, 'danger')
        webhook = {}
    return webhook
