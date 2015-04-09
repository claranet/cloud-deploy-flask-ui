from flask_wtf import Form

from wtforms import FieldList, FormField, HiddenField, IntegerField, RadioField, SelectField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired as DataRequiredValidator
from wtforms.validators import Regexp as RegexpValidator
from wtforms.validators import NumberRange as NumberRangeValidator

import aws_data

from base64 import b64encode, b64decode
import traceback
import boto.vpc

from apps import apps_schema as ghost_app_schema
from jobs import jobs_schema as ghost_job_schema


def get_wtforms_selectfield_values(allowed_schema_values):
    """
    >>> get_wtforms_selectfield_values([])
    []
    >>> get_wtforms_selectfield_values(['value'])
    [('value', 'value')]
    >>> get_wtforms_selectfield_values(['value1', 'value2'])
    [('value1', 'value1'), ('value2', 'value2')]
    """
    return [(value, value) for value in allowed_schema_values]


def get_ghost_app_envs():
    return get_wtforms_selectfield_values(ghost_app_schema['env']['allowed'])


def get_ghost_app_roles():
    return get_wtforms_selectfield_values(ghost_app_schema['role']['allowed'])


def get_ghost_job_commands():
    return get_wtforms_selectfield_values(ghost_job_schema['command']['allowed'])


def get_ghost_mod_scopes():
    return get_wtforms_selectfield_values(ghost_app_schema['modules']['schema']['schema']['scope']['allowed'])


def get_aws_vpc_ids():
    try:
        c = boto.vpc.connect_to_region('eu-west-1')
        vpcs = c.get_all_vpcs()
        vpc_ids = []
        for vpc in vpcs:
            vpc_ids.append(vpc.id)
        return [(value, value) for value in vpc_ids]
    except:
        traceback.print_exc()
        return [('vpc-0', 'vpc-0 (dummy)')]


def get_aws_regions():
    return [
        ('eu-west-1', 'eu-west-1 (Ireland)'),
        ('us-east-1', 'us-east-1 (North Virginia)')
    ]


def get_aws_instance_types():
    return [(value, value) for value in aws_data.instance_type]


# Mappings
def map_form_to_app_log_notifications(form, app):
    """
    Extract log_notifications data
    """
    app['log_notifications'] = []
    for form_log_notification in form.log_notifications:
        if form_log_notification.data:
            log_notification = form_log_notification.data
            app['log_notifications'].append(log_notification)


def map_form_to_app_autoscale(form, app):
    """
    Extract autoscale data
    """
    app['autoscale'] = {}
    app['autoscale']['min'] = form.autoscale.form.min.data
    app['autoscale']['max'] = form.autoscale.form.max.data
    app['autoscale']['name'] = form.autoscale.form.name.data


def map_form_to_app_build_infos(form, app):
    """
    Extract build_infos data
    """
    app['build_infos'] = {}
    app['build_infos']['ssh_username'] = form.build_infos.form.ssh_username.data
    app['build_infos']['source_ami'] = form.build_infos.form.source_ami.data
    app['build_infos']['ami_name'] = form.build_infos.form.ami_name.data
    app['build_infos']['subnet_id'] = form.build_infos.form.subnet_id.data


def map_form_to_app_resources(form, app):
    """
    Extract resources data
    """
    #TODO: Extract resources app data


def map_form_to_app_environment_infos(form, app):
    """
    Extract environment_infos data
    """
    app['environment_infos'] = {}
    app['environment_infos']['security_groups'] = []
    for form_security_group in form.environment_infos.form.security_groups:
        if form_security_group.data:
            security_group = form_security_group.data
            app['environment_infos']['security_groups'].append(security_group)
    
    app['environment_infos']['subnet_ids'] = []
    for form_subnet_id in form.environment_infos.form.subnet_ids:
        if form_subnet_id.data:
            subnet_id = form_subnet_id.data
            app['environment_infos']['subnet_ids'].append(subnet_id)
    
    app['environment_infos']['instance_profile'] = form.environment_infos.form.instance_profile.data
    app['environment_infos']['key_name'] = form.environment_infos.form.key_name.data


def map_form_to_app_features(form, app):
    """
    Extract features data
    """
    app['features'] = []
    for form_feature in form.features:
        feature = {}
        if form_feature.feature_name.data:
            feature['name'] = form_feature.feature_name.data
            if form_feature.feature_version.data:
                feature['version'] = form_feature.feature_version.data
        if feature:
            app['features'].append(feature)


def map_form_to_app_modules(form, app):
    """
    Extract modules data
    """
    app['modules'] = []
    for form_module in form.modules:
        module = {}
        module['name'] = form_module.module_name.data
        module['git_repo'] = form_module.module_git_repo.data
        module['path'] = form_module.module_path.data
        module['scope'] = form_module.module_scope.data
        if form_module.module_build_pack.data:
            module['build_pack'] = b64encode(form_module.module_build_pack.data.replace('\r\n', '\n'))
        if form_module.module_pre_deploy.data:
            module['pre_deploy'] = b64encode(form_module.module_pre_deploy.data.replace('\r\n', '\n'))
        if form_module.module_post_deploy.data:
            module['post_deploy'] = b64encode(form_module.module_post_deploy.data.replace('\r\n', '\n'))
        app['modules'].append(module)


def map_form_to_app(form, app):
    if form.name:
        app['name'] = form.name.data
    app['env'] = form.env.data
    app['role'] = form.role.data
    app['region'] = form.region.data
    app['instance_type'] = form.instance_type.data
    app['vpc_id'] = form.vpc_id.data

    map_form_to_app_log_notifications(form, app)
    map_form_to_app_autoscale(form, app)
    map_form_to_app_build_infos(form, app)
    map_form_to_app_resources(form, app)
    map_form_to_app_environment_infos(form, app)
    map_form_to_app_features(form, app)
    map_form_to_app_modules(form, app)


def empty_fieldlist(fieldlist):
    while len(fieldlist) > 0:
        fieldlist.pop_entry()


def map_app_to_form_log_notifications(app, form):
# Populate form with log_notifications data if available
    if 'log_notifications' in app and len(app['log_notifications']) > 0: # Remove default entry
        empty_fieldlist(form.log_notifications)
        for log_notification in app.get('log_notifications', []):
            form.log_notifications.append_entry()
            form_log_notification = form.log_notifications.entries[-1]
            form_log_notification.data = log_notification


def map_app_to_form_autoscale(app, form):
    # Populate form with autoscale data if available
    autoscale = app.get('autoscale', {})
    form.autoscale.form.min.data = autoscale.get('min', 0)
    form.autoscale.form.max.data = autoscale.get('max', 1)
    form.autoscale.form.name.data = autoscale.get('name', '')


def map_app_to_form_build_infos(app, form):
    # Populate form with build_infos data if available
    build_infos = app.get('build_infos', {})
    form.build_infos.form.ssh_username.data = build_infos.get('ssh_username', '')
    form.build_infos.form.source_ami.data = build_infos.get('source_ami', '')
    form.build_infos.form.ami_name.data = build_infos.get('ami_name', '')
    form.build_infos.form.subnet_id.data = build_infos.get('subnet_id', '')


def map_app_to_form_environment_infos(app, form):
    # Populate form with environment_infos data if available
    environment_infos = app.get('environment_infos', {})
    if 'security_groups' in environment_infos and len(environment_infos['security_groups']) > 0: # Remove default entry
        empty_fieldlist(form.environment_infos.form.security_groups)
        for security_group in environment_infos.get('security_groups', []):
            form.environment_infos.form.security_groups.append_entry()
            form_security_group = form.environment_infos.form.security_groups.entries[-1]
            form_security_group.data = security_group
    
    if 'subnet_ids' in environment_infos and len(environment_infos['subnet_ids']) > 0: # Remove default entry
        empty_fieldlist(form.environment_infos.form.subnet_ids)
        for subnet_id in environment_infos.get('subnet_ids', []):
            form.environment_infos.form.subnet_ids.append_entry()
            form_subnet_id = form.environment_infos.form.subnet_ids.entries[-1]
            form_subnet_id.data = subnet_id
    
    form.environment_infos.form.instance_profile.data = environment_infos.get('instance_profile', '')
    form.environment_infos.form.key_name.data = environment_infos.get('key_name', '')


def map_app_to_form_resources(app, form):
    """
    Map resources app data to form 
    """
    # TODO: handle resources app data


def map_app_to_form_features(app, form):
# Populate form with features data if available
    if 'features' in app and len(app['features']) > 0: # Remove default entry
        empty_fieldlist(form.features)
        for feature in app.get('features', []):
            form.features.append_entry()
            form_feature = form.features.entries[-1].form
            form_feature.feature_name.data = feature.get('name', '')
            form_feature.feature_version.data = feature.get('version', '')


def map_app_to_form_modules(app, form):
# Populate form with modules data if available
    if 'modules' in app and len(app['modules']) > 0: # Remove default entry
        form.modules.pop_entry()
        for module in app.get('modules', []):
            form.modules.append_entry()
            form_module = form.modules.entries[-1].form
            form_module.module_name.data = module.get('name', '')
            form_module.module_git_repo.data = module.get('git_repo', '')
            form_module.module_path.data = module.get('path', '')
            form_module.module_scope.data = module.get('scope', '')
            if 'build_pack' in module:
                form_module.module_build_pack.data = b64decode(module['build_pack'])
            if 'pre_deploy' in module:
                form_module.module_pre_deploy.data = b64decode(module['pre_deploy'])
            if 'post_deploy' in module:
                form_module.module_post_deploy.data = b64decode(module['post_deploy'])

def map_app_to_form(app, form):
    # Store App etag in form
    form.etag.data = app['_etag']

    # Populate form with app data
    form.name.data = app.get('name', '')
    form.env.data = app.get('env', '')
    form.role.data = app.get('role', '')
    form.region.data = app.get('region', '')
    form.instance_type.data = app.get('instance_type', '')
    form.vpc_id.data = app.get('vpc_id', '')

    map_app_to_form_log_notifications(app, form)
    map_app_to_form_autoscale(app, form)
    map_app_to_form_build_infos(app, form)
    map_app_to_form_environment_infos(app, form)
    map_app_to_form_resources(app, form)
    map_app_to_form_features(app, form)
    map_app_to_form_modules(app, form)


# Forms
class AutoscaleForm(Form):
    # Disable CSRF in autoscale forms as they are subforms
    def __init__(self, csrf_enabled=False, *args, **kwargs):
        super(AutoscaleForm, self).__init__(csrf_enabled=csrf_enabled, *args, **kwargs)

    name = StringField('Name', validators=[])
    min = IntegerField('Min', validators=[NumberRangeValidator(min=0)])
    max = IntegerField('Max', validators=[NumberRangeValidator(min=1)])
    current = IntegerField('Current', validators=[])


class BuildInfosForm(Form):
    # Disable CSRF in build_infos forms as they are subforms
    def __init__(self, csrf_enabled=False, *args, **kwargs):
        super(BuildInfosForm, self).__init__(csrf_enabled=csrf_enabled, *args, **kwargs)

    ssh_username = StringField('SSH Username', validators=[DataRequiredValidator()])
    source_ami = StringField('Source AWS AMI', validators=[
        DataRequiredValidator(),
        RegexpValidator(
            ghost_app_schema['build_infos']['schema']['source_ami']['regex']
        )
    ])
    ami_name = StringField('AWS AMI Name', validators=[DataRequiredValidator()])
    subnet_id = StringField('AWS Subnet', validators=[
        DataRequiredValidator(),
        RegexpValidator(
            ghost_app_schema['build_infos']['schema']['subnet_id']['regex']
        )
    ])


class EnvironmentInfosForm(Form):
    # Disable CSRF in environment_infos forms as they are subforms
    def __init__(self, csrf_enabled=False, *args, **kwargs):
        super(EnvironmentInfosForm, self).__init__(csrf_enabled=csrf_enabled, *args, **kwargs)

    security_groups = FieldList(StringField('Security Group', validators=[
        RegexpValidator(
            ghost_app_schema['environment_infos']['schema']['security_groups']['schema']['regex']
        )
    ]), min_entries=1)
    subnet_ids = FieldList(StringField('Subnet ID', validators=[
        RegexpValidator(
            ghost_app_schema['environment_infos']['schema']['subnet_ids']['schema']['regex']
        )
    ]), min_entries=1)
    instance_profile = StringField('Instance Profile', validators=[])
    key_name = StringField('Key Name', validators=[])


class ResourceForm(Form):
    # Disable CSRF in resource forms as they are subforms
    def __init__(self, csrf_enabled=False, *args, **kwargs):
        super(ResourceForm, self).__init__(csrf_enabled=csrf_enabled, *args, **kwargs)

    # TODO: implement resource form


class FeatureForm(Form):
    # Disable CSRF in feature forms as they are subforms
    def __init__(self, csrf_enabled=False, *args, **kwargs):
        super(FeatureForm, self).__init__(csrf_enabled=csrf_enabled, *args, **kwargs)

    feature_name = StringField('Name', validators=[
        RegexpValidator(
            ghost_app_schema['features']['schema']['schema']['name']['regex']
        )
    ])
    feature_version = StringField('Version', validators=[
        RegexpValidator(
            ghost_app_schema['features']['schema']['schema']['version']['regex']
        )
    ])


class ModuleForm(Form):
    # Disable CSRF in module forms as they are subforms
    def __init__(self, csrf_enabled=False, *args, **kwargs):
        super(ModuleForm, self).__init__(csrf_enabled=csrf_enabled, *args, **kwargs)

    module_name = StringField('Name', validators=[DataRequiredValidator()])
    module_git_repo = StringField('Git Repository', validators=[DataRequiredValidator()])
    module_path = StringField('Path', validators=[DataRequiredValidator()])
    module_scope = SelectField('Scope', validators=[DataRequiredValidator()], choices=get_ghost_mod_scopes())
    module_build_pack = TextAreaField('Build Pack', validators=[])
    module_pre_deploy = TextAreaField('Pre Deploy', validators=[])
    module_post_deploy = TextAreaField('Post Deploy', validators=[])


class BaseAppForm(Form):
    # App properties
    name = StringField('Name', validators=[
        DataRequiredValidator(), 
        RegexpValidator(
            ghost_app_schema['name']['regex']
        )
    ])
    env = SelectField('Environment', validators=[DataRequiredValidator()], choices=get_ghost_app_envs())
    role = SelectField('Role', validators=[DataRequiredValidator()], choices=get_ghost_app_roles())

    # Notification properties
    log_notifications = FieldList(StringField('', validators=[
        RegexpValidator(
            ghost_app_schema['log_notifications']['schema']['regex']
        )
    ]), min_entries=1)

    # Autoscale properties
    autoscale = FormField(AutoscaleForm)

    # Build properties
    build_infos = FormField(BuildInfosForm)

    # Resources properties
    # TODO: implement resources
    #resources = FieldList(FormField(ResourceForm), min_entries=1)

    # Environment properties
    environment_infos = FormField(EnvironmentInfosForm)

    # AWS properties
    region = SelectField('AWS Region', validators=[DataRequiredValidator()], choices=get_aws_regions())
    instance_type = SelectField('AWS Instance Type', validators=[DataRequiredValidator()], choices=get_aws_instance_types())
    vpc_id = SelectField('AWS VPC', choices=get_aws_vpc_ids(), validators=[
        DataRequiredValidator(), 
        RegexpValidator(
            ghost_app_schema['vpc_id']['regex']
        )
    ])

    # Features
    features = FieldList(FormField(FeatureForm), min_entries=1)

    # Modules
    modules = FieldList(FormField(ModuleForm), min_entries=1)


class CreateAppForm(BaseAppForm):
    submit = SubmitField('Create Application')


class EditAppForm(BaseAppForm):
    etag = HiddenField(validators=[DataRequiredValidator()])

    submit = SubmitField('Update Application')


class CommandAppForm(Form):
    command = SelectField('Command', validators=[DataRequiredValidator()], choices=get_ghost_job_commands())
    module_name = SelectField('Module', validators=[DataRequiredValidator()])

    submit = SubmitField('Run Application Command')


class DeleteAppForm(Form):
    etag = HiddenField(validators=[DataRequiredValidator()])
    confirmation = RadioField('Are you sure?', validators=[DataRequiredValidator()], choices=[('yes', 'Yes'), ('no', 'No')])

    submit = SubmitField('Delete Application')