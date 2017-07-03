from models.apps import apps_schema as ghost_app_schema
from models.env import env as ghost_env_default_values
from models.instance_role import role as ghost_role_default_values

from web_ui.ghost_client import get_ghost_app
from web_ui.ghost_client import get_ghost_job_commands


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


def get_recommendations(commands_fields, app_modified_fields):
    """
    :param commands_fields:
    :param app_modified_fields:
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
            if field in app_modified_fields.keys():
                recommended_cmds.append({
                    'command': cmd_name,
                    'field': field,
                    'user': app_modified_fields[field]['user'],
                    'updated': app_modified_fields[field]['updated'],
                })
                break

    return recommended_cmds


def get_app_command_recommendations(app_id, app=None):
    """
    Compare modified_fields from the app document with the command's fields

    :param app_id:
    :param app:
    :return: The commands to launch with "modified_fields" data
    """

    if not app:
        app = get_ghost_app(app_id)
    commands_fields = get_ghost_job_commands(with_fields=True)
    app_modified_fields = {ob['field']: ob for ob in app.get('modified_fields', [])}

    return get_recommendations(commands_fields, app_modified_fields)
