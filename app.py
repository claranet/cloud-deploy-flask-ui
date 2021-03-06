# -*- coding: utf-8 -*-

from flask import Flask, flash, render_template, request, Response, jsonify, redirect, url_for, make_response
from flask_bootstrap import Bootstrap
from flask_login import LoginManager, UserMixin, login_required
from werkzeug.contrib.fixers import ProxyFix

import hashlib
import json
import logging
import os
import ui_helpers
import yaml

from base64 import b64decode
from settings import DEFAULT_PROVIDER

from models.jobs import CANCELLABLE_JOB_STATUSES, DELETABLE_JOB_STATUSES, JOB_STATUSES, jobs_schema as ghost_jobs_schema
from models.apps import apps_schema as ghost_app_schema
from models.webhooks import webhook_schema as ghost_webhook_schema
from models.instance_role import role as ghost_role_default_values

from ghost_api import FORBIDDEN_PATH
from ghost_client import get_ghost_envs, get_ghost_roles
from ghost_tools import config, CURRENT_REVISION, boolify
from ghost_tools import b64decode_utf8
from ghost_client import get_ghost_apps, get_ghost_app, create_ghost_app, update_ghost_app, delete_ghost_app
from ghost_client import get_ghost_jobs, get_ghost_job, get_ghost_websocket_token, create_ghost_job, cancel_ghost_job, delete_ghost_job
from ghost_client import get_ghost_webhooks, get_ghost_webhook, create_ghost_webhook, update_ghost_webhook, delete_ghost_webhook
from ghost_client import get_ghost_webhooks_invocations
from ghost_client import get_ghost_deployments, get_ghost_deployment
from ghost_client import get_ghost_lxd_images, get_ghost_lxd_status, headers, test_ghost_auth
from libs.blue_green import get_blue_green_copy_ami_config
from libs.blue_green import ghost_has_blue_green_enabled
from libs.blue_green import get_blue_green_from_app
from libs.blue_green import get_blue_green_create_temporary_elb_config
from libs.git_helper import git_ls_remote_branches_tags
from health import get_host_cpu_label, get_host_health, HostHealth

from forms.command import CommandAppForm
from forms.app import CreateAppForm, DeleteAppForm, EditAppForm
from forms.job import CancelJobForm, DeleteJobForm
from forms.webhook import CreateWebhookForm, DeleteWebhookForm, EditWebhookForm
from forms.form_helper import get_ghost_app_roles, get_ghost_app_envs, get_wtforms_selectfield_values
from forms.form_helper import get_app_command_recommendations
from forms.form_helper import get_ansible_role_inventory, get_salt_formula_inventory
from forms.form_aws_helper import get_aws_ec2_regions, get_aws_ec2_instance_types, get_aws_vpc_ids, get_aws_sg_ids
from forms.form_aws_helper import get_aws_subnet_ids, get_aws_ami_ids, get_aws_ec2_key_pairs
from forms.form_aws_helper import get_aws_iam_instance_profiles, get_aws_as_groups
from forms.form_aws_helper import get_ghost_app_ec2_instances, get_ghost_app_as_group, get_as_group_instances
from forms.form_aws_helper import get_elbs_instances_from_as_group, get_safe_deployment_possibilities
from forms.form_aws_helper import get_aws_subnets_ids_from_app
from forms.form_aws_helper import get_aws_connection_data, check_aws_assumed_credentials
from forms.form_aws_helper import s3_list_object_revisions
from forms.form_helper import get_ghost_modules_names

# Web UI App
app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app)

app.config.update(
    SECRET_KEY='a random string',
    WTF_CSRF_SECRET_KEY='a random string'
)
app.jinja_env.add_extension('jinja2.ext.do')

CPU_HEALTH = None

Bootstrap(app)


@app.before_first_request
def create_health(*args, **kwargs):
    global CPU_HEALTH
    # thread handler
    CPU_HEALTH = HostHealth(5, 2)
    CPU_HEALTH.start()


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
            response = test_ghost_auth(user)

            if response.status_code == 200:
                return user
        except:
            message = 'Failure: Error while loading user'
            logging.exception(message)
            flash(message, 'danger')

    return None


@app.before_request
@login_required
def before_request():
    pass


LEGACY_COMMANDS = ['destroyinstance', 'rollback']
DEFAULT_BASH_SHEBANG = """
#!/bin/bash

set -x
set -e
"""


@app.context_processor
def template_context():
    global CPU_HEALTH
    health_stats = CPU_HEALTH.get_stats()
    return dict(
        role_list=ghost_role_default_values,
        statuses=JOB_STATUSES,
        ghost_blue_green=ghost_has_blue_green_enabled(),
        lxd=get_ghost_lxd_status,
        ghost_health_status=get_host_cpu_label(health_stats[0]),
        command_list=ghost_jobs_schema['command']['allowed'] + LEGACY_COMMANDS,
        app_modules_state=ui_helpers.app_modules_state,
        module_state=ui_helpers.module_state,
        check_status_code=ui_helpers.check_status_code,
        get_pretty_yaml_from_json=ui_helpers.get_pretty_yaml_from_json_str,
        ui_config=ui_helpers.ui_config.get('web_ui', {}) or {},
        check_instance_tag=ui_helpers.check_instance_tag,
        check_instance_tags=ui_helpers.check_instance_tags,
    )


def load_ghost_feature_presets():
    presets = {}
    try:
        presets_path = config.get('ghost_root_path') + '/ghost-feature-presets/'
        for file in os.listdir(presets_path):
            if file.endswith('.yml'):
                with open(presets_path + file, 'r') as pre_file:
                    prst = yaml.safe_load(pre_file)
                    presets[file] = prst
    except:
        logging.exception('Error while loading ghost feature presets')
    return presets


FEATURE_PRESETS = load_ghost_feature_presets()


@app.context_processor
def current_revision():
    return CURRENT_REVISION


def get_md5_hash(value):
    """
    >>> get_md5_hash('hello')
    '5d41402abc4b2a76b9719d911017c592'

    >>> get_md5_hash(u'hello')
    '5d41402abc4b2a76b9719d911017c592'

    >>> get_md5_hash(u'Hé ho du bateau!')
    'ef67594ec96664e539a1ee2a8903d734'

    :param value: string to hash
    :return: md5 hash
    """
    return hashlib.md5(value.encode('utf-8')).hexdigest() if value else ''


@app.context_processor
def hash_string_md5():
    return dict(get_md5_hash=get_md5_hash)


@app.route('/web/<provider>/identity/check/<account_id>/<role_name>/<region_name>')
def web_cloud_check_assume_role_region(provider, account_id, role_name, region_name):
    try:
        check = check_aws_assumed_credentials(provider, account_id, role_name, region_name)
    except:
        message = 'Failure: Error while checking assume role region'
        logging.exception(message)
        flash(message, 'danger')
        check = False
    return jsonify({'result': check})


@app.route('/web/<provider>/identity/check/<account_id>/<role_name>/')
def web_cloud_check_assume_role(provider, account_id, role_name):
    try:
        check = check_aws_assumed_credentials(provider, account_id, role_name)
    except:
        message = 'Failure: Error while checking assume role'
        logging.exception(message)
        flash(message, 'danger')
        check = False
    return jsonify({'result': check})


@app.route('/web/<provider>/regions')
def web_cloud_regions(provider):
    query_string = dict((key, request.args.getlist(key) if len(request.args.getlist(key)) > 1
        else request.args.getlist(key)[0]) for key in request.args.keys())
    return jsonify(dict(get_aws_ec2_regions(provider, **query_string)))


@app.route('/web/<provider>/regions/<region_id>/ec2/instancetypes')
def web_ec2_instance_types_list(provider, region_id):
    return jsonify(dict(get_aws_ec2_instance_types(region_id)))


@app.route('/web/<provider>/regions/<region_id>/ec2/keypairs')
def web_ec2_key_pairs_list(provider, region_id):
    query_string = dict((key, request.args.getlist(key) if len(request.args.getlist(key)) > 1
        else request.args.getlist(key)[0]) for key in request.args.keys())
    return jsonify(dict(get_aws_ec2_key_pairs(provider, region_id, **query_string)))


@app.route('/web/<provider>/regions/<region_id>/ec2/autoscale/ids')
def web_ec2_as_list(provider, region_id):
    query_string = dict((key, request.args.getlist(key) if len(request.args.getlist(key)) > 1
        else request.args.getlist(key)[0]) for key in request.args.keys())
    return jsonify(dict(get_aws_as_groups(provider, region_id, **query_string)))


@app.route('/web/<provider>/regions/<region_id>/ec2/<app_id>/infos')
def web_ec2_app_list(provider, region_id, app_id):
    # Get App data
    app = get_ghost_app(app_id)
    app_blue_green, app_color = get_blue_green_from_app(app)
    aws_connection_data = get_aws_connection_data(app.get('assumed_account_id', ''), app.get('assumed_role_name', ''),
                                                  app.get('assumed_region_name', ''))
    ec2s = get_ghost_app_ec2_instances(provider, app['name'], app['env'], app['role'], app['region'], None,
                                       app_color, **aws_connection_data)
    return jsonify({ec2['private_ip_address']: '{ip} - {id} - {size}'.format(ip=ec2['private_ip_address'], id=ec2['id'],
                                                                             size=ec2['instance_type']) for ec2 in
                    ec2s})


@app.route('/web/<provider>/regions/<region_id>/iam/profiles')
def web_iam_profiles_list(provider, region_id):
    query_string = dict((key, request.args.getlist(key) if len(request.args.getlist(key)) > 1
        else request.args.getlist(key)[0]) for key in request.args.keys())
    return jsonify(dict(get_aws_iam_instance_profiles(provider, region_id, **query_string)))


@app.route('/web/<provider>/regions/<region_id>/vpc/ids')
def web_vpcs_list(provider, region_id):
    query_string = dict((key, request.args.getlist(key) if len(request.args.getlist(key)) > 1
        else request.args.getlist(key)[0]) for key in request.args.keys())
    return jsonify(dict(get_aws_vpc_ids(provider, region_id, **query_string)))


@app.route('/web/<provider>/regions/<region_id>/vpc/<vpc_id>/sg/ids')
def web_sgs_list(provider, region_id, vpc_id):
    query_string = dict((key, request.args.getlist(key) if len(request.args.getlist(key)) > 1
        else request.args.getlist(key)[0]) for key in request.args.keys())
    return jsonify(dict(get_aws_sg_ids(provider, region_id, vpc_id, **query_string)))


@app.route('/web/<provider>/regions/<region_id>/vpc/<vpc_id>/subnet/ids')
def web_subnets_list(provider, region_id, vpc_id):
    query_string = dict((key, request.args.getlist(key) if len(request.args.getlist(key)) > 1
        else request.args.getlist(key)[0]) for key in request.args.keys())
    return jsonify(dict(get_aws_subnet_ids(provider, region_id, vpc_id, **query_string)))


@app.route('/web/<provider>/regions/<region_id>/ami/ids')
def web_amis_list(provider, region_id):
    query_string = dict((key, request.args.getlist(key) if len(request.args.getlist(key)) > 1
        else request.args.getlist(key)[0]) for key in request.args.keys())
    return jsonify(dict(get_aws_ami_ids(provider, region_id, **query_string)))


@app.route('/web/container/image/ids')
def web_container_image_list():
    return jsonify(dict(get_ghost_lxd_images()))


@app.route('/web/<provider>/appinfos/<app_id>/subnet/ids')
def web_app_subnets_list(provider, app_id):
    # Get App data
    app = get_ghost_app(app_id)
    aws_connection_data = get_aws_connection_data(app.get('assumed_account_id', ''), app.get('assumed_role_name', ''),
                                                  app.get('assumed_region_name', ''))
    return jsonify(dict(
        get_aws_subnets_ids_from_app(DEFAULT_PROVIDER, app['region'], app['environment_infos']['subnet_ids'],
                                     **aws_connection_data)))


@app.route('/web/<provider>/appinfos/<app_id>/modules/names')
def web_app_modules_list(provider, app_id):
    # Get App data
    app = get_ghost_app(app_id)

    return jsonify([module['name'] for module in app['modules']])


@app.route('/web/<provider>/appinfos/<app_id>', methods=['GET'])
def web_app_infos(provider, app_id):
    # Get App data
    app = get_ghost_app(app_id)
    app_blue_green, app_color = get_blue_green_from_app(app)
    aws_connection_data = get_aws_connection_data(app.get('assumed_account_id', ''), app.get('assumed_role_name', ''),
                                                  app.get('assumed_region_name', ''))
    if app['autoscale']['name']:
        as_group = get_ghost_app_as_group(app.get('provider', DEFAULT_PROVIDER), app['autoscale']['name'],
                                          app['region'], **aws_connection_data)
        if as_group:
            as_instances = get_as_group_instances(app.get('provider', DEFAULT_PROVIDER), as_group, app['region'],
                                                  **aws_connection_data)
            elbs_instances = get_elbs_instances_from_as_group(app.get('provider', DEFAULT_PROVIDER),
                                                              as_group['AutoScalingGroupName'], app['region'],
                                                              **aws_connection_data)
            ghost_instances = get_ghost_app_ec2_instances(app.get('provider', DEFAULT_PROVIDER), app['name'],
                                                          app['env'], app['role'], app['region'], as_instances,
                                                          app_color, **aws_connection_data)
            return render_template('app_infos_content.html', app=app, ghost_instances=ghost_instances,
                                   as_group=as_group, as_instances=as_instances, elbs_instances=elbs_instances)
        else:
            ghost_instances = get_ghost_app_ec2_instances(app.get('provider', DEFAULT_PROVIDER), app['name'],
                                                          app['env'], app['role'], app['region'], [], app_color,
                                                          **aws_connection_data)
            return render_template('app_infos_content.html', app=app, ghost_instances=ghost_instances)
    else:
        ghost_instances = get_ghost_app_ec2_instances(app.get('provider', DEFAULT_PROVIDER), app['name'], app['env'],
                                                      app['role'], app['region'], [], app_color,
                                                      **aws_connection_data)
        return render_template('app_infos_content.html', app=app, ghost_instances=ghost_instances)


@app.route('/web/ghost/health-status', methods=['GET'])
def web_ghost_health_status():
    global CPU_HEALTH
    with app.app_context():
        query = request.args.get('json', None)
        health = CPU_HEALTH.get_stats()
        status = get_host_health(health[0], health[1])
        if request.is_xhr and query:
            response = jsonify(status)
        else:
            response = render_template('ghost_health_status_content.html', status=status)
        response = Response(response)
        response.headers['Cache-Control'] = 'private, max-age=0, no-cache'
        return response


@app.route('/web/feature/presets')
def web_feature_presets_list():
    preset_list = []
    for file in FEATURE_PRESETS:
        filename, fileext = os.path.splitext(file)
        preset_list.append((file, filename.replace('-', ' ')))
    return jsonify(dict(preset_list))


@app.route('/web/feature/presets/import/<config>')
def web_feature_presets_import(config):
    return jsonify(FEATURE_PRESETS[config])


@app.route('/web/feature/ansible/inventory')
def web_feature_ansible_role_inventory():
    return jsonify(dict(get_wtforms_selectfield_values(get_ansible_role_inventory().keys())))


@app.route('/web/feature/salt/inventory')
def web_feature_salt_inventory():
    return jsonify(dict(get_wtforms_selectfield_values(get_salt_formula_inventory())))


@app.route('/web/feature/ansible/role-schema/<role>')
def web_feature_ansible_role_schema(role):
    data = get_ansible_role_inventory().get(role)
    response = app.response_class(
        response=json.dumps(data, sort_keys=False),
        status=200,
        mimetype='application/json'
    )
    return response


@app.route('/web/t-apps')
def web_t_apps_list():
    # redirect to apps as the page was unified
    return redirect(url_for('web_app_list'), code=301)


@app.route('/web/apps')
def web_app_list():
    page = request.args.get('page', '1')
    application_name = request.args.get('application') or None
    application_env = request.args.get('env') or None
    application_role = request.args.get('role') or None

    selected_env = application_env
    if selected_env == None:
        selected_env = '*'

    apps = get_ghost_apps(role=application_role, page=page, env=application_env, name=application_name, embed_deployments=True)
    envs = get_ghost_envs()

    query_values = {
        'application_name': application_name,
        'application_env': application_env,
        'application_role': application_role
    }

    if request.is_xhr:
        return render_template('app_list_content.html', env_list=envs, apps=apps,
                               page=int(page))
    return render_template('app_list.html', env_list=envs, selected_env=selected_env, apps=apps,
                           page=int(page), query_values=query_values)


@app.route('/web/apps/create', methods=['GET', 'POST'])
def web_app_create():
    form = CreateAppForm()

    clone_from_app = None
    clone_from_app_id = request.args.get('clone_from', None)
    if clone_from_app_id:
        clone_from_app = get_ghost_app(clone_from_app_id)

    try:
        cloud_provider = form.provider.data
    except:
        cloud_provider = DEFAULT_PROVIDER
    # Dynamic selections update
    if form.is_submitted() and cloud_provider:
        if form.use_custom_identity.data:
            aws_connection_data = get_aws_connection_data(
                form.assumed_account_id.data,
                form.assumed_role_name.data,
                form.assumed_region_name.data
            )
        else:
            form.assumed_account_id.data = ""
            form.assumed_role_name.data = ""
            form.assumed_region_name.data = ""
            aws_connection_data = {}
        # form.region.choices = get_aws_ec2_regions(form.provider.data, **aws_connection_data)
        if not form.env.data in form.env.choices:
            form.env.choices = get_ghost_app_envs() + [(form.env.data, form.env.data)]
        if not form.role.data in form.role.choices:
            form.role.choices = get_ghost_app_roles() + [(form.role.data, form.role.data)]
        form.instance_type.choices = get_aws_ec2_instance_types(form.region.data)
        form.vpc_id.choices = get_aws_vpc_ids(cloud_provider, form.region.data, **aws_connection_data)
        form.autoscale.as_name.choices = get_aws_as_groups(cloud_provider, form.region.data, **aws_connection_data)
        form.build_infos.source_ami.choices = get_aws_ami_ids(cloud_provider, form.region.data, **aws_connection_data)
        form.build_infos.container.choices = get_ghost_lxd_images()
        form.build_infos.subnet_id.choices = get_aws_subnet_ids(cloud_provider, form.region.data, form.vpc_id.data,
                                                                **aws_connection_data)
        form.environment_infos.instance_profile.choices = get_aws_iam_instance_profiles(cloud_provider,
                                                                                        form.region.data,
                                                                                        **aws_connection_data)
        form.environment_infos.key_name.choices = get_aws_ec2_key_pairs(cloud_provider, form.region.data,
                                                                        **aws_connection_data)
        for subnet in form.environment_infos.subnet_ids:
            subnet.choices = get_aws_subnet_ids(cloud_provider, form.region.data, form.vpc_id.data,
                                                **aws_connection_data)
        for sg in form.environment_infos.security_groups:
            sg.choices = get_aws_sg_ids(cloud_provider, form.region.data, form.vpc_id.data, **aws_connection_data)

    # Perform validation
    if form.validate_on_submit():
        app = {}
        form.map_to_app(app)

        message, result, status_code = create_ghost_app(app)
        app_id = result['_id'] if '_id' in result else None
        cmd_recommendations = get_app_command_recommendations(app_id) if ui_helpers.check_status_code(
            status_code) else None
        return render_template('action_completed.html', message=message, action_object_type='apps',
                               action_object_id=app_id,
                               status_code=status_code,
                               cmd_recommendations=cmd_recommendations)

    if clone_from_app:
        form.map_from_app(clone_from_app)
        if not form.is_submitted():
            if clone_from_app.get('assumed_account_id', None) and clone_from_app.get('assumed_role_name', None):
                form.use_custom_identity.data = True
            aws_connection_data = get_aws_connection_data(clone_from_app.get('assumed_account_id', ''),
                                                          clone_from_app.get('assumed_role_name', ''),
                                                          clone_from_app.get('assumed_region_name', ''))
            if not form.env.data in form.env.choices:
                form.env.choices = get_ghost_app_envs() + [(form.env.data, form.env.data)]
            if not form.role.data in form.role.choices:
                form.role.choices = get_ghost_app_roles() + [(form.role.data, form.role.data)]
            form.region.choices = get_aws_ec2_regions(clone_from_app.get('provider', DEFAULT_PROVIDER),
                                                      **aws_connection_data)
            form.instance_type.choices = get_aws_ec2_instance_types(clone_from_app['region'])
            form.vpc_id.choices = get_aws_vpc_ids(clone_from_app.get('provider', DEFAULT_PROVIDER),
                                                  clone_from_app['region'], **aws_connection_data)
            form.autoscale.as_name.choices = get_aws_as_groups(clone_from_app.get('provider', DEFAULT_PROVIDER),
                                                               clone_from_app['region'], **aws_connection_data)
            form.build_infos.source_ami.choices = get_aws_ami_ids(clone_from_app.get('provider', DEFAULT_PROVIDER),
                                                                  clone_from_app['region'], **aws_connection_data)
            form.build_infos.container.choices = get_ghost_lxd_images()
            form.build_infos.subnet_id.choices = get_aws_subnet_ids(clone_from_app.get('provider', DEFAULT_PROVIDER),
                                                                    clone_from_app['region'], clone_from_app['vpc_id'],
                                                                    **aws_connection_data)
            form.environment_infos.instance_profile.choices = get_aws_iam_instance_profiles(
                clone_from_app.get('provider', DEFAULT_PROVIDER), clone_from_app['region'], **aws_connection_data)
            form.environment_infos.key_name.choices = get_aws_ec2_key_pairs(
                clone_from_app.get('provider', DEFAULT_PROVIDER), clone_from_app['region'], **aws_connection_data)
            for subnet in form.environment_infos.subnet_ids:
                subnet.choices = get_aws_subnet_ids(clone_from_app.get('provider', DEFAULT_PROVIDER),
                                                    clone_from_app['region'], clone_from_app['vpc_id'],
                                                    **aws_connection_data)
            for sg in form.environment_infos.security_groups:
                sg.choices = get_aws_sg_ids(clone_from_app.get('provider', DEFAULT_PROVIDER), clone_from_app['region'],
                                            clone_from_app['vpc_id'], **aws_connection_data)

    form.build_infos.container.choices = get_ghost_lxd_images()

    # Display default template in GET case
    return render_template('app_edit.html', form=form, edit=False,
                           schema=ghost_app_schema, forbidden_paths=FORBIDDEN_PATH)


@app.route('/web/apps/<app_id>', methods=['GET'])
def web_app_view(app_id):
    # Get App data
    app = get_ghost_app(app_id, embed_deployments=True, embed_features_params_as_yml=True)
    cmd_recommendations = get_app_command_recommendations(app_id, app)

    return render_template('app_view.html', app=app, cmd_recommendations=cmd_recommendations)


@app.route('/web/apps/<app_id>/edit', methods=['GET', 'POST'])
def web_app_edit(app_id):
    form = EditAppForm()

    # Dynamic selections update
    try:
        cloud_provider = form.provider.data
    except:
        cloud_provider = DEFAULT_PROVIDER
    if form.is_submitted() and cloud_provider:
        if form.use_custom_identity.data:
            aws_connection_data = get_aws_connection_data(form.assumed_account_id.data, form.assumed_role_name.data,
                                                          form.assumed_region_name.data)
        else:
            form.assumed_account_id.data = ""
            form.assumed_role_name.data = ""
            form.assumed_region_name.data = ""
            aws_connection_data = {}
        form.region.choices = get_aws_ec2_regions(cloud_provider, **aws_connection_data)
        if not form.env.data in form.env.choices:
            form.env.choices = get_ghost_app_envs() + [(form.env.data, form.env.data)]
        if not form.role.data in form.role.choices:
            form.role.choices = get_ghost_app_roles() + [(form.role.data, form.role.data)]
        form.instance_type.choices = get_aws_ec2_instance_types(form.region.data)
        form.vpc_id.choices = get_aws_vpc_ids(cloud_provider, form.region.data, **aws_connection_data)
        form.autoscale.as_name.choices = get_aws_as_groups(cloud_provider, form.region.data, **aws_connection_data)
        form.build_infos.source_ami.choices = get_aws_ami_ids(cloud_provider, form.region.data, **aws_connection_data)
        form.build_infos.container.choices = get_ghost_lxd_images()
        form.build_infos.subnet_id.choices = get_aws_subnet_ids(cloud_provider, form.region.data, form.vpc_id.data,
                                                                **aws_connection_data)
        form.environment_infos.instance_profile.choices = get_aws_iam_instance_profiles(cloud_provider,
                                                                                        form.region.data,
                                                                                        **aws_connection_data)
        form.environment_infos.key_name.choices = get_aws_ec2_key_pairs(cloud_provider, form.region.data,
                                                                        **aws_connection_data)
        for subnet in form.environment_infos.subnet_ids:
            subnet.choices = get_aws_subnet_ids(cloud_provider, form.region.data, form.vpc_id.data,
                                                **aws_connection_data)
        for sg in form.environment_infos.security_groups:
            sg.choices = get_aws_sg_ids(cloud_provider, form.region.data, form.vpc_id.data, **aws_connection_data)

    form.build_infos.container.choices = get_ghost_lxd_images()

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

        message, status_code = update_ghost_app(app_id, local_headers, app)
        cmd_recommendations = get_app_command_recommendations(app_id) if ui_helpers.check_status_code(
            status_code) else None

        # if form.update_manifest.data:
        # TODO Perform Manifest update

        return render_template('action_completed.html', message=message, action_object_type='apps',
                               action_object_id=app_id,
                               status_code=status_code,
                               cmd_recommendations=cmd_recommendations)

    # Get App data on first access
    if not form.etag.data:
        app = get_ghost_app(app_id)
        form.map_from_app(app)

    # Remove alternative options from select fields that cannot be changed
    form.env.choices = [(form.env.data, form.env.data)]
    form.role.choices = [(form.role.data, form.role.data)]

    aws_connection_data = get_aws_connection_data(form.assumed_account_id.data, form.assumed_role_name.data,
                                                  form.assumed_region_name.data)
    form.region.choices = get_aws_ec2_regions(cloud_provider, **aws_connection_data)
    form.instance_type.choices = get_aws_ec2_instance_types(form.region.data)
    form.vpc_id.choices = get_aws_vpc_ids(cloud_provider, form.region.data, **aws_connection_data)
    form.autoscale.as_name.choices = get_aws_as_groups(cloud_provider, form.region.data, **aws_connection_data)
    form.build_infos.source_ami.choices = get_aws_ami_ids(cloud_provider, form.region.data, **aws_connection_data)
    form.build_infos.container.choices = get_ghost_lxd_images()
    form.build_infos.subnet_id.choices = get_aws_subnet_ids(cloud_provider, form.region.data, form.vpc_id.data,
                                                            **aws_connection_data)
    form.environment_infos.instance_profile.choices = get_aws_iam_instance_profiles(cloud_provider, form.region.data,
                                                                                    **aws_connection_data)
    form.environment_infos.key_name.choices = get_aws_ec2_key_pairs(cloud_provider, form.region.data,
                                                                    **aws_connection_data)
    for subnet in form.environment_infos.subnet_ids:
        subnet.choices = get_aws_subnet_ids(cloud_provider, form.region.data, form.vpc_id.data, **aws_connection_data)
    for sg in form.environment_infos.security_groups:
        sg.choices = get_aws_sg_ids(cloud_provider, form.region.data, form.vpc_id.data, **aws_connection_data)

    # Display default template in GET case
    return render_template('app_edit.html', form=form, edit=True, app_id=app_id,
                           schema=ghost_app_schema, forbidden_paths=FORBIDDEN_PATH)


@app.route('/web/apps/<app_id>/command', methods=['GET', 'POST'])
@app.route('/web/apps/<app_id>/command/<default_command>', methods=['GET', 'POST'])
def web_app_command(app_id, default_command='deploy'):
    form = CommandAppForm(app_id)
    app = get_ghost_app(app_id)
    aws_connection_data = get_aws_connection_data(app.get('assumed_account_id', ''), app.get('assumed_role_name', ''),
                                                  app.get('assumed_region_name', ''))

    # Dynamic selections update
    if form.is_submitted():
        form.safe_deployment_strategy.choices = get_safe_deployment_possibilities(app)
        form.rolling_update_strategy.choices = form.safe_deployment_strategy.choices
        form.subnet.choices = get_aws_subnets_ids_from_app(DEFAULT_PROVIDER, app['region'],
                                                           app['environment_infos']['subnet_ids'],
                                                           **aws_connection_data)

    # Perform validation
    if form.validate_on_submit():
        message = create_ghost_job(app_id, form, headers)

        return render_template('action_completed.html', message=message)

    # Display default template in GET case
    form.map_from_app(app)

    if not form.is_submitted():
        form.fabric_execution_strategy.data = config.get('fabric_execution_strategy', 'serial')
        form.skip_provisioner_bootstrap.data = config.get('skip_provisioner_bootstrap',
                                                          config.get('skip_salt_bootstrap', True))
        form.prepare_bg_copy_ami.data = get_blue_green_copy_ami_config(config)
        form.prepare_create_temp_elb.data = get_blue_green_create_temporary_elb_config(config)
        form.to_execute_script.data = DEFAULT_BASH_SHEBANG
        form.command.data = default_command

    return render_template('app_command.html', form=form, app=app)


@app.route('/web/apps/<app_id>/command/job/<job_id>', methods=['GET', 'POST'])
def web_app_command_from_job(app_id, job_id):
    form = CommandAppForm(app_id)
    app = get_ghost_app(app_id)
    aws_connection_data = get_aws_connection_data(app.get('assumed_account_id', ''), app.get('assumed_role_name', ''),
                                                  app.get('assumed_region_name', ''))

    # Dynamic selections update
    if form.is_submitted():
        form.safe_deployment_strategy.choices = get_safe_deployment_possibilities(app)
        form.rolling_update_strategy.choices = form.safe_deployment_strategy.choices
        form.subnet.choices = get_aws_subnets_ids_from_app(DEFAULT_PROVIDER, app['region'],
                                                           app['environment_infos']['subnet_ids'],
                                                           **aws_connection_data)

    # Perform validation
    if form.validate_on_submit():
        message = create_ghost_job(app_id, form, headers)

        return render_template('action_completed.html', message=message)

    # Display default template in GET case
    form.map_from_app(app)

    # Get job info and map command form
    job = get_ghost_job(job_id)

    form.command.data = job['command']

    if job['command'] == 'deploy' and 'options' in job and len(job['options']):
        form.fabric_execution_strategy.data = job['options'][0]
    else:
        form.fabric_execution_strategy.data = config.get('fabric_execution_strategy', 'serial')
    if job['command'] == 'buildimage' and 'options' in job and len(job['options']):
        form.skip_provisioner_bootstrap.data = job['options'][0]
    else:
        form.skip_provisioner_bootstrap.data = config.get('skip_provisioner_bootstrap',
                                                          config.get('skip_salt_bootstrap', True))

    if job['command'] == 'deploy':
        job_modules = {}
        for mod in job['modules']:
            job_modules[mod['name']] = mod
        # Map deployed modules
        for form_module in form.modules:
            if form_module.form.name.data in job_modules.keys():
                form_module.deploy.data = True
                form_module.rev.data = job_modules[form_module.form.name.data]['rev']
        # Map safe deployment options
        if 'options' in job and len(job['options']) > 1:
            form.safe_deployment.data = True
            form.safe_deployment_strategy.choices = get_safe_deployment_possibilities(app)
            form.safe_deployment_strategy.data = job['options'][1]

    if job['command'] == 'redeploy' and 'options' in job and len(job['options']):
        form.deploy_id.data = job['options'][0]
        # Map fabric_execution_strategy
        if 'options' in job and len(job['options']) > 1:
            form.fabric_execution_strategy.data = job['options'][1]
        else:
            form.fabric_execution_strategy.data = config.get('fabric_execution_strategy', 'serial')
        # Map safe deployment options
        if 'options' in job and len(job['options']) > 2:
            form.safe_deployment.data = True
            form.safe_deployment_strategy.choices = get_safe_deployment_possibilities(app)
            form.safe_deployment_strategy.data = job['options'][2]

    if job['command'] == 'executescript' and 'options' in job and len(job['options']):
        # Map script
        if 'options' in job and len(job['options']) > 0:
            form.to_execute_script.data = b64decode_utf8(job['options'][0])
        else:
            form.to_execute_script.data = DEFAULT_BASH_SHEBANG
        # Map script_module_context
        if 'options' in job and len(job['options']) > 1:
            form.script_module_context.data = job['options'][1]
        # Map execution_strategy
        if 'options' in job and len(job['options']) > 2:
            form.execution_strategy.data = job['options'][2]
        if 'options' in job and len(job['options']) > 3:
            if form.execution_strategy.data == 'single':
                form.single_host_instance.data = job['options'][3]
            else:
                form.safe_deployment_strategy.choices = get_safe_deployment_possibilities(app)
                form.safe_deployment_strategy.data = job['options'][3]

    if job['command'] == 'recreateinstances' and 'options' in job and len(job['options']):
        form.rolling_update.data = True
        form.rolling_update_strategy.choices = get_safe_deployment_possibilities(app)
        form.rolling_update_strategy.data = job['options'][0]

    if job['command'] == 'createinstance' and 'options' in job and len(job['options']) > 0:
        form.subnet.choices = get_aws_subnets_ids_from_app(DEFAULT_PROVIDER, app['region'],
                                                           app['environment_infos']['subnet_ids'],
                                                           **aws_connection_data)
        form.subnet.data = job['options'][0]
        if len(job['options']) > 1:
            form.private_ip_address.data = job['options'][1]

    if job['command'] == 'preparebluegreen' and 'options' in job:
        if len(job['options']) > 0:
            form.prepare_bg_copy_ami.data = boolify(job['options'][0])
        if len(job['options']) > 1:
            form.prepare_create_temp_elb.data = boolify(job['options'][1])

    return render_template('app_command.html', form=form, app=app)


@app.route('/web/apps/<app_id>/command/module/<module>', methods=['GET', 'POST'])
def web_app_module_last_revision(app_id, module):
    last_revision = ''
    deployments = get_ghost_deployments('{{"app_id": "{}", "module": "{}"}}'.format(app_id, module))
    if deployments and len(deployments) > 0:
        last_revision = deployments[0].get('revision', '')
    return last_revision


@app.route('/web/apps/<app_id>/command/deploy/safe_possibilities', methods=['GET'])
def web_app_get_safe_deployment_possibilities(app_id):
    # Get App data
    app = get_ghost_app(app_id)
    if not app:
        r = jsonify({'error': 'invalid app ID'})
        r.status_code = 400
        return r
    return jsonify(dict(get_safe_deployment_possibilities(app)))


@app.route('/web/apps/<app_id>/module/<module_name>/available-revisions')
def web_app_git_ls_remote(app_id, module_name):
    # Get App data
    app = get_ghost_app(app_id)
    source_url = ""
    source_protocol = None
    for mod in app['modules']:
        if mod['name'] == module_name:
            source_url = mod['source']['url']
            source_protocol = mod['source']['protocol']
    # We don't use jsonify here because it casts to dict, which is not sortable in Javascript/JSON
    if source_protocol == 'git':
        return json.dumps(git_ls_remote_branches_tags(source_url))
    else:
        return json.dumps(s3_list_object_revisions(app, source_url))


@app.route('/web/apps/<app_id>/delete', methods=['GET', 'POST'])
def web_app_delete(app_id):
    form = DeleteAppForm()

    # Perform validation
    if form.validate_on_submit and form.confirmation.data == 'yes':
        local_headers = headers.copy()
        local_headers['If-Match'] = form.etag.data

        message, status_code = delete_ghost_app(app_id, local_headers)

        if ui_helpers.check_status_code(status_code):
            return redirect(url_for('web_app_list'))
        else:
            return render_template('action_completed.html', message=message, form_action='delete')
    elif form.validate_on_submit and form.confirmation.data == 'no':
        flash('App "{}" has not been deleted'.format(app_id), 'info')
        return redirect(url_for('web_app_list'), code=301)

    # Get Application etag
    app = get_ghost_app(app_id)
    form.etag.data = app.get('_etag', '')

    # Display default template in GET case
    return render_template('app_delete.html', form=form, app=app)


@app.route('/web/jobs')
def web_job_list():
    page = request.args.get('page', '1')
    application_name = request.args.get('application') or None
    application_env = request.args.get('env') or None
    application_role = request.args.get('role') or None
    job_user = request.args.get('user') or None
    job_status = request.args.get('status') or None
    job_command = request.args.get('command') or None

    query_values = {
        'application_name': application_name,
        'application_env': application_env,
        'application_role': application_role,
        'job_user': job_user,
        'job_status': job_status,
        'job_command': job_command
    }

    jobs = get_ghost_jobs(page=page, application_name=application_name, application_role=application_role,
                          application_env=application_env, job_status=job_status, job_command=job_command,
                          job_user=job_user)
    envs = get_ghost_envs(with_wildcard=False)
    roles = get_ghost_roles(with_wildcard=False)

    if request.is_xhr:
        return render_template('job_list_content.html', jobs=jobs, env_list=envs, role_list=roles,
                               deletable_job_statuses=DELETABLE_JOB_STATUSES,
                               cancellable_job_statuses=CANCELLABLE_JOB_STATUSES,
                               page=int(page))

    return render_template('job_list.html', jobs=jobs, env_list=envs, role_list=roles,
                           deletable_job_statuses=DELETABLE_JOB_STATUSES,
                           cancellable_job_statuses=CANCELLABLE_JOB_STATUSES,
                           query_values=query_values, page=int(page))


@app.route('/web/jobs/<job_id>', methods=['GET'])
def web_job_view(job_id):
    job = get_ghost_job(job_id)

    if request.is_xhr:
        return jsonify(job)

    websocket_token = get_ghost_websocket_token(job_id)

    return render_template('job_view.html', job=job, websocket_token=websocket_token,
                           deletable_job_statuses=DELETABLE_JOB_STATUSES,
                           cancellable_job_statuses=CANCELLABLE_JOB_STATUSES)


@app.route('/web/jobs/<job_id>/delete', methods=['GET', 'POST'])
def web_job_delete(job_id):
    form = DeleteJobForm()

    # Perform validation
    if form.validate_on_submit and form.confirmation.data == 'yes':
        local_headers = headers.copy()
        local_headers['If-Match'] = form.etag.data

        message, status_code = delete_ghost_job(job_id, local_headers)

        if ui_helpers.check_status_code(status_code):
            return redirect(url_for('web_job_list'))
        else:
            return render_template('action_completed.html', message=message, form_action='delete')
    elif form.validate_on_submit and form.confirmation.data == 'no':
        flash('Job "{}" has not been deleted'.format(job_id), 'info')
        return redirect(url_for('web_job_list'), code=301)

    # Get job etag
    job = get_ghost_job(job_id)
    if job and job.get('status', '') in DELETABLE_JOB_STATUSES:
        form.etag.data = job['_etag']

    # Display default template in GET case
    return render_template('job_delete.html', form=form, job=job)


@app.route('/web/jobs/<job_id>/cancel', methods=['GET', 'POST'])
def web_job_cancel(job_id):
    form = CancelJobForm()

    # Perform validation
    if form.validate_on_submit and form.confirmation.data == 'yes':
        local_headers = headers.copy()
        local_headers['If-Match'] = form.etag.data

        message = cancel_ghost_job(job_id, local_headers)

        return render_template('action_completed.html', message=message)

    # Get job etag
    job = get_ghost_job(job_id)
    if job and job.get('status', '') in CANCELLABLE_JOB_STATUSES:
        form.etag.data = job['_etag']

    # Display default template in GET case
    return render_template('job_cancel.html', form=form, job=job)


@app.route('/web/deployments')
def web_deployments_list():
    page = request.args.get('page', '1')
    application_name = request.args.get('application') or None
    application_env = request.args.get('env') or None
    application_role = request.args.get('role') or None
    deployment_revision = request.args.get('revision') or None
    deployment_module = request.args.get('module') or None

    query_values = {
        'application_name': application_name,
        'application_env': application_env,
        'application_role': application_role,
        'deployment_revision': deployment_revision,
        'deployment_module': deployment_module,
    }

    deployments = get_ghost_deployments(page=page, application_name=application_name, application_role=application_role,
                                        application_env=application_env, deployment_revision=deployment_revision, deployment_module=deployment_module)
    envs = get_ghost_envs(with_wildcard=False)
    roles = get_ghost_roles(with_wildcard=False)

    if request.is_xhr:
        return render_template('deployment_list_content.html', env_list=envs, role_list=roles, page=int(page),
                               deployments=deployments, bucket_s3=config.get('bucket_s3'))

    return render_template('deployment_list.html', env_list=envs, role_list=roles, page=int(page),
                           deployments=deployments, bucket_s3=config.get('bucket_s3'), query_values=query_values)


@app.route('/web/deployments/<deployment_id>', methods=['GET'])
def web_deployments_view(deployment_id):
    # Get Deployment
    deployment = get_ghost_deployment(deployment_id)

    return render_template('deployment_view.html', deployment=deployment, bucket_s3=config.get('bucket_s3'))


@app.route('/web/deployments/<deployment_id>/redeploy', methods=['GET', 'POST'])
def web_deployment_redeploy(deployment_id):
    # Get Deployment
    deployment = get_ghost_deployment(deployment_id)

    app = deployment['app_id']
    form = CommandAppForm(app['_id'])

    form.command.data = 'redeploy'
    form.deploy_id.data = deployment_id

    # Dynamic selections update
    if form.is_submitted():
        safe_choices = get_safe_deployment_possibilities(app)
        form.safe_deployment_strategy.choices = list(safe_choices)

    # Perform validation
    if form.validate_on_submit():
        message = create_ghost_job(app['_id'], form, headers)

        return render_template('action_completed.html', message=message)

    # Display default template in GET case
    return render_template('app_command.html', form=form, app=app)


@app.route('/web/webhooks', methods=['GET'])
def web_webhook_list():
    query = request.args.get('where', None)
    page = request.args.get('page', '1')
    application_name = request.args.get('application') or None
    module = request.args.get('module') or None
    webhook_revision = request.args.get('revision') or None

    query_values = {
        'application_name': application_name,
        'webhook_revision': webhook_revision,
        'module': module,
    }

    webhooks = get_ghost_webhooks(query, page, application_name, module, webhook_revision)

    # Generate error message if at least one of the webhook configs is invalid
    if not ui_helpers.check_webhooks_validity(webhooks):
        flash('At least one of your webhooks is invalid: invalid app or module.', 'danger')

    if request.is_xhr:
        return render_template('webhook_list_content.html', webhooks=webhooks, page=int(page), query_values=query_values)

    return render_template('webhook_list.html', webhooks=webhooks, page=int(page), query_values=query_values)


@app.route('/web/webhooks/all/invocations', methods=['GET'])
def web_webhook_list_all_invocations():
    query = request.args.get('where', None)
    page = request.args.get('page', '1')
    invocations = get_ghost_webhooks_invocations(query, page)

    if request.is_xhr:
        return render_template('webhook_invocation_list_content.html', invocations=invocations, page=int(page), all=True)

    return render_template('webhook_invocation_list.html', invocations=invocations, page=int(page), all=True)

@app.route('/web/webhooks/<webhook_id>/', methods=['GET'])
def web_webhook_redirect_list_invocations(**kwargs):
    return redirect(url_for('web_webhook_list_invocations', **kwargs), code=301)

@app.route('/web/webhooks/<webhook_id>/invocations/', methods=['GET'])
def web_webhook_list_invocations(webhook_id):
    query = request.args.get('where', None)
    page = request.args.get('page', '1')
    invocations = get_ghost_webhooks_invocations(query, page, webhook_id)
    webhook = get_ghost_webhook(webhook_id)

    if request.is_xhr:
        return render_template('webhook_invocation_list_content.html', invocations=invocations, page=int(page),
                               all=False, webhook=webhook)

    return render_template('webhook_invocation_list.html', invocations=invocations, page=int(page),
                           all=False, webhook=webhook)


@app.route('/web/webhooks/<webhook_id>/delete', methods=['GET', 'POST'])
def web_webhook_delete(webhook_id):
    form = DeleteWebhookForm()

    # Perform validation
    if form.validate_on_submit and form.confirmation.data == 'yes':
        local_headers = headers.copy()
        local_headers['If-Match'] = form.etag.data

        message, status_code = delete_ghost_webhook(webhook_id, local_headers)

        if ui_helpers.check_status_code(status_code):
            return redirect(url_for('web_webhook_list'))
        else:
            return render_template('action_completed.html', message=message, form_action='delete')
    elif form.validate_on_submit and form.confirmation.data == 'no':
        flash('Webhook "%s" has not been deleted' % webhook_id, 'info')
        return redirect(url_for('web_webhook_list'), code=301)

    # Get webhook etag
    webhook = get_ghost_webhook(webhook_id)
    form.etag.data = webhook['_etag']

    # Display default template in GET case
    return render_template('webhook_delete.html', form=form, webhook=webhook)


@app.route('/web/webhooks/create', methods=['GET', 'POST'])
def web_webhook_create():
    form = CreateWebhookForm()

    if form.is_submitted():
        # Set dynamic fields
        apps = get_ghost_apps()
        form.app_id.choices = [(app['_id'], "{name} ({id})".format(name=app['name'], id=app['_id'])) for app in apps]
        selected_app = get_ghost_app(form.app_id.data)
        form.module.choices = get_ghost_modules_names(selected_app['_id'])
        form.safe_deployment_strategy.choices = get_safe_deployment_possibilities(selected_app)
        form.instance_type.choices = get_aws_ec2_instance_types(selected_app["region"])

    if form.validate_on_submit():
        webhook = {}
        form.map_to_webhook(webhook)

        message, result, status_code = create_ghost_webhook(webhook)
        webhook_id = result['_id'] if '_id' in result else None

        return render_template('action_completed.html', message=message, action_object_type='webhooks',
                               action_object_id=webhook_id,
                               status_code=status_code,
                               cmd_recommendations=None)

    # Set dynamic fields
    apps = get_ghost_apps()
    if not apps:
        flash('You need at least 1 app to create a webhook', 'info')
        return redirect(url_for('web_app_list'), code=301)
    form.app_id.choices = [(app['_id'], "{name} ({id})".format(name=app['name'], id=app['_id'])) for app in apps]
    form.module.choices = get_ghost_modules_names(apps[0]['_id'])
    form.safe_deployment_strategy.choices = get_safe_deployment_possibilities(apps[0])
    form.instance_type.choices = get_aws_ec2_instance_types(apps[0]["region"])

    # Display default template in GET case
    return render_template('webhook_edit.html', form=form, edit=False, app=apps[0],
                           schema=ghost_webhook_schema, forbidden_paths=FORBIDDEN_PATH)


@app.route('/web/webhooks/<webhook_id>/edit', methods=['GET', 'POST'])
def web_webhook_edit(webhook_id):
    form = EditWebhookForm()

    if form.is_submitted():
        # Set read-only fields to pass validation
        webhook = get_ghost_webhook(webhook_id)
        form.app_id.choices = [(webhook['app_id']['_id'], webhook['app_id']['_id'])]
        form.app_id.data = webhook['app_id']['_id']

        # Set dynamic fields
        form.safe_deployment_strategy.choices = get_safe_deployment_possibilities(webhook['app_id'])
        form.instance_type.choices = get_aws_ec2_instance_types(webhook['app_id']['region'])
        form.module.choices = get_ghost_modules_names(webhook['app_id']['_id'])

    if form.validate_on_submit():
        local_headers = headers.copy()
        local_headers['If-Match'] = form.etag.data

        # Update Webhook
        webhook = {}
        form.map_to_webhook(webhook)

        # Remove read-only fields that cannot be changed
        del webhook['app_id']

        message, status_code = update_ghost_webhook(webhook_id, local_headers, webhook)

        return render_template('action_completed.html', message=message, action_object_type='webhooks',
                               action_object_id=webhook_id,
                               status_code=status_code)

    # Get webhook data on first access
    webhook = get_ghost_webhook(webhook_id)
    form.map_from_webhook(webhook)

    # Check app still exists
    if not webhook['app_id']:
        flash('Associated app has been removed! This webhook configuration is no '
              'longer useful and must then be removed.', 'danger')
        return redirect(url_for('web_webhook_delete', webhook_id=webhook_id))

    # Set dynamic fields
    form.safe_deployment_strategy.choices = get_safe_deployment_possibilities(webhook['app_id'])
    form.instance_type.choices = get_aws_ec2_instance_types(webhook['app_id']['region'])
    form.module.choices = get_ghost_modules_names(webhook['app_id']['_id'])

    # Display default template in GET case
    return render_template('webhook_edit.html', form=form, edit=True, webhook_id=webhook_id, webhook=webhook,
                           schema=ghost_webhook_schema, forbidden_paths=FORBIDDEN_PATH)


@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404
