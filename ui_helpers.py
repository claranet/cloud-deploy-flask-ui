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


def check_log_id(log_id):
    """
    Check log_id syntax
    :param log_id: string
    :return SRE_Match object

    >>> check_log_id("5ab13d4673c5787c54a75e1d") is not None
    True

    >>> check_log_id("/etc/test") is not None
    False
    """
    return re.match("^[a-f0-9]{24}$", log_id)