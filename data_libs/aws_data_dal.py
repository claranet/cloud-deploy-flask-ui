"""
    Library with all needed data layer access for AWS Data objects
"""
# -*- coding: utf-8 -*-

from pymongo import MongoClient
import logging
import requests

from settings import MONGO_DBNAME, MONGO_HOST, MONGO_PORT

AWS_INSTANCES_DATA_URL = 'https://d2xn1uj035lhvj.cloudfront.net/pricing/1.0/ec2/region/{region}/ondemand/linux/index.json'
AWS_OLD_INSTANCES_DATA_URL = 'https://d2xn1uj035lhvj.cloudfront.net/pricing/1.0/ec2/region/{region}/previous-generation/ondemand/linux/index.json'

# Logging config
logging.basicConfig(format='%(asctime)s %(message)s')

# DB Access
db = MongoClient(host=MONGO_HOST, port=MONGO_PORT, connectTimeoutMS=100, serverSelectionTimeoutMS=100)[MONGO_DBNAME]


def get_fresh_connection():
    return MongoClient(host=MONGO_HOST, port=MONGO_PORT)[MONGO_DBNAME]


def get_deployments_db():
    return db.deploy_histories


# Data Access
def get_aws_per_region_data(aws_region):
    if not aws_region:
        return None
    region_data = db.aws_data.find_one({'region': aws_region})
    return region_data


def update_aws_data_region(aws_region, json_latest_data, json_previous_data):
    if aws_region and json_latest_data:
        payload = {'region': aws_region, 'data_latest': json_latest_data}
        if json_previous_data:
            payload['data_previous'] = json_previous_data
        return db.aws_data.replace_one(
            {'region': aws_region},
            payload,
            upsert=True,
        )


def get_fresh_region_data(aws_region, url):
    with requests.get(url.format(region=aws_region)) as resp:
        if resp.status_code != 200:
            logging.error("Cannot retrieve data from '{}'".format(url.format(region=aws_region)))
            return {}
    region_data = resp.json()
    return region_data or {}
