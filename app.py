from flask import Flask, flash, render_template, request, Response, jsonify
from flask_bootstrap import Bootstrap
from flask.ext.login import LoginManager, UserMixin, login_required

from base64 import b64decode
import traceback
import sys

from models.jobs import CANCELLABLE_JOB_STATUSES, DELETABLE_JOB_STATUSES

from ghost_client import get_ghost_apps, get_ghost_app, create_ghost_app, update_ghost_app, delete_ghost_app
from ghost_client import get_ghost_jobs, get_ghost_job, create_ghost_job, cancel_ghost_job, delete_ghost_job
from ghost_client import get_ghost_deployments, get_ghost_deployment
from ghost_client import headers, test_ghost_auth

from forms import CommandAppForm, CreateAppForm, DeleteAppForm, EditAppForm
from forms import CancelJobForm, DeleteJobForm
from forms import get_aws_ec2_instance_types, get_aws_vpc_ids, get_aws_sg_ids, get_aws_subnet_ids, get_aws_ami_ids

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

@app.route('/web/aws/regions/<region_id>/ec2/instancetypes')
def web_ec2_instance_types_list(region_id):
    return jsonify(get_aws_ec2_instance_types(region_id))

@app.route('/web/aws/regions/<region_id>/vpc/ids')
def web_vpcs_list(region_id):
    return jsonify(get_aws_vpc_ids(region_id))

@app.route('/web/aws/regions/<region_id>/vpc/<vpc_id>/sg/ids')
def web_sgs_list(region_id, vpc_id):
    return jsonify(get_aws_sg_ids(region_id, vpc_id))

@app.route('/web/aws/regions/<region_id>/vpc/<vpc_id>/subnet/ids')
def web_subnets_list(region_id, vpc_id):
    return jsonify(get_aws_subnet_ids(region_id, vpc_id))

@app.route('/web/aws/regions/<region_id>/ami/ids')
def web_amis_list(region_id):
    return jsonify(get_aws_ami_ids(region_id))

@app.route('/web/apps')
def web_app_list():
    query = request.args.get('where', None)
    apps = get_ghost_apps(query)
    return render_template('app_list.html', apps=apps)

@app.route('/web/apps/create', methods=['GET', 'POST'])
def web_app_create():
    form = CreateAppForm()

    clone_from_app = None
    clone_from_app_id = request.args.get('clone_from', None)
    if clone_from_app_id:
        clone_from_app = get_ghost_app(clone_from_app_id)

    # Dynamic selections update
    if form.is_submitted() and form.region.data:
        form.instance_type.choices = get_aws_ec2_instance_types(form.region.data)
        form.vpc_id.choices = get_aws_vpc_ids(form.region.data)
        form.build_infos.source_ami.choices = get_aws_ami_ids(form.region.data)
        form.build_infos.subnet_id.choices = get_aws_subnet_ids(form.region.data, form.vpc_id.data)
        for subnet in form.environment_infos.subnet_ids:
            subnet.choices = get_aws_subnet_ids(form.region.data, form.vpc_id.data)
        for sg in  form.environment_infos.security_groups:
            sg.choices = get_aws_sg_ids(form.region.data, form.vpc_id.data)
    elif not form.is_submitted() and clone_from_app:
        form.instance_type.choices = get_aws_ec2_instance_types(clone_from_app['region'])
        form.vpc_id.choices = get_aws_vpc_ids(clone_from_app['region'])
        form.build_infos.source_ami.choices = get_aws_ami_ids(clone_from_app['region'])
        form.build_infos.subnet_id.choices = get_aws_subnet_ids(clone_from_app['region'], clone_from_app['vpc_id'])
        for subnet in form.environment_infos.subnet_ids:
            subnet.choices = get_aws_subnet_ids(clone_from_app['region'], clone_from_app['vpc_id'])
        for sg in  form.environment_infos.security_groups:
            sg.choices = get_aws_sg_ids(clone_from_app['region'], clone_from_app['vpc_id'])

    # Perform validation
    if form.validate_on_submit():
        app = {}
        form.map_to_app(app)

        message = create_ghost_app(app)

        return render_template('action_completed.html', message=message)

    if clone_from_app:
        form.map_from_app(clone_from_app)

    # Display default template in GET case
    return render_template('app_edit.html', form=form, edit=False)

@app.route('/web/apps/<app_id>', methods=['GET'])
def web_app_view(app_id):
    # Get App data
    app = get_ghost_app(app_id)

    return render_template('app_view.html', app=app)

@app.route('/web/apps/<app_id>/edit', methods=['GET', 'POST'])
def web_app_edit(app_id):
    form = EditAppForm()

    # Dynamic selections update
    if form.is_submitted() and form.region.data:
        form.instance_type.choices = get_aws_ec2_instance_types(form.region.data)
        form.vpc_id.choices = get_aws_vpc_ids(form.region.data)
        form.build_infos.source_ami.choices = get_aws_ami_ids(form.region.data)
        form.build_infos.subnet_id.choices = get_aws_subnet_ids(form.region.data, form.vpc_id.data)
        for subnet in form.environment_infos.subnet_ids:
            subnet.choices = get_aws_subnet_ids(form.region.data, form.vpc_id.data)
        for sg in  form.environment_infos.security_groups:
            sg.choices = get_aws_sg_ids(form.region.data, form.vpc_id.data)

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

        return render_template('action_completed.html', message=message)

    # Get App data on first access
    if not form.etag.data:
        app = get_ghost_app(app_id)
        form.map_from_app(app)

    # Remove alternative options from select fields that cannot be changed
    form.env.choices = [(form.env.data, form.env.data)]
    form.role.choices = [(form.role.data, form.role.data)]

    form.instance_type.choices = get_aws_ec2_instance_types(form.region.data)
    form.vpc_id.choices = get_aws_vpc_ids(form.region.data)
    form.build_infos.source_ami.choices = get_aws_ami_ids(form.region.data)
    form.build_infos.subnet_id.choices = get_aws_subnet_ids(form.region.data, form.vpc_id.data)
    for subnet in form.environment_infos.subnet_ids:
        subnet.choices = get_aws_subnet_ids(form.region.data, form.vpc_id.data)
    for sg in  form.environment_infos.security_groups:
        sg.choices = get_aws_sg_ids(form.region.data, form.vpc_id.data)    

    # Display default template in GET case
    return render_template('app_edit.html', form=form, edit=True)

@app.route('/web/apps/<app_id>/command', methods=['GET', 'POST'])
def web_app_command(app_id):
    form = CommandAppForm(app_id)

    # Perform validation
    if form.validate_on_submit():
        message = create_ghost_job(app_id, form, headers)

        return render_template('action_completed.html', message=message)

    # Display default template in GET case
    app = get_ghost_app(app_id)

    return render_template('app_command.html', form=form, app=app)

@app.route('/web/apps/<app_id>/command/module/<module>', methods=['GET', 'POST'])
def web_app_module_last_revision(app_id, module):
    last_revision = ''
    deployments = get_ghost_deployments('{"app_id": "%s", "module": "%s"}' % (app_id, module))
    if deployments and len(deployments) > 0:
        last_revision = deployments[0].get('revision', '')
    return last_revision

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
    jobs = get_ghost_jobs(query)

    return render_template('job_list.html', jobs=jobs,
                           deletable_job_statuses=DELETABLE_JOB_STATUSES,
                           cancellable_job_statuses=CANCELLABLE_JOB_STATUSES)

@app.route('/web/jobs/<job_id>', methods=['GET'])
def web_job_view(job_id):
    job = get_ghost_job(job_id)

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
    if job and job.get('status', '') in jobs.CANCELLABLE_JOB_STATUSES:
        form.etag.data = job['_etag']

    # Display default template in GET case
    return render_template('job_cancel.html', form=form, job=job)

@app.route('/web/deployments')
def web_deployments_list():
    query = request.args.get('where', None)
    deployments = get_ghost_deployments(query)

    return render_template('deployment_list.html', deployments=deployments)

@app.route('/web/deployments/<deployment_id>', methods=['GET'])
def web_deployments_view(deployment_id):
    # Get Deployment
    deployment = get_ghost_deployment(deployment_id)

    return render_template('deployment_view.html', deployment=deployment)

@app.route('/web/deployments/<deployment_id>/rollback', methods=['GET', 'POST'])
def web_deployment_rollback(deployment_id):
    # Get Deployment
    deployment = get_ghost_deployment(deployment_id)

    app = deployment['app_id']
    form = CommandAppForm(app['_id'])

    form.command.data = 'rollback'
    form.module_deploy_id.data = deployment_id

    # Perform validation
    if form.validate_on_submit():
        message = create_ghost_job(app['_id'], form, headers)

        return render_template('action_completed.html', message=message)

    # Display default template in GET case
    return render_template('app_command.html', form=form, app=app)
