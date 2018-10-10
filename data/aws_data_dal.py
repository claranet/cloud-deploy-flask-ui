"""
    Library with all needed data layer access for AWS Data objects
"""
# -*- coding: utf-8 -*-

from pymongo import MongoClient
from bson.objectid import ObjectId

from settings import MONGO_DBNAME, MONGO_HOST, MONGO_PORT

# DB Access
db = MongoClient(host=MONGO_HOST, port=MONGO_PORT)[MONGO_DBNAME]


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
    return db.aws_data.replace_one(
        {'region': aws_region},
        {'region': aws_region, 'data_latest': json_latest_data, 'data_previous': json_previous_data},
        upsert=True,
    )
