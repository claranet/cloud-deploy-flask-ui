from flask_wtf import Form

from wtforms import FieldList, FormField, HiddenField, IntegerField, RadioField, SelectField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired as DataRequiredValidator
from wtforms.validators import NumberRange as NumberRangeValidator
from wtforms.validators import Optional as OptionalValidator
from wtforms.validators import Regexp as RegexpValidator

from base64 import b64encode
import traceback
import boto.vpc
import boto.ec2
import aws_data

from models.apps import apps_schema as ghost_app_schema
from models.jobs import jobs_schema as ghost_job_schema

from web_ui.ghost_client import get_ghost_app


# Helpers
def empty_fieldlist(fieldlist):
    while len(fieldlist) > 0:
        fieldlist.pop_entry()


def get_wtforms_selectfield_values(allowed_schema_values):
    """
    Returns a list of (value, label) tuples

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


def get_ghost_optional_volumes():
    return get_wtforms_selectfield_values(ghost_app_schema['environment_infos']['schema']['optional_volumes']['schema']['schema']['volume_type']['allowed'])


def get_aws_vpc_ids(region):
    vpcs = []
    try:
        c = boto.vpc.connect_to_region(region)
        vpcs = c.get_all_vpcs()
    except:
        traceback.print_exc()
    return [(vpc.id, vpc.id + ' (' + vpc.tags.get('Name', '') + ')') for vpc in vpcs]

def get_aws_sg_ids(region, vpc_id):
    sgs = []
    try:
        c = boto.ec2.connect_to_region(region)
        sgs = c.get_all_security_groups(filters={'vpc_id': vpc_id})
    except:
        traceback.print_exc()
    return [(sg.id, sg.id + ' (' + sg.name + ')') for sg in sgs]

def get_aws_ami_ids(region):
    amis = []
    try:
        c = boto.ec2.connect_to_region(region)
        amis = c.get_all_images(
            filters={
                'image_type': 'machine',
                'is-public': 'false'
            }
        )
    except:
        traceback.print_exc()
    return [(ami.id, ami.id + ' (' + ami.name + ')') for ami in amis]

def get_aws_subnet_ids(region, vpc_id):
    subs = []
    try:
        c = boto.vpc.connect_to_region(region)
        subs = c.get_all_subnets(filters={'vpc_id': vpc_id})
    except:
        traceback.print_exc()
    return [(sub.id, sub.id + ' (' + sub.tags.get('Name', '') + ')') for sub in subs]

def get_aws_ec2_regions():
    regions = []
    try:
        regions = sorted(boto.ec2.regions(), key=lambda region: region.name)
    except:
        traceback.print_exc()
    return [(region.name, '{name} ({endpoint})'.format(name=region.name, endpoint=region.endpoint)) for region in regions]


def get_aws_ec2_instance_types(region):
    # Uncomment when implemented on AWS side
    #types = []
    #try:
    #    c = boto.ec2.connect_to_region(region)
    #    types = c.get_all_instance_types()
    #except:
    #    traceback.print_exc()

    types = aws_data.instance_types[region]
    return [(instance_type.name,
         '{name} (cores:{cores}, memory:{memory}, disk:{disk})'.format(name=instance_type.name,
                                                                       cores=instance_type.cores,
                                                                       memory=instance_type.memory,
                                                                       disk=instance_type.disk)
         ) for instance_type in types]


class OptionalVolumeForm(Form):
    device_name = StringField('DeviceName', validators=[])
    volume_type = SelectField('VolumeType', validators=[], choices=get_ghost_optional_volumes())
    volume_size = IntegerField('VolumeSize', validators=[OptionalValidator()])
    iops = IntegerField('IOPS', validators=[OptionalValidator()])

    # Disable CSRF in optional_volume forms as they are subforms
    def __init__(self, csrf_enabled=False, *args, **kwargs):
        super(OptionalVolumeForm, self).__init__(csrf_enabled=csrf_enabled, *args, **kwargs)

    def map_from_app(self, optional_volume):
        self.device_name.data = optional_volume.get('device_name', '')
        self.volume_type.data = optional_volume.get('volume_type', '')
        self.volume_size.data = optional_volume.get('volume_size', '')
        self.iops.data = optional_volume.get('iops', '')

# Forms
class AutoscaleForm(Form):
    name = StringField('Name', validators=[])

    min = IntegerField('Min', validators=[
        OptionalValidator(),
        NumberRangeValidator(min=0)
    ])

    max = IntegerField('Max', validators=[
        OptionalValidator(),
        NumberRangeValidator(min=1)
    ])

    current = IntegerField('Initial', validators=[
        OptionalValidator()
    ])

    # Disable CSRF in autoscale forms as they are subforms
    def __init__(self, csrf_enabled=False, *args, **kwargs):
        super(AutoscaleForm, self).__init__(csrf_enabled=csrf_enabled, *args, **kwargs)

    def map_from_app(self, app):
        # Populate form with autoscale data if available
        autoscale = app.get('autoscale', {})
        self.min.data = autoscale.get('min', '')
        self.max.data = autoscale.get('max', '')
        self.current.data = autoscale.get('current', '')
        self.name.data = autoscale.get('name', '')

    def map_to_app(self, app):
        """
        Map autoscale data from form to app
        """
        app['autoscale'] = {}
        app['autoscale']['name'] = self.name.data
        if self.min.data:
            app['autoscale']['min'] = self.min.data
        if self.max.data:
            app['autoscale']['max'] = self.max.data
        if self.current.data:
            app['autoscale']['current'] = self.current.data


class BuildInfosForm(Form):
    ssh_username = StringField('SSH Username', validators=[
        DataRequiredValidator(),
        RegexpValidator(
            ghost_app_schema['build_infos']['schema']['ssh_username']['regex']
        )
    ], default='admin')

    source_ami = SelectField('Source AWS AMI', choices=[], validators=[
        DataRequiredValidator(),
        RegexpValidator(
            ghost_app_schema['build_infos']['schema']['source_ami']['regex']
        )
    ])

    subnet_id = SelectField('AWS Subnet', choices=[], validators=[
        DataRequiredValidator(),
        RegexpValidator(
            ghost_app_schema['build_infos']['schema']['subnet_id']['regex']
        )
    ])

    # Disable CSRF in build_infos forms as they are subforms
    def __init__(self, csrf_enabled=False, *args, **kwargs):
        super(BuildInfosForm, self).__init__(csrf_enabled=csrf_enabled, *args, **kwargs)

    def map_from_app(self, app):
        """
        Map build infos data from app to form
        """
        build_infos = app.get('build_infos', {})
        self.ssh_username.data = build_infos.get('ssh_username', '')
        self.source_ami.data = build_infos.get('source_ami', '')
        self.subnet_id.data = build_infos.get('subnet_id', '')

    def map_to_app(self, app):
        """
        Map build infos data from form to app
        """
        app['build_infos'] = {}
        app['build_infos']['ssh_username'] = self.ssh_username.data
        app['build_infos']['source_ami'] = self.source_ami.data
        app['build_infos']['subnet_id'] = self.subnet_id.data

class EnvironmentInfosForm(Form):
    security_groups = FieldList(SelectField('Security Group', choices=[], validators=[
        OptionalValidator(),
        RegexpValidator(
            ghost_app_schema['environment_infos']['schema']['security_groups']['schema']['regex']
        )
    ]), min_entries=1)

    subnet_ids = FieldList(SelectField('Subnet ID', choices=[], validators=[
        OptionalValidator(),
        RegexpValidator(
            ghost_app_schema['environment_infos']['schema']['subnet_ids']['schema']['regex']
        )
    ]), min_entries=1)

    instance_profile = StringField('Instance Profile', validators=[
        OptionalValidator(),
        RegexpValidator(
            ghost_app_schema['environment_infos']['schema']['instance_profile']['regex']
        )
    ])

    key_name = StringField('Key Name', validators=[
        OptionalValidator(),
        RegexpValidator(
            ghost_app_schema['environment_infos']['schema']['key_name']['regex']
        )
    ])

    root_block_device_size = IntegerField('Size (GiB)', validators=[
        OptionalValidator(),
        NumberRangeValidator(min=0)
    ]);

    root_block_device_name = StringField('Name', validators=[
        OptionalValidator(),
        RegexpValidator(
            ghost_app_schema['environment_infos']['schema']['root_block_device']['schema']['name']['regex']
        )
    ])

    optional_volumes = FieldList(FormField(OptionalVolumeForm, validators=[]), min_entries=1)


    # Disable CSRF in environment_infos forms as they are subforms
    def __init__(self, csrf_enabled=False, *args, **kwargs):
        super(EnvironmentInfosForm, self).__init__(csrf_enabled=csrf_enabled, *args, **kwargs)

    def map_from_app(self, app):
        environment_infos = app.get('environment_infos', {})

        # Populate form with security groups data if available
        if 'security_groups' in environment_infos and len(environment_infos['security_groups']) > 0:
            empty_fieldlist(self.security_groups)
            for security_group in environment_infos.get('security_groups', []):
                self.security_groups.append_entry()
                form_security_group = self.security_groups.entries[-1]
                form_security_group.data = security_group

        # Populate form with subnet data if available
        if 'subnet_ids' in environment_infos and len(environment_infos['subnet_ids']) > 0:
            empty_fieldlist(self.subnet_ids)
            for subnet_id in environment_infos.get('subnet_ids', []):
                self.subnet_ids.append_entry()
                form_subnet_id = self.subnet_ids.entries[-1]
                form_subnet_id.data = subnet_id

        self.instance_profile.data = environment_infos.get('instance_profile', '')
        self.key_name.data = environment_infos.get('key_name', '')

        self.root_block_device_size.data = environment_infos.get('root_block_device', {}).get('size', '')
        self.root_block_device_name.data = environment_infos.get('root_block_device', {}).get('name', '')

        if 'optional_volumes' in environment_infos and len(environment_infos['optional_volumes']) > 0:
            empty_fieldlist(self.optional_volumes)
            for opt_vol in environment_infos.get('optional_volumes', []):
                self.optional_volumes.append_entry()
                form_opt_vol = self.optional_volumes.entries[-1].form
                form_opt_vol.map_from_app(opt_vol)

class ResourceForm(Form):
    # Disable CSRF in resource forms as they are subforms
    def __init__(self, csrf_enabled=False, *args, **kwargs):
        super(ResourceForm, self).__init__(csrf_enabled=csrf_enabled, *args, **kwargs)

    def map_from_app(self, feature):
        # TODO: implement resource form
        pass

class FeatureForm(Form):
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

    # Disable CSRF in feature forms as they are subforms
    def __init__(self, csrf_enabled=False, *args, **kwargs):
        super(FeatureForm, self).__init__(csrf_enabled=csrf_enabled, *args, **kwargs)

    def map_from_app(self, feature):
        self.feature_name.data = feature.get('name', '')
        self.feature_version.data = feature.get('version', '')


class ModuleForm(Form):
    module_name = StringField('Name', validators=[
        DataRequiredValidator(),
        RegexpValidator(
            ghost_app_schema['modules']['schema']['schema']['name']['regex']
        )
    ])
    module_git_repo = StringField('Git Repository', validators=[DataRequiredValidator()])
    module_path = StringField('Path', validators=[
        DataRequiredValidator(),
        RegexpValidator(
            ghost_app_schema['modules']['schema']['schema']['path']['regex']
        )
    ])
    module_scope = SelectField('Scope', validators=[DataRequiredValidator()], choices=get_ghost_mod_scopes())
    module_build_pack = TextAreaField('Build Pack', validators=[])
    module_pre_deploy = TextAreaField('Pre Deploy', validators=[])
    module_post_deploy = TextAreaField('Post Deploy', validators=[])

    # Disable CSRF in module forms as they are subforms
    def __init__(self, csrf_enabled=False, *args, **kwargs):
        super(ModuleForm, self).__init__(csrf_enabled=csrf_enabled, *args, **kwargs)

    def map_from_app(self, module):
        self.module_name.data = module.get('name', '')
        self.module_git_repo.data = module.get('git_repo', '')
        self.module_path.data = module.get('path', '')
        self.module_scope.data = module.get('scope', '')
        if 'build_pack' in module:
            self.module_build_pack.data = module['build_pack']
        if 'pre_deploy' in module:
            self.module_pre_deploy.data = module['pre_deploy']
        if 'post_deploy' in module:
            self.module_post_deploy.data = module['post_deploy']


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
    log_notifications = FieldList(StringField('email', validators=[
        OptionalValidator(),
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
    # resources = FieldList(FormField(ResourceForm), min_entries=1)

    # Environment properties
    environment_infos = FormField(EnvironmentInfosForm)

    # AWS properties
    region = SelectField('AWS Region', validators=[DataRequiredValidator()], choices=[])

    instance_type = SelectField('AWS Instance Type', validators=[DataRequiredValidator()], choices=[])

    vpc_id = SelectField('AWS VPC', choices=[], validators=[
        DataRequiredValidator(),
        RegexpValidator(
            ghost_app_schema['vpc_id']['regex']
        )
    ])

    # Features
    features = FieldList(FormField(FeatureForm), min_entries=1)

    # Modules
    modules = FieldList(FormField(ModuleForm), min_entries=1)


    def map_to_app(self, app):
        """
        Map app data from form to app
        """
        if self.name:
            app['name'] = self.name.data
        if self.env:
            app['env'] = self.env.data
        if self.role:
            app['role'] = self.role.data
        app['region'] = self.region.data
        app['instance_type'] = self.instance_type.data
        app['vpc_id'] = self.vpc_id.data

        self.map_to_app_log_notifications(app)
        self.map_to_app_autoscale(app)
        self.map_to_app_build_infos(app)
        self.map_to_app_resources(app)
        self.map_to_app_environment_infos(app)
        self.map_to_app_features(app)
        self.map_to_app_modules(app)

    def map_to_app_log_notifications(self, app):
        """
        Maps log notifications data from form to app

        >>> from web_ui.tests import create_test_app_context; create_test_app_context()

        >>> form = BaseAppForm()
        >>> app = {}
        >>> form.map_to_app_log_notifications(app)
        >>> app
        {'log_notifications': []}

        >>> form.log_notifications[0].data = "test@test.fr"
        >>> form.map_to_app_log_notifications(app)
        >>> app
        {'log_notifications': ['test@test.fr']}
        """
        app['log_notifications'] = []
        for form_log_notification in self.log_notifications:
            if form_log_notification.data:
                log_notification = form_log_notification.data
                app['log_notifications'].append(log_notification)

    def map_to_app_autoscale(self, app):
        """
        Map autoscale data from form to app
        """
        self.autoscale.form.map_to_app(app)

    def map_to_app_build_infos(self, app):
        """
        Map build infos data from form to app
        """
        self.build_infos.form.map_to_app(app)

    def map_to_app_resources(self, app):
        """
        Map resources data from form to app
        """
        # TODO: Extract resources app data
        pass

    def map_to_app_environment_infos(self, app):
        """
        Map environment infos data from form to app
        """
        app['environment_infos'] = {}
        app['environment_infos']['security_groups'] = []
        for form_security_group in self.environment_infos.form.security_groups:
            if form_security_group.data:
                security_group = form_security_group.data
                app['environment_infos']['security_groups'].append(security_group)

        app['environment_infos']['subnet_ids'] = []
        for form_subnet_id in self.environment_infos.form.subnet_ids:
            if form_subnet_id.data:
                subnet_id = form_subnet_id.data
                app['environment_infos']['subnet_ids'].append(subnet_id)

        app['environment_infos']['instance_profile'] = self.environment_infos.form.instance_profile.data
        app['environment_infos']['key_name'] = self.environment_infos.form.key_name.data

        app['environment_infos']['root_block_device'] = {}
        if self.environment_infos.form.root_block_device_size.data:
            app['environment_infos']['root_block_device']['size'] = self.environment_infos.form.root_block_device_size.data
        if self.environment_infos.form.root_block_device_name.data:
            app['environment_infos']['root_block_device']['name'] = self.environment_infos.form.root_block_device_name.data

        app['environment_infos']['optional_volumes'] = []
        for form_opt_vol in self.environment_infos.form.optional_volumes:
            opt_vol = {}
            if form_opt_vol.device_name.data:
                opt_vol['device_name'] = form_opt_vol.device_name.data
                if form_opt_vol.volume_type.data:
                    opt_vol['volume_type'] = form_opt_vol.volume_type.data
                if form_opt_vol.volume_size.data:
                    opt_vol['volume_size'] = form_opt_vol.volume_size.data
                if form_opt_vol.iops.data:
                    opt_vol['iops'] = form_opt_vol.iops.data
                app['environment_infos']['optional_volumes'].append(opt_vol)


    def map_to_app_features(self, app):
        """
        Map features data from form to app
        """
        app['features'] = []
        for form_feature in self.features:
            feature = {}
            if form_feature.feature_name.data:
                feature['name'] = form_feature.feature_name.data
                if form_feature.feature_version.data:
                    feature['version'] = form_feature.feature_version.data
            if feature:
                app['features'].append(feature)


    def map_to_app_modules(self, app):
        """
        Map modules data from form to app
        """
        app['modules'] = []
        for form_module in self.modules:
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

    def map_from_app(self, app):
        """
        Map app data from app to form
        """

        # Populate form with app data
        self.name.data = app.get('name', '')
        self.env.data = app.get('env', '')
        self.role.data = app.get('role', '')
        self.region.data = app.get('region', '')
        self.instance_type.data = app.get('instance_type', '')
        self.vpc_id.data = app.get('vpc_id', '')

        self.map_from_app_notifications(app)
        self.map_from_app_autoscale(app)
        self.map_from_app_build_infos(app)
        self.map_from_app_environment_infos(app)
        self.map_from_app_features(app)
        self.map_from_app_modules(app)

        # TODO: handle resources app data

    def map_from_app_autoscale(self, app):
        """
        Map autoscale data from app to form
        """
        return self.autoscale.form.map_from_app(app)

    def map_from_app_build_infos(self, app):
        """
        Map build infos data from app to form
        """
        return self.build_infos.form.map_from_app(app)

    def map_from_app_environment_infos(self, app):
        """
        Map environment infos data from app to form
        """
        return self.environment_infos.form.map_from_app(app)

    def map_from_app_features(self, app):
        """
        Map features data from app to form
        """
        if 'features' in app and len(app['features']) > 0:
            empty_fieldlist(self.features)
            for feature in app.get('features', []):
                self.features.append_entry()
                form_feature = self.features.entries[-1].form
                form_feature.map_from_app(feature)

    def map_from_app_modules(self, app):
        """
        Map modules data from app to form
        """
        if 'modules' in app and len(app['modules']) > 0:
            empty_fieldlist(self.modules)
            for module in app.get('modules', []):
                self.modules.append_entry()
                form_module = self.modules.entries[-1].form
                form_module.map_from_app(module)

    def map_from_app_notifications(self, app):
        """
        Map log_notifications data from app to form
        """
        if 'log_notifications' in app and len(app['log_notifications']) > 0:
            empty_fieldlist(self.log_notifications)
            for log_notification in app.get('log_notifications', []):
                self.log_notifications.append_entry()
                form_log_notification = self.log_notifications.entries[-1]
                form_log_notification.data = log_notification


class CreateAppForm(BaseAppForm):
    submit = SubmitField('Create Application')

    def __init__(self, *args, **kwargs):
        super(CreateAppForm, self).__init__(*args, **kwargs)

        # Refresh AWS lists
        self.region.choices = [('', 'Please select region')] + get_aws_ec2_regions()
        self.instance_type.choices = [('', 'Please select region first')]
        self.vpc_id.choices = [('', 'Please select region first')]
        self.environment_infos.security_groups[0].choices = [('', 'Please select region first')]
        self.build_infos.source_ami.choices = [('', 'Please select region first')]
        self.build_infos.subnet_id.choices = [('', 'Please select VPC first')]
        self.environment_infos.subnet_ids[0].choices = [('', 'Please select VPC first')]


class EditAppForm(BaseAppForm):
    etag = HiddenField(validators=[DataRequiredValidator()])

    submit = SubmitField('Update Application')

    def __init__(self, *args, **kwargs):
        super(EditAppForm, self).__init__(*args, **kwargs)

        # Refresh AWS lists
        self.region.choices = get_aws_ec2_regions()


    def map_from_app(self, app):
        """
        Map app data from app to form
        """
        # Store app etag in form
        self.etag.data = app.get('_etag', '')

        super(EditAppForm, self).map_from_app(app)


class CommandAppForm(Form):
    command = SelectField('Command', validators=[DataRequiredValidator()], choices=get_ghost_job_commands())
    module_name = SelectField('Module name', validators=[])
    module_rev = StringField('Module revision', validators=[])
    module_deploy_id = StringField('Deploy ID', validators=[])
    instance_type = SelectField('Instance Type', validators=[], choices=[])

    submit = SubmitField('Run Application Command')

    def __init__(self, app_id, *args, **kwargs):
        super(CommandAppForm, self).__init__(*args, **kwargs)

        # Get the Ghost application
        app = get_ghost_app(app_id)

        # Get the modules of the Ghost application
        self.module_name.choices = [('', '')] + [(module['name'], module['name']) for module in app['modules']]

        # Get the instance types in the Ghost application's region
        self.instance_type.choices = get_aws_ec2_instance_types(app["region"])

        # Use the instance type of the Ghost application as default
        self.instance_type.data = app.get('instance_type', '')

class DeleteAppForm(Form):
    etag = HiddenField(validators=[DataRequiredValidator()])
    confirmation = RadioField('Are you sure?', validators=[DataRequiredValidator()], choices=[('yes', 'Yes'), ('no', 'No')])

    submit = SubmitField('Delete Application')

class DeleteJobForm(Form):
    etag = HiddenField(validators=[DataRequiredValidator()])
    confirmation = RadioField('Are you sure?', validators=[DataRequiredValidator()], choices=[('yes', 'Yes'), ('no', 'No')])

    submit = SubmitField('Delete Job')

class CancelJobForm(Form):
    etag = HiddenField(validators=[DataRequiredValidator()])
    confirmation = RadioField('Are you sure?', validators=[DataRequiredValidator()], choices=[('yes', 'Yes'), ('no', 'No')])

    submit = SubmitField('Cancel Job')
