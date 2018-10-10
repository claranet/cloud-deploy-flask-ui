"""
    Script to update AWS Data objects from AWS API Pricing
"""
# -*- coding: utf-8 -*-
import argparse
import os
import requests
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)) + '/..')

from data.aws_data_dal import update_aws_data_region
from aws_data import regions_locations

AWS_INSTANCES_DATA_URL = 'https://d2xn1uj035lhvj.cloudfront.net/pricing/1.0/ec2/region/{region}/ondemand/linux/index.json'


def get_region_data(aws_region):
    with requests.get(AWS_INSTANCES_DATA_URL.format(region=aws_region)) as resp:
        if resp.status_code != 200:
            print 'Cannot get region {r}'.format(r=aws_region)
            return None
    region_data = resp.json()
    return region_data


def parse_args():
    parser = argparse.ArgumentParser(
        description='Manual trigger an AWS Data update.'
    )
    parser.add_argument('-r', '--region', help='Optional argument, to update only a specific region.')
    return parser.parse_args()


def main():
    args = parse_args()
    for aws_region in [args.region] if args.region else regions_locations:
        print('Updating AWS Data for region "{r}"'.format(r=aws_region))
        update_aws_data_region(aws_region, get_region_data(aws_region))


if __name__ == '__main__':
    main()
