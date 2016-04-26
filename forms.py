from flask_wtf import Form

from wtforms import FieldList, FormField, HiddenField, IntegerField, RadioField, SelectField, StringField, SubmitField, TextAreaField, BooleanField
from wtforms.validators import DataRequired as DataRequiredValidator
from wtforms.validators import NumberRange as NumberRangeValidator
from wtforms.validators import Optional as OptionalValidator
from wtforms.validators import Regexp as RegexpValidator

from datetime import datetime
from base64 import b64encode
import traceback
import boto.vpc
import boto.ec2
import boto.iam
import boto.ec2.autoscale
import boto.ec2.elb
import aws_data

from models.apps import apps_schema as ghost_app_schema
from models.jobs import jobs_schema as ghost_job_schema

from web_ui.ghost_client import get_ghost_app, get_ghost_job_commands


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

def get_aws_iam_instance_profiles(region):
    profiles = []
    try:
        c = boto.iam.connect_to_region(region)
        profiles = c.list_instance_profiles()
    except:
        traceback.print_exc()
    return [(profile.instance_profile_name, profile.instance_profile_name + ' (' + profile.arn + ')') for profile in profiles.instance_profiles]

def get_aws_ec2_key_pairs(region):
    keys = []
    try:
        c = boto.ec2.connect_to_region(region)
        keys = c.get_all_key_pairs()
    except:
        traceback.print_exc()
    return [(key.name, key.name + ' (' + key.fingerprint + ')') for key in keys]

def get_aws_ec2_regions():
    regions = []
    try:
        regions = sorted(boto.ec2.regions(), key=lambda region: region.name)
    except:
        traceback.print_exc()
    return [(region.name, '{name} ({endpoint})'.format(name=region.name, endpoint=region.endpoint)) for region in regions]
    
def get_aws_as_groups(region):
    asgs = []
    try:
        conn_as = boto.ec2.autoscale.connect_to_region(region)
        asgs = conn_as.get_all_groups()
    except:
        traceback.print_exc()
    return [('', '-- No Autoscale for this app --')]+[(asg.name, asg.name + ' (' + asg.launch_config_name + ')') for asg in asgs]

def get_ghost_app_as_group(as_group_name, region):
    try:
        conn_as = boto.ec2.autoscale.connect_to_region(region)
        asgs = conn_as.get_all_groups(names=[as_group_name])
        if len(asgs) > 0:
            return asgs[0]
        return None
    except:
        traceback.print_exc()
    return None

def get_as_group_instances(as_group, region):
    conn = boto.ec2.connect_to_region(region)
    instance_ids = []
    for i in as_group.instances:
        if i.health_status != 'Unhealthy':
            instance_ids.append(i.instance_id)
    hosts = []
    if len(instance_ids) > 0:
        instances = conn.get_only_instances(instance_ids=instance_ids)
        for host in instances:
            hosts.append(format_host_infos(host, conn, region))
    return hosts

def get_elbs_in_as_group(as_group, region):
    try:
        conn_elb = boto.ec2.elb.connect_to_region(region)
        if len(as_group.load_balancers) > 0:
            as_elbs = conn_elb.get_all_load_balancers(load_balancer_names=as_group.load_balancers)
            if len(as_elbs) > 0:
                return as_elbs
            else:
                return None
        else:
            return None
    except:
        traceback.print_exc()
    return None

def get_elbs_instances_from_as_group(as_group, region):
    try:
        elbs = get_elbs_in_as_group(as_group, region)
        if elbs:
            elbs_instances = []
            for elb in elbs:
                if len(elb.instances) > 0:
                    elb_instance_ids = []
                    for instance in elb.instances:
                        elb_instance_ids.append('#' + instance.id)
                    elbs_instances.append({'elb_name':elb.name, 'elb_instances':elb_instance_ids})
            return elbs_instances
        else:
            return None
    except:
        traceback.print_exc()
    return None

def get_ghost_app_ec2_instances(ghost_app, ghost_env, ghost_role, region, filters=[]):
    conn_as = boto.ec2.autoscale.connect_to_region(region)
    conn = boto.ec2.connect_to_region(region)

    # Retrieve running instances
    running_instance_filters = {"tag:env": ghost_env, "tag:role": ghost_role, "tag:app": ghost_app}
    running_instances = conn.get_only_instances(filters=running_instance_filters)

    host_ids_as = []
    if len(filters) > 0:
        for h in filters:
            host_ids_as.append(h.instance_id)
    hosts = []
    for instance in running_instances:
        # Instances in autoscale "Terminating:*" states are still "running" but no longer in the Load Balancer
        autoscale_instances = conn_as.get_all_autoscaling_instances(instance_ids=[instance.id])
        if not autoscale_instances or not autoscale_instances[0].lifecycle_state in ['Terminating', 'Terminating:Wait', 'Terminating:Proceed']:
            if instance.id not in host_ids_as:
                hosts.append(format_host_infos(instance, conn, region))
        else:
            hosts.append({'id': instance.id, 'private_ip_address': instance.private_ip_address, 'status': 'terminated'})

    return hosts

def format_host_infos(instance, conn, region):
    sg_string = None
    image = conn.get_image(instance.image_id)
    image_string = "{ami_id} ({ami_name})".format(ami_id=instance.image_id, ami_name=image.name if image is not None else 'deregistered')
    sg_string = ', '.join(["{sg_id} ({sg_name})".format(sg_id=sg.id, sg_name=sg.name) for sg in instance.groups])

    if instance.subnet_id:
        subnets = boto.vpc.connect_to_region(region).get_all_subnets(subnet_ids=[instance.subnet_id])
        subnet_string = instance.subnet_id + ' (' + subnets[0].tags.get('Name', '') + ')'
    else:
        subnet_string = '-'
    host = {
      'id': instance.id,
      'private_ip_address': instance.private_ip_address,
      'public_ip_address': instance.ip_address,
      'status': instance.state,
      'launch_time': datetime.strptime(instance.launch_time, "%Y-%m-%dT%H:%M:%S.%fZ"),
      'security_group':sg_string,
      'subnet_id':subnet_string,
      'image_id':image_string,
      'instance_type':instance.instance_type,
      'instance_profile':str(instance.instance_profile['arn']).split("/")[1] if instance.instance_profile else '-'
    }
    return host

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

def safe_deployment_possibilities(hosts_list):
    """ Return a dict with split types as key and string as value
        which describes the number of instances per deployment group.

        :param  hosts_list  list:  A list of instances IPs.
        :return  dict
    """
    split_types = ['1by1', '1/3', '25%', '50%']
    msg = 'Number of instances per deployment group:'
    possibilities = {}
    for split_type in split_types:
        if split_type == '1by1' and len(hosts_list) > 1:
            groups_one = ['Group' + str(i[0] + 1) + ' : 1 |' for i in enumerate(hosts_list)]
            if len(groups_one) > 5:
                groups_one = groups_one[0:5] + ['.....']
            possibilities['1by1'] = '{0} | {1} ' .format(msg, str(' '.join(groups_one))[:-2])
        elif split_type == '1/3' and len(hosts_list) > 2:
            split_list = [hosts_list[i::3] for i in range(3)]
            possibilities['1/3'] =  '{0} | Group1 : {1} | Group2 : {2} | Group3 : {3}' .format(msg, len(split_list[0]), len(split_list[1]), len(split_list[2]))
        elif split_type == '25%' and len(hosts_list) > 3:
            split_list = [hosts_list[i::4] for i in range(4)]
            possibilities['25%'] = '{0} | Group1 : {1} | Group2 : {2} | Group3 : {3} | Group4 : {4}' .format(msg, len(split_list[0]), len(split_list[1]), len(split_list[2]), len(split_list[3]))
        elif split_type == '50%' and len(hosts_list) == 2 or len(hosts_list) > 3:
            split_list = [hosts_list[i::2] for i in range(2)]
            possibilities['50%'] = '{0} | Group1 : {1} | Group2 : {2}' .format(msg, len(split_list[0]), len(split_list[1]))
    if not possibilities:
        possibilities = {'None': 'Not Supported because at least two instances must be running for this application'}
    return possibilities


class OptionalVolumeForm(Form):
    device_name = StringField('Device Name', description='Should match /dev/sd[a-z] or /dev/xvd[b-c][a-z]', validators=[])
    volume_type = SelectField('Volume Type', description='More details on <a target="_blank" href="http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/EBSVolumeTypes.html">AWS Documentation</a>', validators=[], choices=get_ghost_optional_volumes())
    volume_size = IntegerField('Volume Size', description='In GiB', validators=[OptionalValidator()])
    iops = IntegerField('IOPS', description='For information, 1TiB volume size is 3000 IOPS in GP2 type', validators=[OptionalValidator()])

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
    as_name = SelectField('Name', choices=[], validators=[])

    min = IntegerField('Min', description='The minimum size of the Auto Scaling group', validators=[
        OptionalValidator(),
        NumberRangeValidator(min=0)
    ])

    max = IntegerField('Max', description='The maximum size of the Auto Scaling group', validators=[
        OptionalValidator(),
        NumberRangeValidator(min=1)
    ])

    current = IntegerField('Desired', description='The number of instances that should be running in the Auto Scaling group', validators=[
        OptionalValidator()
    ])

    lb_type = SelectField('Load Balancer', validators=[], choices=[('elb','Elastic Load Balancer'), ('haproxy','HAProxy')])

    safe_deploy_wait_before = IntegerField('Time to wait before deployment', validators=[], default = 10)
    safe_deploy_wait_after = IntegerField('Time to wait after deployment', validators=[], default = 10)

    haproxy_app_tag = StringField('HAProxy app tag', validators=[], description="Enter the value set for the HAproxy tag 'app'.\
                                A filter will be perform on Haproxy instances with this app tag value, running in the same environment \
                                as this application and with the tag role set to 'loadbalancer'")
    haproxy_api_port = IntegerField('HAProxy API port', validators=[], description="Enter the port number for the HAproxy API. Default is 5001", default = 5001)
                                as this application and with the tag role set to 'loadbalancer'")
    haproxy_backend = StringField('HAProxy backend name', validators=[], description="Enter the Haproxy backend name where the \
                                                                                        application's instances will be registered")


    # Disable CSRF in autoscale forms as they are subforms
    def __init__(self, csrf_enabled=False, *args, **kwargs):
        super(AutoscaleForm, self).__init__(csrf_enabled=csrf_enabled, *args, **kwargs)

    def map_from_app(self, app):
        # Populate form with autoscale data if available
        autoscale = app.get('autoscale', {})
        self.min.data = autoscale.get('min', '')
        self.max.data = autoscale.get('max', '')
        self.current.data = autoscale.get('current', '')
        self.as_name.data = autoscale.get('name', '')

    def map_to_app(self, app):
        """
        Map autoscale & safe deployment data from form to app
        """
        app['autoscale'] = {}
        app['autoscale']['name'] = self.as_name.data
        if isinstance(self.min.data, int):
            app['autoscale']['min'] = self.min.data
        if isinstance(self.max.data, int):
            app['autoscale']['max'] = self.max.data
        if isinstance(self.current.data, int):
            app['autoscale']['current'] = self.current.data
        app['safe-deployment'] = {}
        app['safe-deployment']['load_balancer_type'] = self.lb_type.data
        app['safe-deployment']['wait_before_deploy'] = self.safe_deploy_wait_before.data
        app['safe-deployment']['wait_after_deploy'] = self.safe_deploy_wait_after.data
        if self.lb_type.data == "haproxy":
            app['safe-deployment']['app_tag_value'] = self.haproxy_app_tag.data
            app['safe-deployment']['ha_backend'] = self.haproxy_backend.data
            app['safe-deployment']['api_port'] = self.haproxy_api_port.data

class BuildInfosForm(Form):
    ssh_username = StringField('SSH Username', description='ec2-user by default on AWS AMI and admin on Morea Debian AMI', validators=[
        DataRequiredValidator(),
        RegexpValidator(
            ghost_app_schema['build_infos']['schema']['ssh_username']['regex']
        )
    ], default='admin')

    source_ami = SelectField('Source AWS AMI', description='Please choose an AMI compatible with Ghost provisioning', choices=[], validators=[
        DataRequiredValidator(),
        RegexpValidator(
            ghost_app_schema['build_infos']['schema']['source_ami']['regex']
        )
    ])

    subnet_id = SelectField('AWS Subnet', description='This subnet for building should be a public one', choices=[], validators=[
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

    instance_profile = SelectField('Instance Profile', description='EC2 IAM should have at minimum ec2-describe-tags and s3-read-only policy on the Ghost bucket', validators=[
        OptionalValidator(),
        RegexpValidator(
            ghost_app_schema['environment_infos']['schema']['instance_profile']['regex']
        )
    ])

    key_name = SelectField('Key Name', description='Ghost should have the associated private key to deploy on instances', validators=[
        OptionalValidator(),
        RegexpValidator(
            ghost_app_schema['environment_infos']['schema']['key_name']['regex']
        )
    ])

    root_block_device_size = IntegerField('Size (GiB)', description='Must be equal or greater than the source AMI root block size', validators=[
        OptionalValidator(),
        NumberRangeValidator(min=0)
    ]);

    root_block_device_name = StringField('Name', description='Empty if you want to use the default one', validators=[
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

class LifecycleHooksForm(Form):
    pre_bootstrap = TextAreaField('Pre Bootstrap', description='Script executed at bootstrap before modules deploy', validators=[])
    post_bootstrap = TextAreaField('Post Bootstrap', description='Script executed at bootstrap after modules deploy', validators=[])

    # Disable CSRF in module forms as they are subforms
    def __init__(self, csrf_enabled=False, *args, **kwargs):
        super(LifecycleHooksForm, self).__init__(csrf_enabled=csrf_enabled, *args, **kwargs)

    def map_from_app(self, app):
        if 'lifecycle_hooks' in app:
            lifecycle_hooks = app['lifecycle_hooks']
            if 'pre_bootstrap' in lifecycle_hooks:
                self.pre_bootstrap.data = lifecycle_hooks['pre_bootstrap']
            if 'pre_bootstrap' in lifecycle_hooks:
                self.post_bootstrap.data = lifecycle_hooks['post_bootstrap']

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
    module_uid = IntegerField('UID', description='File UID (User), by default it uses the ID of Ghost user on the Ghost instance', validators=[
        OptionalValidator(),
        NumberRangeValidator(min=0)
    ])
    module_gid = IntegerField('GID', description='File GID (Group), by default it uses the ID of Ghost group on the Ghost instance', validators=[
        OptionalValidator(),
        NumberRangeValidator(min=0)
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
        self.module_uid.data = module.get('uid', '')
        self.module_gid.data = module.get('gid', '')
        if 'build_pack' in module:
            self.module_build_pack.data = module['build_pack']
        if 'pre_deploy' in module:
            self.module_pre_deploy.data = module['pre_deploy']
        if 'post_deploy' in module:
            self.module_post_deploy.data = module['post_deploy']


class BaseAppForm(Form):
    # App properties
    name = StringField('App name', description='This mandatory field will not be editable after app creation', validators=[
        DataRequiredValidator(),
        RegexpValidator(
            ghost_app_schema['name']['regex']
        )
    ])

    env = SelectField('App environment', description='This mandatory field will not be editable after app creation', validators=[DataRequiredValidator()], choices=get_ghost_app_envs())

    role = SelectField('App role', description='This mandatory field will not be editable after app creation', validators=[DataRequiredValidator()], choices=get_ghost_app_roles())

    # Notification properties
    log_notifications = FieldList(StringField('Email', description='Recipient destination', validators=[
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


    def map_to_app_lifecycle_hooks(self, app):
        """
        Map lifecycle hooks data from form to app
        """
        app['lifecycle_hooks'] = {}
        form_lifecycle_hooks = self.lifecycle_hooks
        if form_lifecycle_hooks.pre_bootstrap.data:
            app['lifecycle_hooks']['pre_bootstrap'] = b64encode(form_lifecycle_hooks.pre_bootstrap.data.replace('\r\n', '\n'))
        else:
            app['lifecycle_hooks']['pre_bootstrap'] = ''

        if form_lifecycle_hooks.post_bootstrap.data:
            app['lifecycle_hooks']['post_bootstrap'] = b64encode(form_lifecycle_hooks.post_bootstrap.data.replace('\r\n', '\n'))
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
        self.map_from_app_lifecycle_hooks(app)
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
        self.region.choices = [('', 'Please select region')] + get_aws_ec2_regions()
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
    update_manifest = HiddenField(validators=[]);

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
    command = SelectField('Command', validators=[DataRequiredValidator()], choices=[])
    module_name = SelectField('Module name', validators=[])
    module_rev = StringField('Module revision', validators=[])
    deploy_id = StringField('Deploy ID', validators=[])
    fabric_execution_strategy = SelectField('Deployment strategy', validators=[], choices=[('serial', 'serial'), ('parallel', 'parallel')])
    safe_deployment = BooleanField('Deploy with Safe Deployment', validators=[])
    safe_deployment_strategy = SelectField('Safe Deployment Strategy', validators=[], choices=[])
    instance_type = SelectField('Instance Type', validators=[], choices=[])
    skip_salt_bootstrap = BooleanField('Skip Salt Bootstrap', validators=[])

    submit = SubmitField('Run Application Command')

    def __init__(self, app_id, *args, **kwargs):
        super(CommandAppForm, self).__init__(*args, **kwargs)

        # Get the Ghost application
        app = get_ghost_app(app_id)

        # Get the list of commands at construction time because it requires a request context
        self.command.choices = get_ghost_job_commands()

        # Get the modules of the Ghost application
        self.module_name.choices = [('', '')] + [(module['name'], module['name']) for module in app['modules']]

        # Get the instance types in the Ghost application's region
        self.instance_type.choices = get_aws_ec2_instance_types(app["region"])

        # Get the safe deployment possibilities
        hosts_list = get_ghost_app_ec2_instances(app['name'], app['env'], app['role'], app['region'])
        safe_possibilities = safe_deployment_possibilities(hosts_list)
        self.safe_deployment_strategy.choices = [('', '')] + [(k, v) for k,v in safe_possibilities.items()]

    def map_from_app(self, app):
        """
        Map app data from app to form
        """
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
