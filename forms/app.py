from flask_wtf import FlaskForm

from web_ui.forms.form_helper import empty_fieldlist
from web_ui.forms.form_helper import get_wtforms_selectfield_values

from web_ui.forms.form_helper import get_default_name_tag
from web_ui.forms.form_helper import get_ghost_app_envs
from web_ui.forms.form_helper import get_ghost_app_roles
from web_ui.forms.form_helper import get_ghost_optional_volumes
from web_ui.forms.form_helper import get_ghost_mod_scopes

from web_ui.forms.form_aws_helper import get_aws_connection_data
from web_ui.forms.form_aws_helper import get_aws_ec2_regions

from wtforms import FieldList, FormField, HiddenField, IntegerField, RadioField, StringField, SubmitField, TextAreaField, BooleanField
from web_ui.forms.form_wtf_helper import BetterSelectField, BetterSelectFieldNonValidating
from wtforms.validators import DataRequired as DataRequiredValidator
from wtforms.validators import NumberRange as NumberRangeValidator
from wtforms.validators import Optional as OptionalValidator
from wtforms.validators import Regexp as RegexpValidator
from wtforms.validators import Length as LengthValidator
from wtforms.validators import NoneOf as NoneOfValidator

from models.apps import apps_schema as ghost_app_schema

from ghost_tools import get_available_provisioners_from_config
from ghost_tools import b64encode_utf8

from settings import DEFAULT_PROVIDER
from libs.provisioner import DEFAULT_PROVISIONER_TYPE
from libs.blue_green import get_blue_green_from_app


class OptionalVolumeForm(FlaskForm):
    device_name = StringField('Device Name', description='Should match /dev/sd[a-z] or /dev/xvd[b-c][a-z]',
                              validators=[])
    volume_type = BetterSelectField('Volume Type',
                                    description='More details on <a target="_blank" href="http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/EBSVolumeTypes.html">AWS Documentation</a>',
                                    validators=[], choices=get_ghost_optional_volumes())
    volume_size = IntegerField('Volume Size', description='In GiB', validators=[OptionalValidator()])
    iops = IntegerField('IOPS', description='For information, 1TiB volume size is 3000 IOPS in GP2 type',
                        validators=[OptionalValidator()])

    # Disable CSRF in optional_volume forms as they are subforms
    def __init__(self, csrf_enabled=False, *args, **kwargs):
        super(OptionalVolumeForm, self).__init__(meta={'csrf': False}, *args, **kwargs)

    def map_from_app(self, optional_volume):
        self.device_name.data = optional_volume.get('device_name', '')
        self.volume_type.data = optional_volume.get('volume_type', '')
        self.volume_size.data = optional_volume.get('volume_size', '')
        self.iops.data = optional_volume.get('iops', '')


class InstanceTagForm(FlaskForm):
    tag_name = StringField('Tag Name',
                           description='Enter a Tag name(case sensitive) except these reserved names "app_id/env/app/role/color"',
                           validators=[LengthValidator(min=1, max=127), DataRequiredValidator(),
                                       NoneOfValidator(['app_id', 'env', 'app', 'role', 'color'])])
    tag_value = StringField('Tag Value', description='Enter the Tag value(case sensitive) associate with the Tag Name.\
                            You can use GHOST_APP variables to refer to its content(ex: GHOST_APP_ROLE will be replaced by the role defined in this application)',
                            validators=[LengthValidator(min=1, max=255), DataRequiredValidator()])

    def __init__(self, csrf_enabled=False, *args, **kwargs):
        super(InstanceTagForm, self).__init__(meta={'csrf': False}, *args, **kwargs)

    def map_from_app(self, instance_tag):
        self.tag_name.data = instance_tag.get('tag_name', '')
        self.tag_value.data = instance_tag.get('tag_value', '')


# Forms
class AutoscaleForm(FlaskForm):
    as_name = BetterSelectField('Name', choices=[], validators=[])
    enable_metrics = BooleanField('Enable Auto Scaling Metrics', validators=[])

    min = IntegerField('Min', description='The minimum size of the Auto Scaling group', validators=[
        OptionalValidator(),
        NumberRangeValidator(min=0)
    ])

    max = IntegerField('Max', description='The maximum size of the Auto Scaling group', validators=[
        OptionalValidator(),
        NumberRangeValidator(min=0)
    ])

    # Disable CSRF in autoscale forms as they are subforms
    def __init__(self, csrf_enabled=False, *args, **kwargs):
        super(AutoscaleForm, self).__init__(meta={'csrf': False}, *args, **kwargs)

    def map_from_app(self, app):
        # Populate form with autoscale data if available
        autoscale = app.get('autoscale', {})
        self.min.data = autoscale.get('min', '')
        self.max.data = autoscale.get('max', '')
        self.as_name.data = autoscale.get('name', '')
        self.enable_metrics.data = autoscale.get('enable_metrics', True)

    def map_to_app(self, app):
        """
        Map autoscale data from form to app
        """
        app['autoscale'] = {}
        app['autoscale']['name'] = self.as_name.data
        app['autoscale']['enable_metrics'] = self.enable_metrics.data
        if isinstance(self.min.data, int):
            app['autoscale']['min'] = self.min.data
        if isinstance(self.max.data, int):
            app['autoscale']['max'] = self.max.data


class SafedeploymentForm(FlaskForm):
    lb_type = BetterSelectField('Load Balancer', validators=[],
                                choices=[('elb', 'Classic Load Balancer (ELB)'), ('alb', 'Application Load Balancer'),
                                         ('haproxy', 'HAProxy')])
    safe_deploy_wait_before = IntegerField('Wait before deploy (s)',
                                           description='Time to wait before deployment (in seconds)', validators=[],
                                           default=10)
    safe_deploy_wait_after = IntegerField('Wait after deploy (s)',
                                          description='Time to wait after deployment (in seconds)', validators=[],
                                          default=10)

    haproxy_app_tag = StringField('HAProxy app tag', validators=[], description="Enter the value set for the HAproxy tag 'app'.\
                                A filter will be perform on Haproxy instances with this app tag value, running in the same environment \
                                as this application and with the tag role set to 'loadbalancer'")
    haproxy_api_port = IntegerField('HAProxy API port', validators=[],
                                    description="Enter the port number for the HAproxy API. Default is 5001",
                                    default=5001)
    haproxy_backend = StringField('HAProxy backend name', validators=[], description="Enter the Haproxy backend name where the \
                                                                                        application's instances will be registered")

    def __init__(self, csrf_enabled=False, *args, **kwargs):
        super(SafedeploymentForm, self).__init__(meta={'csrf': False}, *args, **kwargs)

    def map_from_app(self, app):
        # Populate form with safe deployment data if available. If not
        # set the default value to avoid applications created before the
        # safe deployment feature to stay stuck in the app edit view.
        if 'safe-deployment' not in app.keys():
            self.lb_type.data = 'elb'
            self.safe_deploy_wait_before.data = 10
            self.safe_deploy_wait_after.data = 10
        else:
            safe_deployment = app.get('safe-deployment', {})
            self.lb_type.data = safe_deployment.get('load_balancer_type', '')
            self.safe_deploy_wait_before.data = safe_deployment.get('wait_before_deploy', '')
            self.safe_deploy_wait_after.data = safe_deployment.get('wait_after_deploy', '')
            self.haproxy_app_tag.data = safe_deployment.get('app_tag_value', '')
            self.haproxy_backend.data = safe_deployment.get('ha_backend', '')
            self.haproxy_api_port.data = safe_deployment.get('api_port', 5001)

    def map_to_app(self, app):
        """
        Map safe deployment data from to app
        """
        app['safe-deployment'] = {}
        app['safe-deployment']['load_balancer_type'] = self.lb_type.data
        app['safe-deployment']['wait_before_deploy'] = self.safe_deploy_wait_before.data
        app['safe-deployment']['wait_after_deploy'] = self.safe_deploy_wait_after.data
        if self.lb_type.data == "haproxy":
            app['safe-deployment']['app_tag_value'] = self.haproxy_app_tag.data.strip()
            app['safe-deployment']['ha_backend'] = self.haproxy_backend.data.strip()
            app['safe-deployment']['api_port'] = self.haproxy_api_port.data


class BuildInfosForm(FlaskForm):
    ssh_username = StringField('SSH Username',
                               description='ec2-user by default on AWS AMI and admin on Claranet Debian AMI',
                               validators=[
                                   DataRequiredValidator(),
                                   RegexpValidator(
                                       ghost_app_schema['build_infos']['schema']['ssh_username']['regex']
                                   )
                               ], default='admin')

    source_ami = BetterSelectField('Source AWS AMI',
                                   description='Please choose a compatible AMI', choices=[],
                                   validators=[
                                       DataRequiredValidator(),
                                       RegexpValidator(
                                           ghost_app_schema['build_infos']['schema']['source_ami']['regex']
                                       )
                                   ])

    subnet_id = BetterSelectField('AWS Subnet', description='This subnet for building should be a public one',
                                  choices=[], validators=[
            DataRequiredValidator(),
            RegexpValidator(
                ghost_app_schema['build_infos']['schema']['subnet_id']['regex']
            )
        ])

    # Disable CSRF in build_infos forms as they are subforms
    def __init__(self, csrf_enabled=False, *args, **kwargs):
        super(BuildInfosForm, self).__init__(meta={'csrf': False}, *args, **kwargs)

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


class EnvironmentInfosForm(FlaskForm):
    security_groups = FieldList(BetterSelectField('Security Group', choices=[], validators=[
        OptionalValidator(),
        RegexpValidator(
            ghost_app_schema['environment_infos']['schema']['security_groups']['schema']['regex']
        )
    ]), min_entries=1)

    subnet_ids = FieldList(BetterSelectField('Subnet ID', choices=[], validators=[
        OptionalValidator(),
        RegexpValidator(
            ghost_app_schema['environment_infos']['schema']['subnet_ids']['schema']['regex']
        )
    ]), min_entries=1)

    instance_profile = BetterSelectField('Instance Profile',
                                         description='EC2 IAM should have at minimum ec2-describe-tags and s3-read-only policy on the Ghost bucket',
                                         validators=[
                                             OptionalValidator(),
                                             RegexpValidator(
                                                 ghost_app_schema['environment_infos']['schema']['instance_profile'][
                                                     'regex']
                                             )
                                         ])

    key_name = BetterSelectField('Key Name',
                                 description='Ghost should have the associated private key to deploy on instances',
                                 validators=[
                                     OptionalValidator(),
                                     RegexpValidator(
                                         ghost_app_schema['environment_infos']['schema']['key_name']['regex']
                                     )
                                 ])

    public_ip_address = BooleanField('Associate a public IP address',
                                     validators=[],
                                     default=True
                                     )

    root_block_device_size_min = ghost_app_schema['environment_infos']['schema']['root_block_device']['schema']['size'][
        'min']
    root_block_device_size = IntegerField('Size (GiB)',
                                          description='Must be equal or greater than the source AMI root block size (min {min}GiB)'.format(
                                              min=root_block_device_size_min), validators=[
            OptionalValidator(),
            NumberRangeValidator(min=root_block_device_size_min,
                                 message='To prevent low disk space alerts, disk size should be greater than {min}GiB'.format(
                                     min=root_block_device_size_min))
        ])

    root_block_device_name = StringField('Block Device Name', description='Empty if you want to use the default one', validators=[
        OptionalValidator(),
        RegexpValidator(
            ghost_app_schema['environment_infos']['schema']['root_block_device']['schema']['name']['regex']
        )
    ])

    optional_volumes = FieldList(FormField(OptionalVolumeForm, validators=[]), min_entries=1)

    instance_tags = FieldList(FormField(InstanceTagForm, validators=[]), min_entries=1, max_entries=42)

    # Disable CSRF in environment_infos forms as they are subforms
    def __init__(self, csrf_enabled=False, *args, **kwargs):
        super(EnvironmentInfosForm, self).__init__(meta={'csrf': False}, *args, **kwargs)

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
        self.public_ip_address.data = environment_infos.get('public_ip_address', True)

        self.root_block_device_size.data = environment_infos.get('root_block_device', {}).get('size', '')
        self.root_block_device_name.data = environment_infos.get('root_block_device', {}).get('name', '')

        if 'optional_volumes' in environment_infos and len(environment_infos['optional_volumes']) > 0:
            empty_fieldlist(self.optional_volumes)
            for opt_vol in environment_infos.get('optional_volumes', []):
                self.optional_volumes.append_entry()
                form_opt_vol = self.optional_volumes.entries[-1].form
                form_opt_vol.map_from_app(opt_vol)

        # Populate form with tags
        instance_tags = []
        if 'instance_tags' in environment_infos:
            instance_tags = environment_infos.get('instance_tags')
        if not instance_tags or 'Name' not in [i['tag_name'] for i in environment_infos['instance_tags']]:
            instance_tags.append(get_default_name_tag(app))
        empty_fieldlist(self.instance_tags)
        for tag in instance_tags:
            self.instance_tags.append_entry()
            form_tag = self.instance_tags.entries[-1].form
            form_tag.map_from_app(tag)


class ResourceForm(FlaskForm):
    # Disable CSRF in resource forms as they are subforms
    def __init__(self, csrf_enabled=False, *args, **kwargs):
        super(ResourceForm, self).__init__(meta={'csrf': False}, *args, **kwargs)

    def map_from_app(self, feature):
        # TODO: implement resource form
        pass


class LifecycleHooksForm(FlaskForm):
    pre_buildimage = TextAreaField('Pre Build Image', description='Script executed at bake before SALT provisioning',
                                   validators=[])
    post_buildimage = TextAreaField('Post Build Image', description='Script executed at bake after SALT provisioning',
                                    validators=[])
    pre_bootstrap = TextAreaField('Pre Bootstrap', description='Script executed at bootstrap before modules deploy',
                                  validators=[])
    post_bootstrap = TextAreaField('Post Bootstrap', description='Script executed at bootstrap after modules deploy',
                                   validators=[])

    # Disable CSRF in module forms as they are subforms
    def __init__(self, csrf_enabled=False, *args, **kwargs):
        super(LifecycleHooksForm, self).__init__(meta={'csrf': False}, *args, **kwargs)

    def map_from_app(self, app):
        if 'lifecycle_hooks' in app:
            lifecycle_hooks = app['lifecycle_hooks']
            if 'pre_buildimage' in lifecycle_hooks:
                self.pre_buildimage.data = lifecycle_hooks['pre_buildimage']
            if 'post_buildimage' in lifecycle_hooks:
                self.post_buildimage.data = lifecycle_hooks['post_buildimage']
            if 'pre_bootstrap' in lifecycle_hooks:
                self.pre_bootstrap.data = lifecycle_hooks['pre_bootstrap']
            if 'pre_bootstrap' in lifecycle_hooks:
                self.post_bootstrap.data = lifecycle_hooks['post_bootstrap']


class FeatureForm(FlaskForm):
    feature_name = StringField('Name', validators=[
        RegexpValidator(
            ghost_app_schema['features']['schema']['schema']['name']['regex']
        )
    ])
    feature_version = StringField('Value', validators=[
        RegexpValidator(
            ghost_app_schema['features']['schema']['schema']['version']['regex']
        )
    ])
    feature_provisioner = BetterSelectFieldNonValidating(
        'Provisioner', validators=[], render_kw={"data-classic-select": "true"},
        choices=get_wtforms_selectfield_values(get_available_provisioners_from_config(config)))

    # Disable CSRF in feature forms as they are subforms
    def __init__(self, csrf_enabled=False, *args, **kwargs):
        super(FeatureForm, self).__init__(meta={'csrf': False}, *args, **kwargs)

    def map_from_app(self, feature):
        self.feature_name.data = feature.get('name', '')
        self.feature_version.data = feature.get('version', '')
        self.feature_provisioner.data = feature.get('provisioner', DEFAULT_PROVISIONER_TYPE)


class EnvvarForm(FlaskForm):
    var_key = StringField('Key', validators=[
        RegexpValidator(
            ghost_app_schema['env_vars']['schema']['schema']['var_key']['regex']
        ), OptionalValidator()
    ])
    var_value = StringField('Value', validators=[
        OptionalValidator()
    ])

    # Disable CSRF in feature forms as they are subforms
    def __init__(self, csrf_enabled=False, *args, **kwargs):
        super(EnvvarForm, self).__init__(meta={'csrf': False}, *args, **kwargs)

    def map_from_app(self, envvar):
        self.var_key.data = envvar.get('var_key', '')
        self.var_value.data = envvar.get('var_value', '')


class ModuleForm(FlaskForm):
    module_name = StringField('Name', description='Module name: should not include special chars', validators=[
        DataRequiredValidator(),
        RegexpValidator(
            ghost_app_schema['modules']['schema']['schema']['name']['regex']
        )
    ])
    module_git_repo = StringField('Git Repository', validators=[DataRequiredValidator()])
    module_path = StringField('Path', description='Destination path to deploy to', validators=[
        DataRequiredValidator(),
        RegexpValidator(
            ghost_app_schema['modules']['schema']['schema']['path']['regex']
        )
    ])
    module_uid = IntegerField('UID',
                              description='File UID (User), by default it uses the ID of Ghost user on the Ghost instance',
                              validators=[
                                  OptionalValidator(),
                                  NumberRangeValidator(min=0)
                              ])
    module_gid = IntegerField('GID',
                              description='File GID (Group), by default it uses the ID of Ghost group on the Ghost instance',
                              validators=[
                                  OptionalValidator(),
                                  NumberRangeValidator(min=0)
                              ])

    module_scope = BetterSelectField('Scope', validators=[DataRequiredValidator()], choices=get_ghost_mod_scopes())
    module_build_pack = TextAreaField('Build Pack',
                                      description='Script executed on Ghost in order to build artifacts before packaging.',
                                      validators=[])
    module_pre_deploy = TextAreaField('Pre Deploy',
                                      description='Script executed on each target instance *before* deploying the module.',
                                      validators=[])
    module_post_deploy = TextAreaField('Post Deploy',
                                       description='Script executed on each target instance *after* deploying the module.',
                                       validators=[])
    module_after_all_deploy = TextAreaField('After All Deploy',
                                            description='Script executed on Ghost after deploying the module on every instances.',
                                            validators=[])

    # Disable CSRF in module forms as they are subforms
    def __init__(self, csrf_enabled=False, *args, **kwargs):
        super(ModuleForm, self).__init__(meta={'csrf': False}, *args, **kwargs)

    def map_from_app(self, module):
        self.module_name.data = module.get('name', '')
        self.module_git_repo.data = module.get('git_repo', '')
        self.module_path.data = module.get('path', '')
        self.module_scope.data = module.get('scope', '')
        self.module_uid.data = module.get('uid', '')
        self.module_gid.data = module.get('gid', '')
        if 'build_pack' in module:
            self.module_build_pack.data = module['build_pack']
        if 'pre_deploy' in module:
            self.module_pre_deploy.data = module['pre_deploy']
        if 'post_deploy' in module:
            self.module_post_deploy.data = module['post_deploy']
        if 'after_all_deploy' in module:
            self.module_after_all_deploy.data = module['after_all_deploy']


class BluegreenForm(FlaskForm):
    alter_ego_id = HiddenField(validators=[])
    color = HiddenField(validators=[])
    enable_blue_green = BooleanField('Enable Blue/Green deployment', validators=[])

    # Disable CSRF in module forms as they are subforms
    def __init__(self, csrf_enabled=False, *args, **kwargs):
        super(BluegreenForm, self).__init__(meta={'csrf': False}, *args, **kwargs)

    def map_from_app(self, app):
        """
        Map app data to blue green form
        """
        blue_green, app_color = get_blue_green_from_app(app)
        if blue_green:
            self.alter_ego_id.data = blue_green.get('alter_ego_id', '')
            self.color.data = app_color
            # Map if blue/green is enabled
            self.enable_blue_green.data = blue_green.get('enable_blue_green',
                                                         blue_green.get('alter_ego_id', None) and app_color)

    def map_to_app(self, app):
        """
        Map blue green data form to app
        """
        app['blue_green'] = {}
        app['blue_green']['enable_blue_green'] = isinstance(self.enable_blue_green.data,
                                                            bool) and self.enable_blue_green.data


class BaseAppForm(FlaskForm):
    # App properties
    name = StringField('App name', description='This mandatory field will not be editable after app creation',
                       validators=[
                           DataRequiredValidator(),
                           RegexpValidator(
                               ghost_app_schema['name']['regex']
                           )
                       ])

    env = BetterSelectField('App environment',
                            description='This mandatory field will not be editable after app creation',
                            validators=[DataRequiredValidator()], choices=get_ghost_app_envs())
    role = BetterSelectField('App role', description='This mandatory field will not be editable after app creation',
                             validators=[DataRequiredValidator()], choices=get_ghost_app_roles())
    # Cloud Provider
    # Leave the following line commented to remember for further
    # dev to manage other cloud providers than aws
    # provider = BetterSelectField('Provider', validators=[DataRequiredValidator()], choices=get_ghost_app_providers())
    use_custom_identity = BooleanField('Use a custom Identity', validators=[])

    assumed_account_id = StringField('Assumed Account ID', validators=[
        OptionalValidator(),
        RegexpValidator(
            ghost_app_schema['assumed_account_id']['regex']
        )
    ])

    assumed_role_name = StringField('Assumed Role Name', validators=[
        OptionalValidator(),
        RegexpValidator(
            ghost_app_schema['assumed_role_name']['regex']
        )
    ])

    assumed_region_name = StringField('Assumed Region Name', validators=[
        OptionalValidator(),
        RegexpValidator(
            ghost_app_schema['assumed_region_name']['regex']
        )
    ])

    # Notification properties
    log_notifications = FieldList(StringField('Email', description='Recipient destination', validators=[
        OptionalValidator(),
        RegexpValidator(
            ghost_app_schema['log_notifications']['schema']['regex']
        )
    ]), min_entries=1)

    # Blue Green hidden properties
    blue_green = FormField(BluegreenForm)

    # Autoscale properties
    autoscale = FormField(AutoscaleForm)

    # Safe deployment properties
    safedeployment = FormField(SafedeploymentForm)

    # Build properties
    build_infos = FormField(BuildInfosForm)

    # Resources properties
    # TODO: implement resources
    # resources = FieldList(FormField(ResourceForm), min_entries=1)

    # Environment properties
    environment_infos = FormField(EnvironmentInfosForm)

    # Env vars
    env_vars = FieldList(FormField(EnvvarForm), min_entries=1)

    # AWS properties
    region = BetterSelectField('AWS Region', validators=[DataRequiredValidator()], choices=[])

    instance_type = BetterSelectField('AWS Instance Type', validators=[DataRequiredValidator()], choices=[])

    instance_monitoring = BooleanField('AWS Detailed Instance Monitoring', validators=[])

    vpc_id = BetterSelectField('AWS VPC', choices=[], validators=[
        DataRequiredValidator(),
        RegexpValidator(
            ghost_app_schema['vpc_id']['regex']
        )
    ])

    lifecycle_hooks = FormField(LifecycleHooksForm)

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
        # app['provider'] = self.provider.data
        if self.assumed_account_id:
            app['assumed_account_id'] = self.assumed_account_id.data
        if self.assumed_role_name:
            app['assumed_role_name'] = self.assumed_role_name.data
        if self.assumed_region_name:
            app['assumed_region_name'] = self.assumed_region_name.data
        if self.env:
            app['env'] = self.env.data
        if self.role:
            app['role'] = self.role.data
        app['region'] = self.region.data
        app['instance_type'] = self.instance_type.data
        app['instance_monitoring'] = self.instance_monitoring.data
        app['vpc_id'] = self.vpc_id.data

        self.map_to_app_log_notifications(app)
        self.map_to_app_blue_green(app)
        self.map_to_app_autoscale(app)
        self.map_to_app_safedeployment(app)
        self.map_to_app_build_infos(app)
        self.map_to_app_resources(app)
        self.map_to_app_environment_infos(app)
        self.map_to_app_env_vars(app)
        self.map_to_app_lifecycle_hooks(app)
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

    def map_to_app_blue_green(self, app):
        """
        Maps blue green data from form to app
        """
        self.blue_green.form.map_to_app(app)

    def map_to_app_autoscale(self, app):
        """
        Map autoscale data from form to app
        """
        self.autoscale.form.map_to_app(app)

    def map_to_app_safedeployment(self, app):
        """
        Map safe deployment data from form to app
        """
        self.safedeployment.form.map_to_app(app)

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
        app['environment_infos']['public_ip_address'] = self.environment_infos.form.public_ip_address.data

        app['environment_infos']['root_block_device'] = {}
        if self.environment_infos.form.root_block_device_size.data:
            app['environment_infos']['root_block_device'][
                'size'] = self.environment_infos.form.root_block_device_size.data
        else:
            # default value to prevent low disk space alerts
            block_min_size = ghost_app_schema['environment_infos']['schema']['root_block_device']['schema']['size']['min']
            app['environment_infos']['root_block_device']['size'] = block_min_size

        root_block_name = self.environment_infos.form.root_block_device_name.data
        app['environment_infos']['root_block_device']['name'] = root_block_name or ''

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

        app['environment_infos']['instance_tags'] = []
        for form_tag in self.environment_infos.form.instance_tags:
            tag = {}
            if form_tag.tag_name.data:
                tag['tag_name'] = form_tag.tag_name.data
                tag['tag_value'] = form_tag.tag_value.data
                app['environment_infos']['instance_tags'].append(tag)

    def map_to_app_env_vars(self, app):
        """
        Map Environment variable data from form to app
        """
        app['env_vars'] = []
        for form_envvar in self.env_vars:
            env_var = {}
            if form_envvar.var_key.data:
                env_var['var_key'] = form_envvar.var_key.data
                if form_envvar.var_value.data:
                    env_var['var_value'] = form_envvar.var_value.data
            if env_var:
                app['env_vars'].append(env_var)

    def map_to_app_lifecycle_hooks(self, app):
        """
        Map lifecycle hooks data from form to app
        """
        app['lifecycle_hooks'] = {}
        form_lifecycle_hooks = self.lifecycle_hooks
        if form_lifecycle_hooks.pre_buildimage.data:
            app['lifecycle_hooks']['pre_buildimage'] = b64encode_utf8(
                form_lifecycle_hooks.pre_buildimage.data.replace('\r\n', '\n'))
        else:
            app['lifecycle_hooks']['pre_buildimage'] = ''

        if form_lifecycle_hooks.post_buildimage.data:
            app['lifecycle_hooks']['post_buildimage'] = b64encode_utf8(
                form_lifecycle_hooks.post_buildimage.data.replace('\r\n', '\n'))
        else:
            app['lifecycle_hooks']['post_buildimage'] = ''

        if form_lifecycle_hooks.pre_bootstrap.data:
            app['lifecycle_hooks']['pre_bootstrap'] = b64encode_utf8(
                form_lifecycle_hooks.pre_bootstrap.data.replace('\r\n', '\n'))
        else:
            app['lifecycle_hooks']['pre_bootstrap'] = ''

        if form_lifecycle_hooks.post_bootstrap.data:
            app['lifecycle_hooks']['post_bootstrap'] = b64encode_utf8(
                form_lifecycle_hooks.post_bootstrap.data.replace('\r\n', '\n'))
        else:
            app['lifecycle_hooks']['post_bootstrap'] = ''

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
                if form_feature.feature_provisioner.data:
                    feature['provisioner'] = form_feature.feature_provisioner.data
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
            if isinstance(form_module.module_uid.data, int):
                module['uid'] = form_module.module_uid.data
            if isinstance(form_module.module_gid.data, int):
                module['gid'] = form_module.module_gid.data
            if form_module.module_build_pack.data:
                module['build_pack'] = b64encode_utf8(form_module.module_build_pack.data.replace('\r\n', '\n'))
            if form_module.module_pre_deploy.data:
                module['pre_deploy'] = b64encode_utf8(form_module.module_pre_deploy.data.replace('\r\n', '\n'))
            if form_module.module_post_deploy.data:
                module['post_deploy'] = b64encode_utf8(form_module.module_post_deploy.data.replace('\r\n', '\n'))
            if form_module.module_after_all_deploy.data:
                module['after_all_deploy'] = b64encode_utf8(
                    form_module.module_after_all_deploy.data.replace('\r\n', '\n'))
            app['modules'].append(module)

    def map_from_app(self, app):
        """
        Map app data from app to form
        """

        # Populate form with app data
        self.name.data = app.get('name', '')
        # self.provider.data = app.get('provider', DEFAULT_PROVIDER)
        self.assumed_account_id.data = app.get('assumed_account_id', '')
        self.assumed_role_name.data = app.get('assumed_role_name', '')
        self.assumed_region_name.data = app.get('assumed_region_name', '')
        self.env.data = app.get('env', '')
        self.role.data = app.get('role', '')
        self.region.data = app.get('region', '')
        self.instance_type.data = app.get('instance_type', '')
        self.instance_monitoring.data = app.get('instance_monitoring', False)
        self.vpc_id.data = app.get('vpc_id', '')

        self.map_from_app_notifications(app)
        self.map_from_app_bluegreen(app)
        self.map_from_app_autoscale(app)
        self.map_from_app_safedeployment(app)
        self.map_from_app_build_infos(app)
        self.map_from_app_environment_infos(app)
        self.map_from_app_env_vars(app)
        self.map_from_app_lifecycle_hooks(app)
        self.map_from_app_features(app)
        self.map_from_app_modules(app)

        # TODO: handle resources app data

    def map_from_app_bluegreen(self, app):
        """
        Map bluegreen data from app to form
        """
        return self.blue_green.form.map_from_app(app)

    def map_from_app_autoscale(self, app):
        """
        Map autoscale data from app to form
        """
        return self.autoscale.form.map_from_app(app)

    def map_from_app_safedeployment(self, app):
        """
        Map safe deployment data from app to form
        """
        return self.safedeployment.form.map_from_app(app)

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

    def map_from_app_env_vars(self, app):
        """
        Map environment variables data from app to form
        """
        if 'env_vars' in app and len(app['env_vars']) > 0:
            empty_fieldlist(self.env_vars)
            for envvar in app.get('env_vars', []):
                self.env_vars.append_entry()
                form_envvar = self.env_vars.entries[-1].form
                form_envvar.map_from_app(envvar)

    def map_from_app_lifecycle_hooks(self, app):
        """
        Map lifecycle hooks data from app to form
        """
        return self.lifecycle_hooks.form.map_from_app(app)

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
        # Leave the following line commented to remember for further
        # The following commented lines intend to manage other cloud providers than aws
        # self.provider.choices = [('', 'Please select a cloud provider')] + get_ghost_app_providers()
        # self.provider.data = DEFAULT_PROVIDER
        if self.use_custom_identity.data:
            aws_connection_data = get_aws_connection_data(
                self.assumed_account_id.data,
                self.assumed_role_name.data,
                self.assumed_region_name.data
            )
        else:
            aws_connection_data = {}
        # provider is intended to be an application attribute
        # self.region.choices = [('', 'Please select region')] + get_aws_ec2_regions(self.provider.data, **aws_connection_data)
        self.region.choices = [('', 'Please select region')] + get_aws_ec2_regions(DEFAULT_PROVIDER,
                                                                                   **aws_connection_data)
        self.instance_type.choices = [('', 'Please select region first')]
        self.vpc_id.choices = [('', 'Please select region first')]
        self.autoscale.as_name.choices = [('', 'Please select region first')]
        self.environment_infos.security_groups[0].choices = [('', 'Please select region first')]
        self.environment_infos.instance_profile.choices = [('', 'Please select region first')]
        self.environment_infos.key_name.choices = [('', 'Please select region first')]
        self.build_infos.source_ami.choices = [('', 'Please select region first')]
        self.build_infos.subnet_id.choices = [('', 'Please select VPC first')]
        self.environment_infos.subnet_ids[0].choices = [('', 'Please select VPC first')]


class EditAppForm(BaseAppForm):
    etag = HiddenField(validators=[DataRequiredValidator()])
    update_manifest = HiddenField(validators=[])

    submit = SubmitField('Update Application')

    def __init__(self, *args, **kwargs):
        super(EditAppForm, self).__init__(*args, **kwargs)

        # Refresh AWS lists, check what to refresh exactly in this new version,
        # self.provider.choices = get_ghost_app_providers()

    def map_from_app(self, app):
        """
        Map app data from app to form
        """
        # Store app etag in form
        self.etag.data = app.get('_etag', '')

        # Keep the use_custom_identity checked if it was
        if app.get('assumed_account_id', None) and app.get('assumed_role_name', None):
            self.use_custom_identity.data = True

        super(EditAppForm, self).map_from_app(app)


class DeleteAppForm(FlaskForm):
    etag = HiddenField(validators=[DataRequiredValidator()])
    confirmation = RadioField('Are you sure?', validators=[DataRequiredValidator()],
                              choices=[('yes', 'Yes'), ('no', 'No')])

    submit = SubmitField('Delete Application')
