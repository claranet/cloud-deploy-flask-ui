import traceback
from datetime import datetime

import aws_data
from ghost_tools import config
from libs import load_balancing
from libs.blue_green import get_blue_green_from_app
from settings import cloud_connections, DEFAULT_PROVIDER


def get_aws_connection_data(assumed_account_id, assumed_role_name, assumed_region_name=""):
    """
    Build a key-value dictionnatiory args for aws cross  connections
    """
    if assumed_account_id and assumed_role_name:
        aws_connection_data = dict(
            [("assumed_account_id", assumed_account_id), ("assumed_role_name", assumed_role_name),
             ("assumed_region_name", assumed_region_name)])
    else:
        aws_connection_data = {}
    return (aws_connection_data)


def get_aws_vpc_ids(provider, region, log_file=None, **kwargs):
    vpcs = []
    try:
        cloud_connection = cloud_connections.get(provider)(log_file, **kwargs)
        c = cloud_connection.get_connection(region, ["vpc"])
        vpcs = c.get_all_vpcs()
    except:
        traceback.print_exc()
    return [(vpc.id, '{} ({})'.format(vpc.id, vpc.tags.get('Name', ''))) for vpc in vpcs]


def check_aws_assumed_credentials(provider, account_id, role_name, region_name="", log_file=None):
    cloud_connection = cloud_connections.get(provider)(
        log_file,
        assumed_account_id=account_id,
        assumed_role_name=role_name,
        assumed_region_name=region_name
    )
    return (cloud_connection.check_credentials())


def get_aws_sg_ids(provider, region, vpc_id, log_file=None, **kwargs):
    sgs = []
    try:
        cloud_connection = cloud_connections.get(provider)(log_file, **kwargs)
        c = cloud_connection.get_connection(region, ["ec2"])
        sgs = c.get_all_security_groups(filters={'vpc_id': vpc_id})
    except:
        traceback.print_exc()
    return [(sg.id, '{} ({})'.format(sg.id, sg.name)) for sg in sgs]


def get_aws_ami_ids(provider, region, log_file=None, **kwargs):
    amis = []
    try:
        cloud_connection = cloud_connections.get(provider)(log_file, **kwargs)
        c = cloud_connection.get_connection(region, ["ec2"])
        amis = c.get_all_images(
            filters={
                'image_type': 'machine',
                'is-public': 'false'
            }
        )
        accounts = config.get('display_amis_from_aws_accounts', [])
        if accounts:
            amis += c.get_all_images(
                owners=accounts,
                filters={
                    'image_type': 'machine',
                }
            )
    except:
        traceback.print_exc()
    return [(ami.id, "{}/{} ({})".format(ami.owner_id, ami.id, ami.name)) for ami in amis]


def get_aws_subnet_ids(provider, region, vpc_id, log_file=None, **kwargs):
    subs = []
    try:
        cloud_connection = cloud_connections.get(provider)(log_file, **kwargs)
        c = cloud_connection.get_connection(region, ["vpc"])
        subs = c.get_all_subnets(filters={'vpc_id': vpc_id})
    except:
        traceback.print_exc()
    return [(sub.id, '{} ({})'.format(sub.id, sub.tags.get('Name', ''))) for sub in subs]


def get_aws_subnets_ids_from_app(provider, region, subnets, log_file=None, **kwargs):
    subs = []
    try:
        cloud_connection = cloud_connections.get(provider)(log_file, **kwargs)
        c = cloud_connection.get_connection(region, ["vpc"])
        subs = c.get_all_subnets(subnet_ids=subnets)
    except:
        traceback.print_exc()
    return [('', '')] + [(sub.id, '{} ({} - {})'.format( sub.id, sub.tags.get('Name', ''), sub.cidr_block))
                         for sub in subs]


def get_aws_iam_instance_profiles(provider, region, log_file=None, **kwargs):
    profiles = []
    try:
        cloud_connection = cloud_connections.get(provider)(log_file, **kwargs)
        c = cloud_connection.get_connection(region, ["iam"])
        profiles = c.list_instance_profiles()
    except:
        traceback.print_exc()
    if len(profiles):
        return [(profile.instance_profile_name, '{} ({})'.format(profile.instance_profile_name, profile.arn))
                for profile in profiles.instance_profiles]
    else:
        return []


def get_aws_ec2_key_pairs(provider, region, log_file=None, **kwargs):
    keys = []
    try:
        cloud_connection = cloud_connections.get(provider)(log_file, **kwargs)
        c = cloud_connection.get_connection(region, ["ec2"])
        keys = c.get_all_key_pairs()
    except:
        traceback.print_exc()
    return [(key.name, '{} ({})'.format(key.name, key.fingerprint)) for key in keys]


def get_aws_ec2_regions(provider, log_file=None, **kwargs):
    regions = []
    try:
        cloud_connection = cloud_connections.get(provider)(log_file, **kwargs)
        regions = sorted(cloud_connection.get_regions(["ec2"]), key=lambda region: region.name)
    except:
        traceback.print_exc()
    return [(region.name, '{} ({})'.format(region.name, region.endpoint))
            for region in regions]


def get_aws_as_groups(provider, region, log_file=None, **kwargs):
    asgs = []
    try:
        cloud_connection = cloud_connections.get(provider)(log_file, **kwargs)
        conn_as = cloud_connection.get_connection(region, ['autoscaling'], boto_version='boto3')
        asgs = conn_as.describe_auto_scaling_groups()['AutoScalingGroups']
    except:
        traceback.print_exc()
    return [('', '-- No Autoscale for this app --')] + [
            (asg['AutoScalingGroupName'], '{} ({})'.format(asg['AutoScalingGroupName'], asg['LaunchConfigurationName']))
            for asg in asgs]


def get_ghost_app_as_group(provider, as_group_name, region, log_file=None, **kwargs):
    try:
        cloud_connection = cloud_connections.get(provider)(log_file, **kwargs)
        conn_as = cloud_connection.get_connection(region, ['autoscaling'], boto_version='boto3')
        asgs_page = conn_as.describe_auto_scaling_groups(AutoScalingGroupNames=[as_group_name], MaxRecords=1)
        asgs = asgs_page['AutoScalingGroups']
        if len(asgs) > 0:
            return asgs[0]
        return None
    except:
        traceback.print_exc()
    return None


def get_as_group_instances(provider, as_group, region, log_file=None, **kwargs):
    cloud_connection = cloud_connections.get(provider)(log_file, **kwargs)
    conn = cloud_connection.get_connection(region, ["ec2"])
    instance_ids = []
    for i in as_group['Instances']:
        if i['HealthStatus'] != 'Unhealthy':
            instance_ids.append(i['InstanceId'])
    hosts = []
    if len(instance_ids) > 0:
        instances = conn.get_only_instances(instance_ids=instance_ids)
        for host in instances:
            hosts.append(format_host_infos(host, conn, cloud_connection, region))
    return hosts


def get_elbs_in_as_group(cloud_connection, as_group, region, log_file=None):
    try:
        conn_elb = cloud_connection.get_connection(region, ["ec2", "elb"])
        if len(as_group['LoadBalancerNames']) > 0:
            as_elbs = conn_elb.get_all_load_balancers(load_balancer_names=as_group['LoadBalancerNames'])
            if len(as_elbs) > 0:
                return as_elbs
            else:
                return None
        else:
            return None
    except:
        traceback.print_exc()
    return None


def get_elbs_instances_from_as_group(provider, as_group_name, region, log_file=None, **kwargs):
    lbs_instances = []
    try:
        cloud_connection = cloud_connections.get(provider)(log_file, **kwargs)

        lb_mgr = load_balancing.get_lb_manager(cloud_connection, region, load_balancing.LB_TYPE_AWS_MIXED)
        lb_as_instances = lb_mgr.get_instances_status_from_autoscale(as_group_name,
                                                                     log_file)
        for lb, instances in lb_as_instances.items():
            lbs_instances.append({'elb_name': lb, 'elb_instances': [i_id for i_id, status in instances.items()]})
    except:
        traceback.print_exc()
    return lbs_instances


def get_ghost_app_ec2_instances(provider, ghost_app_name, ghost_env, ghost_role, region, filters=None, log_file=None,
                                ghost_app_color=None, **kwargs):
    filters = filters or []
    cloud_connection = cloud_connections.get(provider)(log_file, **kwargs)
    conn_as = cloud_connection.get_connection(region, ["ec2", "autoscale"])
    conn = cloud_connection.get_connection(region, ["ec2"])

    # Retrieve running instances
    running_instance_filters = {"tag:env": ghost_env, "tag:role": ghost_role, "tag:app": ghost_app_name}
    if ghost_app_color:
        running_instance_filters["tag:color"] = ghost_app_color
    running_instances = conn.get_only_instances(filters=running_instance_filters)

    host_ids_as = []
    if len(filters) > 0:
        for h in filters:
            host_ids_as.append(h['id'])
    hosts = []
    as_instances = conn_as.get_all_autoscaling_instances(instance_ids=[i.id for i in running_instances])
    autoscale_instances = {a.instance_id: a for a in as_instances}
    for instance in running_instances:
        # Instances in autoscale "Terminating:*" states are still "running" but no longer in the Load Balancer
        terminating_states = ['Terminating', 'Terminating:Wait', 'Terminating:Proceed']
        if not instance.id in autoscale_instances or not autoscale_instances[instance.id].lifecycle_state in terminating_states:
            if instance.id not in host_ids_as:
                hosts.append(format_host_infos(instance, conn, cloud_connection, region))
        else:
            hosts.append({'id': instance.id, 'private_ip_address': instance.private_ip_address, 'status': 'terminated'})

    return hosts


def format_host_infos(instance, conn, cloud_connection, region):
    sg_string = None
    image = conn.get_image(instance.image_id)
    image_string = "{ami_id} ({ami_name})".format(ami_id=instance.image_id,
                                                  ami_name=image.name if image is not None else 'deregistered')
    sg_string = ', '.join(["{sg_id} ({sg_name})".format(sg_id=sg.id, sg_name=sg.name) for sg in instance.groups])

    if instance.subnet_id:
        subnets = cloud_connection.get_connection(region, ["vpc"]).get_all_subnets(subnet_ids=[instance.subnet_id])
        subnet_string = instance.subnet_id + ' (' + subnets[0].tags.get('Name', '') + ')'
    else:
        subnet_string = '-'

    host = {
        'id': instance.id,
        'private_ip_address': instance.private_ip_address,
        'public_ip_address': instance.ip_address,
        'status': instance.state,
        'launch_time': datetime.strptime(instance.launch_time, "%Y-%m-%dT%H:%M:%S.%fZ"),
        'security_group': sg_string,
        'subnet_id': subnet_string,
        'image_id': image_string,
        'instance_type': instance.instance_type,
        'instance_profile': str(instance.instance_profile['arn']).split("/")[1] if instance.instance_profile else '-'
    }
    return host


def get_aws_ec2_instance_types(region):
    # TODO: use `get_all_instance_types()` once implemented on AWS side
    # cf. https://github.com/boto/boto/issues/3137
    types = aws_data.instance_types[region]
    return [(instance_type.name,
             '{name} (cores:{cores}, memory:{memory}, disk:{disk})'.format(name=instance_type.name,
                                                                           cores=instance_type.cores,
                                                                           memory=instance_type.memory,
                                                                           disk=instance_type.disk)
             ) for instance_type in types]


def get_safe_deployment_possibilities(app):
    """ Return the list of items needed by the interface for
        safe_deployment_possibilities select

        :param app: Ghost app object
        :return array of pair
    """
    aws_connection_data = get_aws_connection_data(app.get('assumed_account_id', ''), app.get('assumed_role_name', ''),
                                                  app.get('assumed_region_name', ''))
    asg_name = app['autoscale']['name']
    if not asg_name or not get_ghost_app_as_group(app.get('provider', DEFAULT_PROVIDER), asg_name, app['region'],
                                                  **aws_connection_data):
        return [('', '')] + [(None, 'Not Supported because there is no AutoScale Group for this application')]
    app_blue_green, app_color = get_blue_green_from_app(app)
    hosts_list = get_ghost_app_ec2_instances(app.get('provider', DEFAULT_PROVIDER), app['name'], app['env'],
                                             app['role'], app['region'], [], None, app_color, **aws_connection_data)
    safe_possibilities = safe_deployment_possibilities([i for i in hosts_list if i['status'] == 'running'])
    return [('', '')] + [(k, v) for k, v in safe_possibilities.items()]


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
            possibilities['1by1'] = '{0} | {1} '.format(msg, str(' '.join(groups_one))[:-2])
        elif split_type == '1/3' and len(hosts_list) > 2:
            split_list = [hosts_list[i::3] for i in range(3)]
            possibilities['1/3'] = '{0} | Group1 : {1} | Group2 : {2} | Group3 : {3}'.format(msg, len(split_list[0]),
                                                                                             len(split_list[1]),
                                                                                             len(split_list[2]))
        elif split_type == '25%' and len(hosts_list) > 3:
            split_list = [hosts_list[i::4] for i in range(4)]
            possibilities['25%'] = '{0} | Group1 : {1} | Group2 : {2} | Group3 : {3} | Group4 : {4}'.format(msg, len(
                split_list[0]), len(split_list[1]), len(split_list[2]), len(split_list[3]))
        elif split_type == '50%' and len(hosts_list) >= 2:
            split_list = [hosts_list[i::2] for i in range(2)]
            possibilities['50%'] = '{0} | Group1 : {1} | Group2 : {2}'.format(msg, len(split_list[0]),
                                                                              len(split_list[1]))
    if not possibilities:
        possibilities = {'None': 'Not Supported because at least two instances must be running for this application'}
    return possibilities
