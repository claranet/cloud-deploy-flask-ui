import json
import os
import requests
from boto.ec2.instancetype import InstanceType
from data.aws_data_dal import get_aws_per_region_data

# full file AWS_INSTANCES_DATA_URL =
# 'https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonEC2/current/{region}/index.json'
# light file (on demand only extract)
AWS_REGIONS_DATA_URL = 'https://d2xn1uj035lhvj.cloudfront.net/pricing/1.0/ec2/manifest.json'
AWS_REGIONS_LOCATIONS_DATA_PATH = '{cwd}/data/aws_data_regions_locations.json'.format(
    cwd=os.path.dirname(os.path.abspath(__file__))
)

instance_types = {}

# Instance types from China (cn-north-1) region are not available like in others

instance_types['cn-north-1'] = {
    InstanceType(name='t2.micro',    cores='1',  memory='1',     disk='EBS only'),
    InstanceType(name='t2.small',    cores='1',  memory='2',     disk='EBS only'),
    InstanceType(name='t2.medium',   cores='2',  memory='4',     disk='EBS only'),
    InstanceType(name='t2.large',    cores='2',  memory='8',     disk='EBS only'),
    InstanceType(name='t2.xlarge',   cores='4',  memory='16',    disk='EBS only'),
    InstanceType(name='t2.2xlarge',  cores='8',  memory='32',    disk='EBS only'),
    InstanceType(name='m4.large',    cores='2',  memory='8',     disk='EBS only'),
    InstanceType(name='m4.xlarge',   cores='4',  memory='16',    disk='EBS only'),
    InstanceType(name='m4.2xlarge',  cores='8',  memory='32',    disk='EBS only'),
    InstanceType(name='m4.4xlarge',  cores='16', memory='64',    disk='EBS only'),
    InstanceType(name='m4.10xlarge', cores='40', memory='160',   disk='EBS only'),
    InstanceType(name='m4.16xlarge', cores='64', memory='256',   disk='EBS only'),
    InstanceType(name='m3.medium',   cores='1',  memory='3.75',  disk='1 x 4 SSD'),
    InstanceType(name='m3.large',    cores='2',  memory='7.5',   disk='1 x 32 SSD'),
    InstanceType(name='m3.xlarge',   cores='4',  memory='15',    disk='2 x 40 SSD'),
    InstanceType(name='m3.2xlarge',  cores='8',  memory='30',    disk='2 x 80 SSD'),
    InstanceType(name='c4.large',    cores='2',  memory='3.75',  disk='EBS only'),
    InstanceType(name='c4.xlarge',   cores='4',  memory='7.5',   disk='EBS only'),
    InstanceType(name='c4.2xlarge',  cores='8',  memory='15',    disk='EBS only'),
    InstanceType(name='c4.4xlarge',  cores='16', memory='30',    disk='EBS only'),
    InstanceType(name='c4.8xlarge',  cores='36', memory='60',    disk='EBS only'),
    InstanceType(name='c3.large',    cores='2',  memory='3.75',  disk='2 x 16 SSD'),
    InstanceType(name='c3.xlarge',   cores='4',  memory='7.5',   disk='2 x 40 SSD'),
    InstanceType(name='c3.2xlarge',  cores='8',  memory='15',    disk='2 x 80 SSD'),
    InstanceType(name='c3.4xlarge',  cores='16', memory='30',    disk='2 x 160 SSD'),
    InstanceType(name='c3.8xlarge',  cores='32', memory='60',    disk='2 x 320 SSD'),
    InstanceType(name='r3.large',    cores='2',  memory='15',    disk='1 x 32 SSD'),
    InstanceType(name='r3.xlarge',   cores='4',  memory='30.5',  disk='1 x 80 SSD'),
    InstanceType(name='r3.2xlarge',  cores='8',  memory='61',    disk='1 x 160 SSD'),
    InstanceType(name='r3.4xlarge',  cores='16', memory='122',   disk='1 x 320 SSD'),
    InstanceType(name='r3.8xlarge',  cores='32', memory='244',   disk='2 x 320 SSD'),
    InstanceType(name='r4.large',    cores='2',  memory='15.25', disk='EBS only'),
    InstanceType(name='r4.xlarge',   cores='4',  memory='30.5',  disk='EBS only'),
    InstanceType(name='r4.2xlarge',  cores='8',  memory='61',    disk='EBS only'),
    InstanceType(name='r4.4xlarge',  cores='16', memory='122',   disk='EBS only'),
    InstanceType(name='r4.8xlarge',  cores='32', memory='244',   disk='EBS only'),
    InstanceType(name='r4.16xlarge', cores='64', memory='488',   disk='EBS only'),
    InstanceType(name='i2.xlarge',   cores='4',  memory='30.5',  disk='1 x 800 SSD'),
    InstanceType(name='i2.2xlarge',  cores='8',  memory='61',    disk='2 x 800 SSD'),
    InstanceType(name='i2.4xlarge',  cores='16', memory='122',   disk='4 x 800 SSD'),
    InstanceType(name='i2.8xlarge',  cores='32', memory='244',   disk='8 x 800 SSD'),
}  # yapf: disable

instance_types['cn-northwest-1'] = {
    InstanceType(name='t2.micro',    cores='1',  memory='1',     disk='EBS only'),
    InstanceType(name='t2.small',    cores='1',  memory='2',     disk='EBS only'),
    InstanceType(name='t2.medium',   cores='2',  memory='4',     disk='EBS only'),
    InstanceType(name='t2.large',    cores='2',  memory='8',     disk='EBS only'),
    InstanceType(name='t2.xlarge',   cores='4',  memory='16',    disk='EBS only'),
    InstanceType(name='t2.2xlarge',  cores='8',  memory='32',    disk='EBS only'),
    InstanceType(name='m4.large',    cores='2',  memory='8',     disk='EBS only'),
    InstanceType(name='m4.xlarge',   cores='4',  memory='16',    disk='EBS only'),
    InstanceType(name='m4.2xlarge',  cores='8',  memory='32',    disk='EBS only'),
    InstanceType(name='m4.4xlarge',  cores='16', memory='64',    disk='EBS only'),
    InstanceType(name='m4.10xlarge', cores='40', memory='160',   disk='EBS only'),
    InstanceType(name='m4.16xlarge', cores='64', memory='256',   disk='EBS only'),
    InstanceType(name='c4.large',    cores='2',  memory='3.75',  disk='EBS only'),
    InstanceType(name='c4.xlarge',   cores='4',  memory='7.5',   disk='EBS only'),
    InstanceType(name='c4.2xlarge',  cores='8',  memory='15',    disk='EBS only'),
    InstanceType(name='c4.4xlarge',  cores='16', memory='30',    disk='EBS only'),
    InstanceType(name='c4.8xlarge',  cores='36', memory='60',    disk='EBS only'),
    InstanceType(name='g3.4xlarge',  cores='16', memory='122',   disk='EBS only'),
    InstanceType(name='g3.8xlarge',  cores='32', memory='244',   disk='EBS only'),
    InstanceType(name='g3.16xlarge',  cores='64', memory='488',  disk='EBS only'),
    InstanceType(name='r4.large',    cores='2',  memory='15.25', disk='EBS only'),
    InstanceType(name='r4.xlarge',   cores='4',  memory='30.5',  disk='EBS only'),
    InstanceType(name='r4.2xlarge',  cores='8',  memory='61',    disk='EBS only'),
    InstanceType(name='r4.4xlarge',  cores='16', memory='122',   disk='EBS only'),
    InstanceType(name='r4.8xlarge',  cores='32', memory='244',   disk='EBS only'),
    InstanceType(name='r4.16xlarge', cores='64', memory='488',   disk='EBS only'),
    InstanceType(name='i2.xlarge',   cores='4',  memory='30.5',  disk='1 x 800 SSD'),
    InstanceType(name='i2.2xlarge',  cores='8',  memory='61',    disk='2 x 800 SSD'),
    InstanceType(name='i2.4xlarge',  cores='16', memory='122',   disk='4 x 800 SSD'),
    InstanceType(name='i2.8xlarge',  cores='32', memory='244',   disk='8 x 800 SSD'),
}  # yapf: disable


def load_regions_locations(filename):
    """
    >>> locations = load_regions_locations(AWS_REGIONS_LOCATIONS_DATA_PATH)

    >>> {'eu-west-3', 'cn-northwest-1', 'us-gov-west-1'} <= set(locations)
    True

    >>> u', '.join([locations['eu-west-3'], locations['cn-northwest-1'], locations['us-gov-west-1']])
    u'EU (Paris), China (Ningxia), AWS GovCloud (US)'

    >>> u', '.join([locations['sa-east-1']]).encode('ascii', errors='xmlcharrefreplace')
    'South America (S&#227;o Paulo)'
    """
    with open(filename) as data_file:
        locations = {
            location_data.get('Region', ''): location_data.get('Location', '')
            for location_data in json.load(data_file)
        }

    with requests.get(AWS_REGIONS_DATA_URL.format()) as api_regions:
        region_list = api_regions.json()
        supplementary_locations = {
            region: region
            for region in region_list['ec2'] if region not in locations.keys()
        }

    return dict(locations, **supplementary_locations)


regions_locations = load_regions_locations(AWS_REGIONS_LOCATIONS_DATA_PATH)


def load_instance_data(instance_types, regions):
    """
    >>> instance_types = {}
    >>> instance_types['cn-north-1'] = { InstanceType(name='t1.micro', cores='1', memory='0.613', disk='EBS only'), }
    >>> locations = load_regions_locations(AWS_REGIONS_LOCATIONS_DATA_PATH)
    >>> load_instance_data(instance_types, locations)
    Cannot get region cn-northwest-1
    >>> { type.name: type for type in instance_types["cn-north-1"] }['t1.micro']
    InstanceType:t1.micro-1,0.613,EBS only
    >>> { type.name: type for type in instance_types["us-east-1"] }['t2.nano']
    InstanceType:t2.nano-1,0.5 GiB,EBS only
    >>> { type.name: type for type in instance_types["eu-west-1"] }['t3.xlarge']
    InstanceType:t3.xlarge-4,16 GiB,EBS only
    >>> { type.name: type for type in instance_types["us-east-1"] }['c5.large']
    InstanceType:c5.large-2,4 GiB,EBS only
    """

    for region in regions:
        if region not in instance_types:
            instance_types[region] = []
            region_data = get_aws_per_region_data(region)
            if not region_data:
                print 'Cannot get region {r}'.format(r=region)
                continue
            for p in region_data['prices']:
                size = p['attributes']
                instance_types[region].append(InstanceType(name=size['aws:ec2:instanceType'],
                                                           cores=size['aws:ec2:vcpu'],
                                                           memory=size['aws:ec2:memory'],
                                                           disk=size['aws:ec2:storage']))


load_instance_data(instance_types, regions_locations)
