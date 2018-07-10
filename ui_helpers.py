import json
import os
import re
import yaml

from flask import Markup

NOT_DEPLOYED_STATE_INFOS = ("exclamation-circle", "not-deployed", "Not deployed")
HALF_DEPLOYED_STATE_INFOS = ("warning", "half-deployed", "Deployment outdated")
FULLY_DEPLOYED_STATE_INFOS = ("check", "fully-deployed", "Fully deployed")
ROOT_PATH = os.path.dirname(os.path.realpath(__file__))

try:
    with open(os.path.dirname(os.path.realpath(__file__)) + '/config.yml', 'r') as conf_file:
        ui_config = yaml.load(conf_file)
except:
    ui_config = {}


def app_modules_state(app):
    """
    Outputs an html snippet with icon and tooltip that indicates the app deployment status
    :param app: dict: a ghost applicatiob
    :return: str: the html snippet
    """
    icon, state, text = NOT_DEPLOYED_STATE_INFOS
    # If all the modules have been deployed at least once
    if all([bool(module.get('last_deployment', False)) for module in app['modules']]):
        # If all the modules are deployed with the current config
        if all([module['initialized'] for module in app['modules']]):
            icon, state, text = FULLY_DEPLOYED_STATE_INFOS
        else:
            icon, state, text = HALF_DEPLOYED_STATE_INFOS
    return Markup('<span class="fa fa-{icon} state-{state}" title="{text}" data-toggle="tooltip"></span>'.format(
        icon=icon, state=state, text=text
    ))


def module_state(module):
    """
    Outputs an html snippet with icon and tooltip that indicates the module deployment status
    :param module: dict: a ghost module
    :return: str: the html snippet
    """
    icon, state, text = NOT_DEPLOYED_STATE_INFOS
    # If the module has been deployed at least once
    if bool(module.get('last_deployment', False)):
        # If the module is deployed with the current config
        if module['initialized']:
            icon, state, text = FULLY_DEPLOYED_STATE_INFOS
        else:
            icon, state, text = HALF_DEPLOYED_STATE_INFOS
    return Markup('<span class="fa fa-{icon} state-{state}" title="{text}" data-toggle="tooltip"></span>'.format(
        icon=icon, state=state, text=text
    ))


def check_status_code(code):
    """
    Checks if the code is HTTP OK
    :param code:
    :return:
    """
    return code and code in [200, 201, 204]


def get_pretty_yaml_from_json(json_obj):
    """
    Get a JSON String and dump it has a pretty YAML string
    :param json_obj: object:
    :return: yaml string
    """
    try:
        return yaml.safe_dump(json_obj, indent=4, allow_unicode=True).decode('utf-8')
    except TypeError as e:
        return ''


def get_pretty_yaml_from_json_str(json_str):
    """
    Get a JSON String and dump it has a pretty YAML string
    :param json_str: string:
    :return: yaml string
    """
    try:
        return yaml.safe_dump(json.loads(json_str), indent=4, allow_unicode=True).decode('utf-8')
    except TypeError as e:
        return ''


def check_instance_tag(tag_key, tag_value, app):
    """
    Check if instance tag given matches the application configuration
    :param tag_key:
    :param tag_value:
    :param app:
    :return: bool

    >>> my_app = {'_id': '123456789', 'name': 'webapp', 'env': 'dev', 'role': 'webfront'}
    >>> check_instance_tag('app', 'nope', my_app)
    False

    >>> check_instance_tag('env', 'prod', my_app)
    False

    >>> check_instance_tag('app', 'webapp', my_app)
    True

    >>> check_instance_tag('app_id', '123456789', my_app)
    True

    >>> check_instance_tag('color', 'green', my_app)
    False

    >>> check_instance_tag('Name', 'ec2.test.front.webapp', my_app)
    False
    """
    if tag_key == 'app_id':
        return tag_value == app['_id']
    if tag_key == 'app':
        return tag_value == app['name']
    if tag_key == 'env':
        return tag_value == app['env']
    if tag_key == 'role':
        return tag_value == app['role']
    if tag_key == 'color':
        return tag_value == app.get('blue_green', {}).get('color')
    if tag_key.startswith('aws:'):
        return True
    instance_tags = {t['tag_name']: t['tag_value'] for t in app.get('environment_infos', {}).get('instance_tags', [])}
    return tag_value == instance_tags.get(tag_key)


def check_instance_tags(tags, app):
    tags_to_check = ['app', 'env', 'role']
    if 'color' in tags:
        tags_to_check.append('color')
    compliant = True
    for tag_key in tags_to_check:
        compliant = compliant and check_instance_tag(tag_key, tags.get(tag_key), app)
    return compliant


def get_app_module_by_name(app, name):
    if not app or not name:
        return None

    for module in app['modules']:
        if module['name'] == name:
            return module

    return None
