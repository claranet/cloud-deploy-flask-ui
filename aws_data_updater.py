"""
    Script to update AWS Data objects from AWS API Pricing
"""
# -*- coding: utf-8 -*-
import argparse
import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)) + '/..')

from data.aws_data_dal import AWS_OLD_INSTANCES_DATA_URL, AWS_INSTANCES_DATA_URL
from data.aws_data_dal import update_aws_data_region, get_fresh_region_data
from aws_data import regions_locations


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
        old_region_data = get_fresh_region_data(aws_region, AWS_OLD_INSTANCES_DATA_URL) or {}
        latest_region_data = get_fresh_region_data(aws_region, AWS_INSTANCES_DATA_URL) or {}
        update_aws_data_region(aws_region, old_region_data, latest_region_data)


if __name__ == '__main__':
    main()
