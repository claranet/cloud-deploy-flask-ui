from libs.lxd import list_lxd_images
import collections
import json
import requests

from models.apps import apps_schema as ghost_app_schema
from models.env import env as ghost_env_default_values
from models.instance_role import role as ghost_role_default_values

from web_ui.ghost_client import get_ghost_app
from web_ui.ghost_client import get_ghost_job_commands

from ghost_tools import config

DEFAULT_ANSIBLE_ROLES_INVENTORY_URL = 'http://inventory.cloudeploy.io/ansible/requirements.json'
DEFAULT_SALT_FORMULAS_INVENTORY_URL = 'http://inventory.cloudeploy.io/salt/morea-salt-formulas.json'


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


def get_default_name_tag(app):
    """ Return the default configuration for the tag "Name"

        :return dict  The default tag "Name" configuration
    """
    return {
        'tag_name': 'Name',
        'tag_value': 'ec2.{GHOST_APP_ENV}.{GHOST_APP_ROLE}.{GHOST_APP_NAME}'.format(
            GHOST_APP_ENV=app['env'],
            GHOST_APP_ROLE=app['role'],
            GHOST_APP_NAME=app['name'])
    }


def get_ghost_app_envs():
    return get_wtforms_selectfield_values(ghost_env_default_values)


def get_ghost_app_providers():
    return get_wtforms_selectfield_values(ghost_app_schema['provider']['allowed'])


def get_ghost_app_roles():
    return get_wtforms_selectfield_values(ghost_role_default_values)


def get_ghost_mod_scopes():
    return get_wtforms_selectfield_values(ghost_app_schema['modules']['schema']['schema']['scope']['allowed'])


def get_ghost_optional_volumes():
    return get_wtforms_selectfield_values(
        ghost_app_schema['environment_infos']['schema']['optional_volumes']['schema']['schema']['volume_type'][
            'allowed'])


def get_ghost_instance_tags():
    return get_wtforms_selectfield_values(
        ghost_app_schema['environment_infos']['schema']['instance_tags']['schema']['schema']['tag_name']['allowed'])


def get_recommendations(commands_fields, app_pending_changes):
    """
    :param commands_fields:
    :param app_pending_changes:
    :return: List of object describing command to run

    >>> cmd_fields = [
    ...     ['cmd1', ['f1', 'f2']],
    ...     ['cmd2', ['prop']],
    ... ]
    >>> app_fields = {
    ...     'f2': {'field': 'f2', 'user': 'api', 'updated': '00:00'}
    ... }
    >>> from pprint import pprint
    >>> pprint(get_recommendations(cmd_fields, app_fields))
    [{'command': 'cmd1', 'field': 'f2', 'updated': '00:00', 'user': 'api'}]
    """
    recommended_cmds = []

    for cmd in commands_fields:
        cmd_name = cmd[0]
        cmd_fields = cmd[1]
        for field in cmd_fields:
            if field in app_pending_changes.keys():
                recommended_cmds.append({
                    'command': cmd_name,
                    'field': field,
                    'user': app_pending_changes[field]['user'],
                    'updated': app_pending_changes[field]['updated'],
                })
                break

    return recommended_cmds


def get_app_command_recommendations(app_id, app=None):
    """
    Compare pending_changes from the app document with the command's fields

    :param app_id:
    :param app:
    :return: The commands to launch with "pending_changes" data
    """

    if not app:
        app = get_ghost_app(app_id)
    commands_fields = get_ghost_job_commands(with_fields=True)
    app_pending_changes = {ob['field']: ob for ob in app.get('pending_changes', [])}

    return get_recommendations(commands_fields, app_pending_changes)


def get_container_images(config=None):
    return list_lxd_images(config)


def get_ansible_role_inventory():
    """
    Requests to load the Ansible Role Inventory file (JSON Format)
    :return: json parsed object
    """
    inventory_url = config.get('features_provisioners', {}).get('ansible', {}).get('ansible_role_inventory_url', DEFAULT_ANSIBLE_ROLES_INVENTORY_URL)
    json_resp = requests.get(inventory_url)
    json_obj = json.loads(json_resp.text, object_pairs_hook=collections.OrderedDict)
    inventory = {role_info.get('name', 'Unknown'): role_info for role_info in json_obj}
    return inventory


def get_salt_formula_inventory():
    """
    Requests to load the Salt formula Inventory file (JSON Format)
    :return: json parsed object
    """
    inventory_url = config.get('features_provisioners', {}).get('salt', {}).get('salt_inventory_url', DEFAULT_SALT_FORMULAS_INVENTORY_URL)
    json_obj = requests.get(inventory_url)
    return json_obj.json()
