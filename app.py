from flask import Flask, flash, render_template, request, Response, jsonify
from flask_bootstrap import Bootstrap
from flask.ext.login import LoginManager, UserMixin, login_required

from base64 import b64decode
import traceback
import sys
from sh import git
from settings import DEFAULT_PROVIDER

from models.jobs import CANCELLABLE_JOB_STATUSES, DELETABLE_JOB_STATUSES, JOB_STATUSES, jobs_schema as ghost_jobs_schema
from models.apps import apps_schema as ghost_app_schema

from ghost_tools import config
from ghost_client import get_ghost_apps, get_ghost_app, create_ghost_app, update_ghost_app, delete_ghost_app
from ghost_client import get_ghost_jobs, get_ghost_job, create_ghost_job, cancel_ghost_job, delete_ghost_job
from ghost_client import get_ghost_deployments, get_ghost_deployment
from ghost_client import headers, test_ghost_auth

from forms import CommandAppForm, CreateAppForm, DeleteAppForm, EditAppForm
from forms import CancelJobForm, DeleteJobForm
from forms import get_aws_ec2_regions, get_aws_ec2_instance_types, get_aws_vpc_ids, get_aws_sg_ids, get_aws_subnet_ids, get_aws_ami_ids, get_aws_ec2_key_pairs, get_aws_iam_instance_profiles, get_aws_as_groups
from forms import get_ghost_app_ec2_instances, get_ghost_app_as_group, get_as_group_instances, get_elbs_instances_from_as_group, get_safe_deployment_possibilities
from forms import get_wtforms_selectfield_values, get_aws_subnets_ids_from_app
from forms import get_aws_connection_data, check_aws_assumed_credentials

# Web UI App
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
            response = test_ghost_auth(user)

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

LEGACY_COMMANDS = ['destroyinstance','rollback']

@app.context_processor
def env_list():
    return dict(env_list=ghost_app_schema['env']['allowed'],
                role_list=ghost_app_schema['role']['allowed'],
                statuses=JOB_STATUSES,
                command_list=ghost_jobs_schema['command']['allowed']+LEGACY_COMMANDS)

try:
    CURRENT_REVISION_NAME=git('symbolic-ref', '-q', '--short', 'HEAD', _tty_out=False)
except:
    try:
        CURRENT_REVISION_NAME=git('describe', '--tags', '--exact-match', _tty_out=False)
    except:
        CURRENT_REVISION_NAME=git('--no-pager', 'rev-parse', '--short', 'HEAD', _tty_out=False).strip()

try:
    CURRENT_REVISION = dict(
        current_revision=git('--no-pager', 'rev-parse', '--short', 'HEAD', _tty_out=False).strip(),
        current_revision_date=git('log', '-1', '--format=%cD', _tty_out=False).strip(),
        current_revision_name=CURRENT_REVISION_NAME.strip()
    )
except:
    CURRENT_REVISION = dict(
        current_revision='unknown',
        current_revision_date='unknown',
        current_revision_name='unknown'
    )

@app.context_processor
def current_revision():
    return CURRENT_REVISION

@app.route('/web/<provider>/identity/check/<account_id>/<role_name>/<region_name>')
def web_cloud_check_assume_role_region(provider, account_id, role_name, region_name):
    try:
        check =  check_aws_assumed_credentials(provider, account_id, role_name, region_name)
    except:
        traceback.print_exc()
        message = 'Failure: %s' % (sys.exc_info()[1])
        flash(message, 'danger')
        check = False
    return jsonify({'result' : check})

@app.route('/web/<provider>/identity/check/<account_id>/<role_name>/')
def web_cloud_check_assume_role(provider, account_id, role_name):
    try:
        check =  check_aws_assumed_credentials(provider, account_id, role_name)
    except:
        traceback.print_exc()
        message = 'Failure: %s' % (sys.exc_info()[1])
        flash(message, 'danger')
        check = False
    return jsonify({'result' : check})

@app.route('/web/<provider>/regions')
def web_cloud_regions(provider):
    query_string = dict((key, request.args.getlist(key) if len(request.args.getlist(key)) > 1
        else request.args.getlist(key)[0]) for key in request.args.keys())
    return jsonify(get_aws_ec2_regions(provider, **query_string))

@app.route('/web/<provider>/regions/<region_id>/ec2/instancetypes')
def web_ec2_instance_types_list(provider, region_id):
    return jsonify(get_aws_ec2_instance_types(region_id))

@app.route('/web/<provider>/regions/<region_id>/ec2/keypairs')
def web_ec2_key_pairs_list(provider, region_id):
    query_string = dict((key, request.args.getlist(key) if len(request.args.getlist(key)) > 1
        else request.args.getlist(key)[0]) for key in request.args.keys())
    return jsonify(get_aws_ec2_key_pairs(provider, region_id, **query_string))

@app.route('/web/<provider>/regions/<region_id>/ec2/autoscale/ids')
def web_ec2_as_list(provider, region_id):
    query_string = dict((key, request.args.getlist(key) if len(request.args.getlist(key)) > 1
        else request.args.getlist(key)[0]) for key in request.args.keys())
    return jsonify(get_aws_as_groups(provider, region_id, **query_string))

@app.route('/web/<provider>/regions/<region_id>/iam/profiles')
def web_iam_profiles_list(provider, region_id):
    query_string = dict((key, request.args.getlist(key) if len(request.args.getlist(key)) > 1
        else request.args.getlist(key)[0]) for key in request.args.keys())
    return jsonify(get_aws_iam_instance_profiles(provider, region_id, **query_string))

@app.route('/web/<provider>/regions/<region_id>/vpc/ids')
def web_vpcs_list(provider, region_id):
    query_string = dict((key, request.args.getlist(key) if len(request.args.getlist(key)) > 1
        else request.args.getlist(key)[0]) for key in request.args.keys())
    return jsonify(get_aws_vpc_ids(provider, region_id, **query_string))

@app.route('/web/<provider>/regions/<region_id>/vpc/<vpc_id>/sg/ids')
def web_sgs_list(provider, region_id, vpc_id):
    query_string = dict((key, request.args.getlist(key) if len(request.args.getlist(key)) > 1
        else request.args.getlist(key)[0]) for key in request.args.keys())
    return jsonify(get_aws_sg_ids(provider, region_id, vpc_id, **query_string))

@app.route('/web/<provider>/regions/<region_id>/vpc/<vpc_id>/subnet/ids')
def web_subnets_list(provider, region_id, vpc_id):
    query_string = dict((key, request.args.getlist(key) if len(request.args.getlist(key)) > 1
        else request.args.getlist(key)[0]) for key in request.args.keys())
    return jsonify(get_aws_subnet_ids(provider, region_id, vpc_id, **query_string))

@app.route('/web/<provider>/regions/<region_id>/ami/ids')
def web_amis_list(provider, region_id):
    query_string = dict((key, request.args.getlist(key) if len(request.args.getlist(key)) > 1
        else request.args.getlist(key)[0]) for key in request.args.keys())
    return jsonify(get_aws_ami_ids(provider, region_id, **query_string))

@app.route('/web/<provider>/appinfos/<app_id>/subnet/ids')
def web_app_subnets_list(provider, app_id):
    # Get App data
    app = get_ghost_app(app_id)
    aws_connection_data = get_aws_connection_data(app.get('assumed_account_id', ''), app.get('assumed_role_name', ''), app.get('assumed_region_name', ''))
    return jsonify(get_aws_subnets_ids_from_app(DEFAULT_PROVIDER, app['region'], app['environment_infos']['subnet_ids'], **aws_connection_data))

@app.route('/web/<provider>/appinfos/<app_id>', methods=['GET'])
def web_app_infos(provider, app_id):
    # Get App data
    app = get_ghost_app(app_id)
    aws_connection_data = get_aws_connection_data(app.get('assumed_account_id', ''), app.get('assumed_role_name', ''), app.get('assumed_region_name', ''))
    if app['autoscale']['name']:
        as_group = get_ghost_app_as_group(app.get('provider', DEFAULT_PROVIDER), app['autoscale']['name'], app['region'], **aws_connection_data)
        if as_group:
            as_instances = get_as_group_instances(app.get('provider', DEFAULT_PROVIDER), as_group, app['region'], **aws_connection_data)
            elbs_instances = get_elbs_instances_from_as_group(app.get('provider', DEFAULT_PROVIDER), as_group, app['region'], **aws_connection_data)
            ghost_instances = get_ghost_app_ec2_instances(app.get('provider', DEFAULT_PROVIDER), app['name'], app['env'], app['role'], app['region'], filters=as_instances, **aws_connection_data)
            return render_template('app_infos_content.html', app=app, ghost_instances=ghost_instances, as_group=as_group, as_instances=as_instances, elbs_instances=elbs_instances)
        else:
            ghost_instances = get_ghost_app_ec2_instances(app.get('provider', DEFAULT_PROVIDER), app['name'], app['env'], app['role'], app['region'], **aws_connection_data)
            return render_template('app_infos_content.html', app=app, ghost_instances=ghost_instances)
    else:
        ghost_instances = get_ghost_app_ec2_instances(app.get('provider', DEFAULT_PROVIDER), app['name'], app['env'], app['role'], app['region'], **aws_connection_data)
        return render_template('app_infos_content.html', app=app, ghost_instances=ghost_instances)

@app.route('/web/apps')
def web_app_list():
    query = request.args.get('where', None)
    page = request.args.get('page', '1')
    apps = get_ghost_apps(query, page)
    if request.is_xhr:
        return render_template('app_list_content.html', apps=apps,
                               page=int(page))
    return render_template('app_list.html', apps=apps,
                           page=int(page))

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
        #form.region.choices = get_aws_ec2_regions(form.provider.data, **aws_connection_data)
        form.instance_type.choices = get_aws_ec2_instance_types(form.region.data)
        form.vpc_id.choices = get_aws_vpc_ids(cloud_provider, form.region.data, **aws_connection_data)
        form.autoscale.as_name.choices = get_aws_as_groups(cloud_provider, form.region.data, **aws_connection_data)
        form.build_infos.source_ami.choices = get_aws_ami_ids(cloud_provider, form.region.data, **aws_connection_data)
        form.build_infos.subnet_id.choices = get_aws_subnet_ids(cloud_provider, form.region.data, form.vpc_id.data, **aws_connection_data)
        form.environment_infos.instance_profile.choices = get_aws_iam_instance_profiles(cloud_provider, form.region.data, **aws_connection_data)
        form.environment_infos.key_name.choices = get_aws_ec2_key_pairs(cloud_provider, form.region.data, **aws_connection_data)
        for subnet in form.environment_infos.subnet_ids:
            subnet.choices = get_aws_subnet_ids(cloud_provider, form.region.data, form.vpc_id.data, **aws_connection_data)
        for sg in  form.environment_infos.security_groups:
            sg.choices = get_aws_sg_ids(cloud_provider, form.region.data, form.vpc_id.data, **aws_connection_data)

    # Perform validation
    if form.validate_on_submit():
        app = {}
        form.map_to_app(app)

        message, result = create_ghost_app(app)
        app_id = result['_id'] if '_id' in result else None
        return render_template('action_completed.html', message=message, action_object_type='apps', action_object_id=app_id)

    if clone_from_app:
        form.map_from_app(clone_from_app)
        if not form.is_submitted():
            if clone_from_app.get('assumed_account_id', None) and clone_from_app.get('assumed_role_name', None):
                form.use_custom_identity.data = True
            aws_connection_data = get_aws_connection_data(clone_from_app.get('assumed_account_id', ''), clone_from_app.get('assumed_role_name', ''), clone_from_app.get('assumed_region_name', ''))
            form.region.choices = get_aws_ec2_regions(clone_from_app.get('provider', DEFAULT_PROVIDER), **aws_connection_data)
            form.instance_type.choices = get_aws_ec2_instance_types(clone_from_app['region'])
            form.vpc_id.choices = get_aws_vpc_ids(clone_from_app.get('provider', DEFAULT_PROVIDER), clone_from_app['region'], **aws_connection_data)
            form.autoscale.as_name.choices = get_aws_as_groups(clone_from_app.get('provider', DEFAULT_PROVIDER), clone_from_app['region'], **aws_connection_data)
            form.build_infos.source_ami.choices = get_aws_ami_ids(clone_from_app.get('provider', DEFAULT_PROVIDER), clone_from_app['region'], **aws_connection_data)
            form.build_infos.subnet_id.choices = get_aws_subnet_ids(clone_from_app.get('provider', DEFAULT_PROVIDER), clone_from_app['region'], clone_from_app['vpc_id'], **aws_connection_data)
            form.environment_infos.instance_profile.choices = get_aws_iam_instance_profiles(clone_from_app.get('provider', DEFAULT_PROVIDER), clone_from_app['region'], **aws_connection_data)
            form.environment_infos.key_name.choices = get_aws_ec2_key_pairs(clone_from_app.get('provider', DEFAULT_PROVIDER), clone_from_app['region'], **aws_connection_data)
            for subnet in form.environment_infos.subnet_ids:
                subnet.choices = get_aws_subnet_ids(clone_from_app.get('provider', DEFAULT_PROVIDER), clone_from_app['region'], clone_from_app['vpc_id'], **aws_connection_data)
            for sg in  form.environment_infos.security_groups:
                sg.choices = get_aws_sg_ids(clone_from_app.get('provider', DEFAULT_PROVIDER), clone_from_app['region'], clone_from_app['vpc_id'], **aws_connection_data)

    # Display default template in GET case
    return render_template('app_edit.html', form=form, edit=False)

@app.route('/web/apps/<app_id>', methods=['GET'])
def web_app_view(app_id):
    # Get App data
    app = get_ghost_app(app_id, embed_deployments=True)

    return render_template('app_view.html', app=app)

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
            aws_connection_data = get_aws_connection_data(form.assumed_account_id.data, form.assumed_role_name.data, form.assumed_region_name.data)
        else:
            form.assumed_account_id.data = ""
            form.assumed_role_name.data = ""
            form.assumed_region_name.data = ""
            aws_connection_data = {}
        form.region.choices = get_aws_ec2_regions(cloud_provider, **aws_connection_data)
        form.instance_type.choices = get_aws_ec2_instance_types(form.region.data)
        form.vpc_id.choices = get_aws_vpc_ids(cloud_provider, form.region.data, **aws_connection_data)
        form.autoscale.as_name.choices = get_aws_as_groups(cloud_provider, form.region.data, **aws_connection_data)
        form.build_infos.source_ami.choices = get_aws_ami_ids(cloud_provider, form.region.data, **aws_connection_data)
        form.build_infos.subnet_id.choices = get_aws_subnet_ids(cloud_provider, form.region.data, form.vpc_id.data, **aws_connection_data)
        form.environment_infos.instance_profile.choices = get_aws_iam_instance_profiles(cloud_provider, form.region.data, **aws_connection_data)
        form.environment_infos.key_name.choices = get_aws_ec2_key_pairs(cloud_provider, form.region.data, **aws_connection_data)
        for subnet in form.environment_infos.subnet_ids:
            subnet.choices = get_aws_subnet_ids(cloud_provider, form.region.data, form.vpc_id.data, **aws_connection_data)
        for sg in  form.environment_infos.security_groups:
            sg.choices = get_aws_sg_ids(cloud_provider, form.region.data, form.vpc_id.data, **aws_connection_data)

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

        message = update_ghost_app(app_id, local_headers, app)

        #if form.update_manifest.data:
        #TODO Perform Manifest update

        return render_template('action_completed.html', message=message, action_object_type='apps', action_object_id=app_id)

    # Get App data on first access
    if not form.etag.data:
        app = get_ghost_app(app_id)
        form.map_from_app(app)

    # Remove alternative options from select fields that cannot be changed
    form.env.choices = [(form.env.data, form.env.data)]
    form.role.choices = [(form.role.data, form.role.data)]

    aws_connection_data = get_aws_connection_data(form.assumed_account_id.data, form.assumed_role_name.data, form.assumed_region_name.data)
    form.region.choices = get_aws_ec2_regions(cloud_provider, **aws_connection_data)
    form.instance_type.choices = get_aws_ec2_instance_types(form.region.data)
    form.vpc_id.choices = get_aws_vpc_ids(cloud_provider, form.region.data, **aws_connection_data)
    form.autoscale.as_name.choices = get_aws_as_groups(cloud_provider, form.region.data, **aws_connection_data)
    form.build_infos.source_ami.choices = get_aws_ami_ids(cloud_provider, form.region.data, **aws_connection_data)
    form.build_infos.subnet_id.choices = get_aws_subnet_ids(cloud_provider, form.region.data, form.vpc_id.data, **aws_connection_data)
    form.environment_infos.instance_profile.choices = get_aws_iam_instance_profiles(cloud_provider, form.region.data, **aws_connection_data)
    form.environment_infos.key_name.choices = get_aws_ec2_key_pairs(cloud_provider, form.region.data, **aws_connection_data)
    for subnet in form.environment_infos.subnet_ids:
        subnet.choices = get_aws_subnet_ids(cloud_provider, form.region.data, form.vpc_id.data, **aws_connection_data)
    for sg in  form.environment_infos.security_groups:
        sg.choices = get_aws_sg_ids(cloud_provider, form.region.data, form.vpc_id.data, **aws_connection_data)

    # Display default template in GET case
    return render_template('app_edit.html', form=form, edit=True)

@app.route('/web/apps/<app_id>/command', methods=['GET', 'POST'])
def web_app_command(app_id):
    form = CommandAppForm(app_id)
    app = get_ghost_app(app_id)

    # Dynamic selections update
    if form.is_submitted():
        form.safe_deployment_strategy.choices = get_safe_deployment_possibilities(app)
        form.subnet.choices = [('', '')] + get_wtforms_selectfield_values(app['environment_infos']['subnet_ids'])

    # Perform validation
    if form.validate_on_submit():
        message = create_ghost_job(app_id, form, headers)

        return render_template('action_completed.html', message=message)

    # Display default template in GET case
    form.map_from_app(app)

    if not form.is_submitted():
        form.fabric_execution_strategy.data = config.get('fabric_execution_strategy', 'serial')
        form.skip_salt_bootstrap.data = config.get('skip_salt_bootstrap', True)
        form.command.data = 'deploy'

    return render_template('app_command.html', form=form, app=app)

@app.route('/web/apps/<app_id>/command/job/<job_id>', methods=['GET', 'POST'])
def web_app_command_from_job(app_id, job_id):
    form = CommandAppForm(app_id)
    app = get_ghost_app(app_id)

    # Dynamic selections update
    if form.is_submitted():
        form.safe_deployment_strategy.choices = get_safe_deployment_possibilities(app)

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
        form.skip_salt_bootstrap.data = job['options'][0]
    else:
        form.skip_salt_bootstrap.data = config.get('skip_salt_bootstrap', True)

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

    return render_template('app_command.html', form=form, app=app)

@app.route('/web/apps/<app_id>/command/module/<module>', methods=['GET', 'POST'])
def web_app_module_last_revision(app_id, module):
    last_revision = ''
    deployments = get_ghost_deployments('{"app_id": "%s", "module": "%s"}' % (app_id, module))
    if deployments and len(deployments) > 0:
        last_revision = deployments[0].get('revision', '')
    return last_revision

@app.route('/web/apps/<app_id>/command/deploy/safe_possibilities', methods=['GET'])
def web_app_get_safe_deployment_possibilities(app_id):
    # Get App data
    app = get_ghost_app(app_id)
    return jsonify(get_safe_deployment_possibilities(app))

@app.route('/web/apps/<app_id>/delete', methods=['GET', 'POST'])
def web_app_delete(app_id):
    form = DeleteAppForm()

    # Perform validation
    if form.validate_on_submit and form.confirmation.data == 'yes':
        local_headers = headers.copy()
        local_headers['If-Match'] = form.etag.data

        message = delete_ghost_app(app_id, local_headers)

        return render_template('action_completed.html', message=message)

    # Get Application etag
    app = get_ghost_app(app_id)
    form.etag.data = app.get('_etag', '')

    # Display default template in GET case
    return render_template('app_delete.html', form=form, app=app)

@app.route('/web/jobs')
def web_job_list():
    query = request.args.get('where', None)
    page = request.args.get('page', '1')
    jobs = get_ghost_jobs(query, page)

    if request.is_xhr:
        return render_template('job_list_content.html', jobs=jobs,
                           deletable_job_statuses=DELETABLE_JOB_STATUSES,
                           cancellable_job_statuses=CANCELLABLE_JOB_STATUSES,
                           page=int(page))

    return render_template('job_list.html', jobs=jobs,
                           deletable_job_statuses=DELETABLE_JOB_STATUSES,
                           cancellable_job_statuses=CANCELLABLE_JOB_STATUSES,
                           page=int(page))

@app.route('/web/jobs/<job_id>', methods=['GET'])
def web_job_view(job_id):
    job = get_ghost_job(job_id)

    if request.is_xhr:
        return jsonify(job)

    return render_template('job_view.html', job=job,
                           deletable_job_statuses=DELETABLE_JOB_STATUSES,
                           cancellable_job_statuses=CANCELLABLE_JOB_STATUSES)

@app.route('/web/jobs/<job_id>/delete', methods=['GET', 'POST'])
def web_job_delete(job_id):
    form = DeleteJobForm()

    # Perform validation
    if form.validate_on_submit and form.confirmation.data == 'yes':
        local_headers = headers.copy()
        local_headers['If-Match'] = form.etag.data

        message = delete_ghost_job(job_id, local_headers)

        return render_template('action_completed.html', message=message)

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
    query = request.args.get('where', None)
    page = request.args.get('page', '1')
    deployments = get_ghost_deployments(query, page)

    if request.is_xhr:
        return render_template('deployment_list_content.html', deployments=deployments,
                               page=int(page), bucket_s3=config.get('bucket_s3'))

    return render_template('deployment_list.html', deployments=deployments,
                           page=int(page), bucket_s3=config.get('bucket_s3'))

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

    # Perform validation
    if form.validate_on_submit():
        message = create_ghost_job(app['_id'], form, headers)

        return render_template('action_completed.html', message=message)

    # Display default template in GET case
    return render_template('app_command.html', form=form, app=app)
